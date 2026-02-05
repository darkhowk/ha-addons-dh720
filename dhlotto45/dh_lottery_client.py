"""동행복권 API 클라이언트 - v2.0 (개선된 로그인 및 차단 방지)"""

import asyncio
import base64
import datetime
import json
import logging
import random
import time
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlparse

import aiohttp
from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA

_LOGGER = logging.getLogger(__name__)

DH_LOTTERY_URL = "https://dhlottery.co.kr"

# User-Agent 풀 (차단 방지)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
]


def _get_random_user_agent() -> str:
    """랜덤 User-Agent 반환"""
    return random.choice(USER_AGENTS)


def _build_browser_headers(user_agent: str) -> dict[str, str]:
    """현대 브라우저 헤더 생성"""
    return {
        "User-Agent": user_agent,
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        "DNT": "1",
    }


@dataclass
class DhLotteryBalanceData:
    deposit: int = 0
    purchase_available: int = 0
    reservation_purchase: int = 0
    withdrawal_request: int = 0
    purchase_impossible: int = 0
    this_month_accumulated_purchase: int = 0


class DhLotteryError(Exception):
    """DH Lottery 예외 클래스"""


class DhAPIError(DhLotteryError):
    """DH API 예외 클래스"""


class DhLotteryLoginError(DhLotteryError):
    """로그인 실패 예외"""


class DhLotteryClient:
    """동행복권 클라이언트 - v2.0"""

    def __init__(self, username: str, password: str):
        self.username = username
        self._password = password
        self.session: Optional[aiohttp.ClientSession] = None
        self._lock = asyncio.Lock()
        self.logged_in = False
        
        # Rate limiting & throttling
        self._min_request_interval = 2.0
        self._max_request_interval = 4.0
        self._last_request_time: float = 0
        self._request_lock = asyncio.Lock()
        
        # User-Agent 관리
        self._current_user_agent = _get_random_user_agent()
        self._ua_rotation_count = 0
        self._ua_rotation_interval = random.randint(20, 40)
        
        # Circuit breaker
        self._consecutive_failures = 0
        self._circuit_failure_threshold = 2
        self._circuit_open_time: float = 0
        self._circuit_cooldown = 180.0
        
        # RSA 키 캐시
        self._cached_rsa_key: Optional[tuple[str, str]] = None
        self._rsa_key_time: float = 0
        self._rsa_key_ttl = 180
        
        _LOGGER.info(
            "[DHLottery] 클라이언트 초기화 v2.0 - 요청간격: %.1f~%.1fs",
            self._min_request_interval,
            self._max_request_interval,
        )

    def _create_session(self):
        """세션 생성"""
        if self.session and not self.session.closed:
            return
        
        # 새 UA로 변경
        self._current_user_agent = _get_random_user_agent()
        
        self.session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False),
            headers=_build_browser_headers(self._current_user_agent),
            timeout=aiohttp.ClientTimeout(total=60),
            cookie_jar=aiohttp.CookieJar(unsafe=True),
        )
        
        _LOGGER.info("[DHLottery] 새 세션 생성 완료")

    async def close(self):
        """세션 종료"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
            self.logged_in = False

    async def _throttle_request(self) -> None:
        """요청 간 랜덤 딜레이 적용"""
        async with self._request_lock:
            now = time.time()
            elapsed = now - self._last_request_time
            
            # 랜덤 간격
            target_interval = random.uniform(
                self._min_request_interval, 
                self._max_request_interval
            )
            
            if elapsed < target_interval:
                delay = target_interval - elapsed
                _LOGGER.debug("[DHLottery] 스로틀링: %.2f초 대기", delay)
                try:
                    await asyncio.sleep(delay)
                except asyncio.CancelledError:
                    raise
            
            self._last_request_time = time.time()
            
            # UA 로테이션
            self._ua_rotation_count += 1
            if self._ua_rotation_count >= self._ua_rotation_interval:
                old_ua = self._current_user_agent
                available_uas = [ua for ua in USER_AGENTS if ua != old_ua]
                self._current_user_agent = random.choice(available_uas) if available_uas else random.choice(USER_AGENTS)
                self._ua_rotation_count = 0
                self._ua_rotation_interval = random.randint(20, 40)
                _LOGGER.debug("[DHLottery] UA 로테이션 완료")

    def _get_headers(self, extra: Optional[dict] = None) -> dict[str, str]:
        """현재 User-Agent가 적용된 헤더 반환"""
        headers = _build_browser_headers(self._current_user_agent)
        if extra:
            headers.update(extra)
        return headers

    async def _warmup_session(self):
        """세션 워밍업 - 쿠키 초기화"""
        if not self.session or self.session.closed:
            self._create_session()
        
        try:
            _LOGGER.info("[DHLottery] 세션 워밍업 중...")
            
            # 메인 페이지 방문
            resp = await self.session.get(
                f"{DH_LOTTERY_URL}/",
                headers=self._get_headers(),
                allow_redirects=True,
            )
            
            if resp.status == 200:
                _LOGGER.info("[DHLottery] 워밍업 완료 (HTTP 200)")
                return True
            else:
                _LOGGER.warning("[DHLottery] 워밍업 실패 (HTTP %s)", resp.status)
                return False
                
        except Exception as e:
            _LOGGER.warning("[DHLottery] 워밍업 실패: %s", e)
            return False

    async def _get_rsa_key(self) -> tuple[str, str]:
        """RSA 공개키 조회 (캐시 사용)"""
        now = time.time()
        
        # 캐시된 키가 있고 유효하면 반환
        if self._cached_rsa_key and (now - self._rsa_key_time) < self._rsa_key_ttl:
            return self._cached_rsa_key
        
        await self._throttle_request()
        
        try:
            resp = await self.session.get(
                f"{DH_LOTTERY_URL}/login/selectRsaModulus.do",
                headers=self._get_headers(),
            )
            
            result = await resp.json()
            data = result.get("data")
            
            if not data:
                raise DhLotteryError("RSA 키 조회 실패")
            
            modulus = data.get("rsaModulus")
            exponent = data.get("publicExponent")
            
            if not modulus or not exponent:
                raise DhLotteryError("RSA 키 데이터 없음")
            
            # 캐시 저장
            self._cached_rsa_key = (modulus, exponent)
            self._rsa_key_time = now
            
            _LOGGER.debug("[DHLottery] RSA 키 조회 완료 (캐시됨)")
            return modulus, exponent
            
        except Exception as e:
            raise DhLotteryError(f"RSA 키 조회 실패: {e}") from e

    def _rsa_encrypt(self, text: str, modulus_hex: str, exponent_hex: str) -> str:
        """RSA 암호화"""
        try:
            # 16진수를 정수로 변환
            n = int(modulus_hex, 16)
            e = int(exponent_hex, 16)
            
            # RSA 키 생성
            public_key = RSA.construct((n, e))
            cipher = PKCS1_v1_5.new(public_key)
            
            # 암호화
            encrypted = cipher.encrypt(text.encode('utf-8'))
            
            # Base64 인코딩
            return base64.b64encode(encrypted).decode('utf-8')
            
        except Exception as ex:
            raise DhLotteryError(f"RSA 암호화 실패: {ex}") from ex

    async def async_login(self, force: bool = False):
        """로그인 수행"""
        if self.logged_in and not force:
            return
        
        async with self._lock:
            if self.logged_in and not force:
                return
            
            _LOGGER.info("[DHLottery] 로그인 시작...")
            
            # 세션 생성 및 워밍업
            if not self.session or self.session.closed:
                self._create_session()
            
            # 워밍업
            await self._warmup_session()
            
            # RSA 키 조회
            modulus, exponent = await self._get_rsa_key()
            
            # 암호화
            enc_user_id = await asyncio.to_thread(
                self._rsa_encrypt, self.username, modulus, exponent
            )
            enc_password = await asyncio.to_thread(
                self._rsa_encrypt, self._password, modulus, exponent
            )
            
            # 로그인 요청
            await self._throttle_request()
            
            headers = self._get_headers({
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": DH_LOTTERY_URL,
                "Referer": f"{DH_LOTTERY_URL}/common.do?method=login",
            })
            
            data = {
                "userId": enc_user_id,
                "userPswdEncn": enc_password,
                "inpUserId": self.username,
            }
            
            try:
                resp = await self.session.post(
                    f"{DH_LOTTERY_URL}/login/securityLoginCheck.do",
                    headers=headers,
                    data=data,
                    allow_redirects=False,  # 리다이렉트 확인을 위해
                )
                
                # 성공 확인
                if resp.status in (200, 302):
                    # Location 헤더 확인
                    location = resp.headers.get('Location', '')
                    response_url = str(resp.url)
                    
                    if 'loginSuccess' in location or 'loginSuccess' in response_url:
                        self.logged_in = True
                        self._consecutive_failures = 0
                        _LOGGER.info("[DHLottery] ✓ 로그인 성공")
                        return
                
                # 실패
                self._consecutive_failures += 1
                self.logged_in = False
                raise DhLotteryLoginError(
                    "로그인 실패: 아이디 또는 비밀번호를 확인해주세요. "
                    "(5회 이상 실패 시 계정이 잠길 수 있습니다)"
                )
                
            except DhLotteryError:
                raise
            except Exception as ex:
                self._consecutive_failures += 1
                self.logged_in = False
                raise DhLotteryError(f"로그인 요청 실패: {ex}") from ex

    async def _check_soundness_pledge(self) -> dict:
        """건전서약 확인"""
        await self._throttle_request()
        
        try:
            resp = await self.session.get(
                f"{DH_LOTTERY_URL}/mypage/selectSoundnessPldgInfo.do",
                headers=self._get_headers(),
            )
            
            result = await resp.json()
            data = result.get("data", {})
            
            pledged = data.get("isPldg") == "Y"
            
            return {
                "pledged": pledged,
                "data": data,
            }
            
        except Exception as e:
            _LOGGER.warning("[DHLottery] 건전서약 확인 실패: %s", e)
            return {"pledged": True, "data": {}}  # 기본값: 통과

    @staticmethod
    async def handle_response_json(response: aiohttp.ClientResponse) -> dict[str, Any]:
        """응답을 JSON으로 파싱"""
        try:
            result = await response.json()
        except Exception as ex:
            raise DhAPIError(f'API 응답 파싱 실패: {ex}')

        if response.status != 200:
            raise DhAPIError(f'API 요청 실패: HTTP {response.status}')

        if 'data' not in result:
            raise DhLotteryError('API 응답 데이터 없음')
            
        return result.get('data', {})

    async def async_get(self, path: str, params: dict) -> dict:
        """GET 요청"""
        if not self.session or self.session.closed:
            self._create_session()
        
        await self._throttle_request()
        
        try:
            resp = await self.session.get(
                url=f"{DH_LOTTERY_URL}/{path}",
                params=params,
                headers=self._get_headers(),
            )
            return await self.handle_response_json(resp)
        except DhLotteryError:
            raise
        except Exception as ex:
            raise DhLotteryError(f"GET 요청 실패: {ex}") from ex

    async def async_get_with_login(
        self,
        path: str,
        params: dict,
        retry: int = 1,
    ) -> dict[str, Any]:
        """로그인이 필요한 GET 요청"""
        async with self._lock:
            try:
                return await self.async_get(path, params)
            except DhAPIError:
                if retry > 0:
                    _LOGGER.info("[DHLottery] API 에러, 재로그인 후 재시도...")
                    await self.async_login(force=True)
                    return await self.async_get_with_login(path, params, retry - 1)
                raise DhLotteryLoginError("로그인 또는 API 요청 실패")
            except DhLotteryError:
                raise
            except Exception as ex:
                raise DhLotteryError(f"로그인 필요 요청 실패: {ex}") from ex

    async def async_get_balance(self) -> DhLotteryBalanceData:
        """예치금 현황 조회"""
        try:
            current_time = int(datetime.datetime.now().timestamp() * 1000)
            
            user_result = await self.async_get_with_login(
                "mypage/selectUserMndp.do",
                params={"_": current_time}
            )

            user_mndp = user_result.get("userMndp", {})
            pnt_dpst_amt = user_mndp.get("pntDpstAmt", 0)
            pnt_tkmny_amt = user_mndp.get("pntTkmnyAmt", 0)
            ncsbl_dpst_Amt = user_mndp.get("ncsblDpstAmt", 0)
            ncsbl_tkmny_amt = user_mndp.get("ncsblTkmnyAmt", 0)
            csbl_dpst_amt = user_mndp.get("csblDpstAmt", 0)
            csbl_tkmny_amt = user_mndp.get("csblTkmnyAmt", 0)
            total_amt = (
                (pnt_dpst_amt - pnt_tkmny_amt) +
                (ncsbl_dpst_Amt - ncsbl_tkmny_amt) +
                (csbl_dpst_amt - csbl_tkmny_amt)
            )

            crnt_entrs_amt = user_mndp.get("crntEntrsAmt", 0)
            rsvt_ordr_amt = user_mndp.get("rsvtOrdrAmt", 0)
            daw_aply_amt = user_mndp.get("dawAplyAmt", 0)
            fee_amt = user_mndp.get("feeAmt", 0)

            purchase_impossible = rsvt_ordr_amt + daw_aply_amt + fee_amt

            home_result = await self.async_get_with_login(
                "mypage/selectMyHomeInfo.do",
                params={"_": current_time},
            )
            prchs_lmt_info = home_result.get("prchsLmtInfo", {})
            wly_prchs_acml_amt = prchs_lmt_info.get("wlyPrchsAcmlAmt", 0)

            return DhLotteryBalanceData(
                deposit=total_amt,
                purchase_available=crnt_entrs_amt,
                reservation_purchase=rsvt_ordr_amt,
                withdrawal_request=daw_aply_amt,
                purchase_impossible=purchase_impossible,
                this_month_accumulated_purchase=wly_prchs_acml_amt,
            )
        except Exception as ex:
            raise DhLotteryError(f"예치금 조회 실패: {ex}") from ex

    async def async_get_buy_list(self, lotto_id: str) -> list[dict[str, Any]]:
        """1주일간의 구매내역 조회"""
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=7)
        
        try:
            result = await self.async_get_with_login(
                "mypage/selectMyLotteryledger.do",
                params={
                    "srchStrDt": start_date.strftime("%Y%m%d"),
                    "srchEndDt": end_date.strftime("%Y%m%d"),
                    "ltGdsCd": lotto_id,
                    "pageNum": 1,
                    "recordCountPerPage": 1000,
                    "_": int(datetime.datetime.now().timestamp() * 1000)
                },
            )
            return result.get("list", [])
        except Exception as ex:
            raise DhLotteryError(f"구매내역 조회 실패: {ex}") from ex

    async def async_get_accumulated_prize(self, lotto_id: str) -> int:
        """당첨금 누적금액 조회 (1년)"""
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=365)
        
        try:
            result = await self.async_get_with_login(
                "mypage/selectMyLotteryledger.do",
                params={
                    "srchStrDt": start_date.strftime("%Y%m%d"),
                    "srchEndDt": end_date.strftime("%Y%m%d"),
                    "ltGdsCd": lotto_id,
                    "pageNum": 1,
                    "winResult": "T",
                    "recordCountPerPage": 1000,
                    "_": int(datetime.datetime.now().timestamp() * 1000),
                },
            )
            items = result.get("list", [])

            accum_prize = 0
            for item in items:
                accum_prize += item.get("ltWnAmt", 0)
            return accum_prize

        except Exception as ex:
            raise DhLotteryError(f"당첨금 조회 실패: {ex}") from ex

    def __del__(self):
        """소멸자"""
        if self.session and not self.session.closed:
            _LOGGER.warning("[DHLottery] 세션이 제대로 닫히지 않았습니다")
