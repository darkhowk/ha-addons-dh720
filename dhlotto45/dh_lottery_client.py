import datetime
import logging
import asyncio
from dataclasses import dataclass
from typing import Any, Optional

import aiohttp

from dh_rsa import RSAKey

_LOGGER = logging.getLogger(__name__)

DH_LOTTERY_URL = "https://www.dhlottery.co.kr"

@dataclass
class DhLotteryBalanceData:
    deposit: int = 0  # 총Balance
    purchase_available: int = 0  # purchase능금액
    reservation_purchase: int = 0  # 예약purchase금액
    withdrawal_request: int = 0  # 출금신청중금액
    purchase_impossible: int = 0  # purchase불능금액
    this_month_accumulated_purchase: int = 0  # 번달누적purchase금액


class DhLotteryError(Exception):
    """DH Lottery 예외 클래스입니다."""

class DhAPIError(DhLotteryError):
    """DH API 예외 클래스입니다."""

class DhLotteryLoginError(DhLotteryError):
    """Login failed했 때 발생하는 예외입니다."""


class DhLotteryClient:
    """동행복권 클라언트 클래스입니다."""

    def __init__(self, username: str, password: str):
        """DhLotteryClient 클래스 초기화합니다."""
        self.username = username
        self._password = password
        self.session: Optional[aiohttp.ClientSession] = None
        self._rsa_key = RSAKey()
        self._lock = asyncio.Lock()
        self.logged_in = False
        self._create_session()

    def _create_session(self):
        """세션 생성합니다."""
        if self.session and not self.session.closed:
            return
        
        self.session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False),
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/143.0.0.0 Safari/537.36",
                "Connection": "keep-alive",
                "Cache-Control": "max-age=0",
                "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "Upgrade-Insecure-Requests": "1",
                "Origin": DH_LOTTERY_URL,
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,"
                "*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Referer": f"{DH_LOTTERY_URL}/login",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-User": "?1",
                "Sec-Fetch-Dest": "document",
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                "DNT": "1",
            },
            timeout=aiohttp.ClientTimeout(total=30),
        )

    async def close(self):
        """세션 ended합니다."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
            self.logged_in = False

    @staticmethod
    async def handle_response_json(response: aiohttp.ClientResponse) -> dict[str, Any]:
        """응답 JSON으로 파싱합니다."""
        try:
            result = await response.json()
        except Exception as ex:
            raise DhAPIError(f'[ERROR]  API    : {ex}')

        if response.status != 200 or response.reason != 'OK':
            raise DhAPIError(f'[ERROR]  API  failed: {response.status} {response.reason}')

        if 'data' not in result:
            raise DhLotteryError('[ERROR]  API    .')
        return result.get('data', {})

    async def async_get(self, path: str, params: dict) -> dict:
        """Login 필요 not page 져옵니다."""
        if not self.session or self.session.closed:
            self._create_session()
        
        try:
            resp = await self.session.get(
                url=f"{DH_LOTTERY_URL}/{path}", 
                params=params
            )
            return await self.handle_response_json(resp)
        except DhLotteryError:
            raise
        except Exception as ex:
            raise DhLotteryError(
                f"[ERROR] page fetch failed: {ex}"
            ) from ex

    async def async_get_with_login(
        self,
        path: str,
        params: dict,
        retry: int = 1,
    ) -> dict[str, Any]:
        """Login 필요한 page 져옵니다."""
        async with self._lock:
            try:
                return await self.async_get(path, params)
            except DhAPIError:
                if retry > 0:
                    _LOGGER.info("API error, retrying with login...")
                    await self.async_login()
                    return await self.async_get_with_login(path, params, retry - 1)
                raise DhLotteryLoginError("[ERROR] Login  API  failed.")
            except DhLotteryError:
                raise
            except Exception as ex:
                raise DhLotteryError(
                    f"[ERROR] Login  page fetch failed: {ex}"
                ) from ex

    async def async_login(self):
        """Login 수행합니다."""
        _LOGGER.info("Login ")
        
        if not self.session or self.session.closed:
            self._create_session()
        
        try:
            # RSA 키 획득
            await self._async_set_select_rsa_module()
            
            # Login POST 요청
            resp = await self.session.post(
                url=f"{DH_LOTTERY_URL}/login/securityLoginCheck.do",
                data={
                    "userId": self._rsa_key.encrypt(self.username),
                    "userPswdEncn": self._rsa_key.encrypt(self._password),
                    "inpUserId": self.username,
                },
                allow_redirects=True,  # 리다렉트 자동 처리
            )
            
            # Login 성공 확인
            final_url = str(resp.url)
            _LOGGER.info(f"Login   URL: {final_url}")
            _LOGGER.info(f" : {resp.status} {resp.reason}")
            
            # 리다렉트 히스토리 확인
            if resp.history:
                _LOGGER.info(f" : {len(resp.history)}")
                for i, redirect_resp in enumerate(resp.history):
                    _LOGGER.debug(f"  {i+1}. {redirect_resp.status} -> {redirect_resp.url}")
            
            # 성공 조건: 200 OK고 URL loginSuccess.do 포함
            if resp.status == 200 and 'loginSuccess.do' in final_url:
                self.logged_in = True
                _LOGGER.info("Login !")
                return
            
            # failed 처리
            _LOGGER.error(f"Login failed - Status: {resp.status}, URL: {final_url}")
            self.logged_in = False
            
            # 응답 내용 확인 (디버깅용)
            try:
                response_text = await resp.text()
                if "failed" in response_text or "" in response_text:
                    _LOGGER.error(f"    : {response_text[:200]}")
            except:
                pass
            
            raise DhLotteryLoginError(
                "Login failed.   number . "
                "(5 failed  .   page number  )"
            )
            
        except DhLotteryError:
            raise
        except Exception as ex:
            self.logged_in = False
            _LOGGER.exception("Login   ")
            raise DhLotteryError(f"[ERROR] Login execute failed: {ex}") from ex

    async def _async_set_select_rsa_module(self) -> None:
        """RSA 모듈 설정합니다. API 우선, failed 시 Login page서 파싱"""
        try:
            # 먼저 API 엔드포인트 시도
            resp = await self.session.get(
                url=f"{DH_LOTTERY_URL}/login/selectRsaModulus.do",
            )
            result = await resp.json()
            data = result.get("data")
            if data and data.get("rsaModulus") and data.get("publicExponent"):
                self._rsa_key.set_public(
                    data.get("rsaModulus"), data.get("publicExponent")
                )
                _LOGGER.info("RSA  API .")
                return
        except Exception as e:
            _LOGGER.warning(f"API RSA   failed: {e}, Login page  ")
        
        # API failed 시 Login page서 RSA 키 파싱
        try:
            import re
            resp = await self.session.get(url=f"{DH_LOTTERY_URL}/login")
            html = await resp.text()
            
            # HTML서 rsaModulus와 publicExponent 추출
            modulus_match = re.search(r"var\s+rsaModulus\s*=\s*'([a-fA-F0-9]+)'", html)
            exponent_match = re.search(r"var\s+publicExponent\s*=\s*'([a-fA-F0-9]+)'", html)
            
            if modulus_match and exponent_match:
                self._rsa_key.set_public(
                    modulus_match.group(1),
                    exponent_match.group(1)
                )
                _LOGGER.info("RSA  Login page .")
                return
            else:
                raise DhLotteryError("Login page RSA    .")
        except Exception as ex:
            raise DhLotteryError(f"RSA  fetch failed: {ex}") from ex

    async def async_get_balance(self) -> DhLotteryBalanceData:
        """Balance status query합니다."""
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
            total_amt = (pnt_dpst_amt - pnt_tkmny_amt) + (ncsbl_dpst_Amt - ncsbl_tkmny_amt) + (csbl_dpst_amt - csbl_tkmny_amt)

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
            raise DhLotteryError(f"[ERROR] Balance status query failed: {ex}") from ex

    async def async_get_buy_list(self, lotto_id: str) -> list[dict[str, Any]]:
        """1주일간 purchasehistory query합니다."""
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
            raise DhLotteryError(
                f"[ERROR] recent 1 purchasehistory query failed: {ex}"
            ) from ex

    async def async_get_accumulated_prize(self, lotto_id: str) -> int:
        """payment deadline ended되지 not winning금 accumulated amount query합니다. 기간 1년"""
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

            accum_prize: int = 0
            for item in items:
                accum_prize += item.get("ltWnAmt", 0)
            return accum_prize

        except Exception as ex:
            raise DhLotteryError(
                f"[ERROR] payment deadline ended not winning query : {ex}"
            ) from ex

    def __del__(self):
        """소멸자"""
        if self.session and not self.session.closed:
            _LOGGER.warning("Session was not properly closed")

    async def async_get_balance(self) -> DhLotteryBalanceData:
        """Balance status query합니다."""
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
            total_amt = (pnt_dpst_amt - pnt_tkmny_amt) + (ncsbl_dpst_Amt - ncsbl_tkmny_amt) + (csbl_dpst_amt - csbl_tkmny_amt)

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
            raise DhLotteryError(f"[ERROR] Balance status query failed: {ex}") from ex

    async def async_get_buy_list(self, lotto_id: str) -> list[dict[str, Any]]:
        """1주일간 purchasehistory query합니다."""
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
            raise DhLotteryError(
                f"[ERROR] recent 1 purchasehistory query failed: {ex}"
            ) from ex

    async def async_get_accumulated_prize(self, lotto_id: str) -> int:
        """payment deadline ended되지 not winning금 accumulated amount query합니다. 기간 1년"""
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

            accum_prize: int = 0
            for item in items:
                accum_prize += item.get("ltWnAmt", 0)
            return accum_prize

        except Exception as ex:
            raise DhLotteryError(
                f"[ERROR] payment deadline ended not winning query : {ex}"
            ) from ex

    def __del__(self):
        """소멸자"""
        if self.session and not self.session.closed:
            _LOGGER.warning("Session was not properly closed")
