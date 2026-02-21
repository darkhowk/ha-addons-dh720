# -*- coding: utf-8 -*-
"""
DH Lottery Pension 720+ Client
연금복권 720+ 구매 및 정보 조회

암호화: AES-128-CBC + PBKDF2(SHA256, 1000iter) / key = JSESSIONID[:32]
Base URL: https://el.dhlottery.co.kr
Purchase Flow: makeOrderNo.do → connPro.do → checkDeposit.do
"""

import os
import logging
import base64
import time
from dataclasses import dataclass
from typing import Optional, List
from urllib.parse import urlencode, parse_qs, quote

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as sym_padding
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from yarl import URL

_LOGGER = logging.getLogger(__name__)

EL_BASE_URL = "https://el.dhlottery.co.kr"


class DhPension720Error(Exception):
    pass


class DhPension720PurchaseError(DhPension720Error):
    pass


@dataclass
class DhPension720BalanceData:
    deposit: int = 0
    purchase_available: int = 0


@dataclass
class DhPension720BuyData:
    round_no: int
    ticket_count: int
    tickets: str
    fail_count: int
    fail_tickets: str
    deposit: int
    amount: int


@dataclass
class DhPension720BuyHistoryData:
    round_no: int
    issue_dt: str
    barcode: str
    ticket_count: int
    amount: int
    result: str


# ---------------------------------------------------------------------------
# AES encryption / decryption  (matches game.jsp encrypt() / decrypt())
# ---------------------------------------------------------------------------

def _encrypt(plaintext: str, jsessionid: str) -> str:
    """
    AES-128-CBC encrypt with PBKDF2 key derivation.
    Returns URL-encoded string matching JavaScript encrypt().

    Format: hex(salt,32B) + hex(iv,16B) + base64(ciphertext)
    Then URL-encoded (encodeURIComponent).
    """
    passphrase = jsessionid[:32].encode("utf-8")
    salt = os.urandom(32)
    iv = os.urandom(16)

    key = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=16, salt=salt, iterations=1000
    ).derive(passphrase)

    padder = sym_padding.PKCS7(128).padder()
    padded = padder.update(plaintext.encode("utf-8")) + padder.finalize()

    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()

    raw = salt.hex() + iv.hex() + base64.b64encode(ciphertext).decode("ascii")
    return quote(raw, safe="")


def _decrypt(enc_text: str, jsessionid: str) -> str:
    """
    AES-128-CBC decrypt with PBKDF2 key derivation.
    Matches JavaScript decrypt().
    """
    passphrase = jsessionid[:32].encode("utf-8")

    salt = bytes.fromhex(enc_text[:64])
    iv = bytes.fromhex(enc_text[64:96])
    ciphertext = base64.b64decode(enc_text[96:])

    key = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=16, salt=salt, iterations=1000
    ).derive(passphrase)

    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()

    unpadder = sym_padding.PKCS7(128).unpadder()
    plaintext = unpadder.update(padded) + unpadder.finalize()
    return plaintext.decode("utf-8")


# ---------------------------------------------------------------------------
# Main client class
# ---------------------------------------------------------------------------

class DhPension720:
    """연금복권 720+ 클라이언트"""

    def __init__(self, client):
        """
        Args:
            client: DhLotteryClient 인스턴스 (로그인 완료 상태)
        """
        self.client = client
        self._jsessionid: Optional[str] = None

    # ------------------------------------------------------------------
    # Session helpers
    # ------------------------------------------------------------------

    async def _ensure_session(self):
        """el.dhlottery.co.kr 세션(JSESSIONID) 확보

        NOTE:
          - el.dhlottery.co.kr 쪽은 때때로 redirect를 타거나,
            Set-Cookie가 최초 응답(resp / resp.history)에만 내려오는 경우가 있음.
          - aiohttp는 resp.cookies 및 cookie_jar 둘 다 활용하는 편이 안전.
        """
        if self._jsessionid:
            return

        async def _pick_jsessionid_from_response(resp) -> Optional[str]:
            """Try multiple sources:
            - resp.cookies
            - resp.history cookies
            - raw Set-Cookie headers (covers cases where cookie jar doesn't store)
            """
            # 1) 현재 응답 쿠키
            try:
                if resp.cookies:
                    # accept any cookie key that starts with JSESSIONID
                    for k, v in resp.cookies.items():
                        if k.upper().startswith("JSESSIONID"):
                            return v.value
            except Exception:
                pass

            # 2) redirect 히스토리 쿠키
            try:
                for h in (resp.history or []):
                    if not h.cookies:
                        continue
                    for k, v in h.cookies.items():
                        if k.upper().startswith("JSESSIONID"):
                            return v.value
            except Exception:
                pass

            # 3) raw Set-Cookie headers
            try:
                hdrs = []
                try:
                    hdrs = resp.headers.getall("Set-Cookie", [])
                except Exception:
                    v = resp.headers.get("Set-Cookie")
                    if v:
                        hdrs = [v]

                for line in hdrs:
                    # e.g. "JSESSIONID=....; Path=/; Secure; HttpOnly"
                    parts = [p.strip() for p in line.split(";") if p.strip()]
                    if not parts:
                        continue
                    kv = parts[0]
                    if "=" not in kv:
                        continue
                    name, val = kv.split("=", 1)
                    if name.upper().startswith("JSESSIONID") and val:
                        return val
            except Exception:
                pass

            return None

        async def _log_cookiejar(prefix: str = ""):
            for cookie in self.client.session.cookie_jar:
                try:
                    _LOGGER.debug(
                        f"{prefix}[PENSION720] cookie: {cookie.key}={cookie.value[:16]}... "
                        f"domain={cookie.get('domain', '?')} path={cookie.get('path','?')}"
                    )
                except Exception:
                    continue

        # (A) 먼저 EL 루트 1회 방문해서 기본 세션 생성 시도
        try:
            async with self.client.session.get(
                f"{EL_BASE_URL}/",
                allow_redirects=True,
                headers={
                    "Origin": EL_BASE_URL,
                    "Referer": f"{EL_BASE_URL}/",
                },
            ) as resp0:
                # ensure response is consumed so aiohttp processes cookies reliably
                try:
                    await resp0.text()
                except Exception:
                    pass

                _LOGGER.info(
                    f"[PENSION720] el root status={resp0.status}, url={resp0.url}"
                )
                self._jsessionid = await _pick_jsessionid_from_response(resp0)
        except Exception as e:
            _LOGGER.warning(f"[PENSION720] el root visit failed (ignored): {e}")

        # (B) game.jsp 방문 (핵심)
        if not self._jsessionid:
            async with self.client.session.get(
                f"{EL_BASE_URL}/game/pension720/game.jsp",
                allow_redirects=True,
                headers={
                    "Origin": EL_BASE_URL,
                    "Referer": f"{EL_BASE_URL}/game/pension720/game.jsp",
                },
            ) as resp:
                try:
                    await resp.text()
                except Exception:
                    pass

                _LOGGER.info(
                    f"[PENSION720] game.jsp status={resp.status}, url={resp.url}"
                )

                # 응답/히스토리/Set-Cookie에서 직접 추출
                self._jsessionid = await _pick_jsessionid_from_response(resp)

        # (C) cookie_jar에서 재시도
        if not self._jsessionid:
            cookies = self.client.session.cookie_jar.filter_cookies(URL(EL_BASE_URL))
            morsel = cookies.get("JSESSIONID")
            if morsel:
                self._jsessionid = morsel.value

        # (D) 마지막으로 전체 cookie_jar를 훑어서 JSESSIONID 찾기
        if not self._jsessionid:
            for cookie in self.client.session.cookie_jar:
                if cookie.key == "JSESSIONID":
                    self._jsessionid = cookie.value
                    break

        if not self._jsessionid:
            await _log_cookiejar(prefix="")
            all_cookies = [
                f"{c.key}(domain={c.get('domain', '?')},path={c.get('path','?')})"
                for c in self.client.session.cookie_jar
            ]
            _LOGGER.error(
                f"[PENSION720] JSESSIONID 없음. 전체 쿠키: {all_cookies}"
            )
            raise DhPension720Error("JSESSIONID를 가져올 수 없습니다")

        _LOGGER.info(f"[PENSION720] JSESSIONID: {self._jsessionid[:8]}...")

    def _enc(self, form_data: str) -> str:
        return _encrypt(form_data, self._jsessionid)

    def _dec(self, enc_text: str) -> str:
        return _decrypt(enc_text, self._jsessionid)

    @staticmethod
    def _parse(decrypted: str) -> dict:
        """URL-encoded 응답 → dict"""
        params = parse_qs(decrypted, keep_blank_values=True)
        return {k: v[0] if len(v) == 1 else v for k, v in params.items()}

    # ------------------------------------------------------------------
    # Plain-JSON info endpoints (암호화 불필요)
    # ------------------------------------------------------------------

    async def async_get_round_info(self) -> dict:
        """현재 회차 정보 조회 (roundRemainTime.do)"""
        resp = await self.client.session.get(
            f"{EL_BASE_URL}/roundRemainTime.do"
        )
        return await resp.json()

    async def async_get_balance(self) -> DhPension720BalanceData:
        """잔액 조회 (selectCrntEntrsAmt.do)"""
        await self._ensure_session()
        t = int(time.time() * 1000)
        resp = await self.client.session.get(
            f"{EL_BASE_URL}/selectCrntEntrsAmt.do?_={t}"
        )
        result = await resp.json()
        return DhPension720BalanceData(
            deposit=result.get("totBuyAmt", 0),
            purchase_available=result.get("crntEntrsAmt", 0),
        )

    # ------------------------------------------------------------------
    # Purchase
    # ------------------------------------------------------------------

    async def async_buy_1(self) -> DhPension720BuyData:
        """1조 자동 1장 구매"""
        return await self._async_buy(groups=[1])

    async def async_buy_5(self) -> DhPension720BuyData:
        """모든 조 자동 5장 구매"""
        return await self._async_buy(groups=[1, 2, 3, 4, 5])

    async def _async_buy(self, groups: List[int]) -> DhPension720BuyData:
        """
        연금복권 720+ 자동 구매

        Flow:
          0. roundRemainTime.do  → 현재 회차 / 잔여시간
          1. makeOrderNo.do      → 주문번호 생성 (encrypted)
          2. connPro.do          → 구매 실행   (encrypted)
          3. checkDeposit.do     → 잔액 확인   (encrypted)
        """
        await self._ensure_session()
        ticket_count = len(groups)

        # ── Step 0: 회차 확인 ─────────────────────────
        round_info = await self.async_get_round_info()
        current_round = round_info.get("round", 0)
        if not current_round:
            raise DhPension720PurchaseError("회차 정보를 가져올 수 없습니다")
        remain = round_info.get("remainTime", 0)
        if remain <= 0:
            raise DhPension720PurchaseError("판매 마감되었습니다")

        _LOGGER.info(
            f"[PURCHASE] round={current_round}, remainTime={remain}, "
            f"groups={groups}"
        )

        # ── frmauto 공통 serialize ────────────────────
        frmauto = urlencode([
            ("ROUND", current_round),
            ("SEL_NO", ""),
            ("BUY_CNT", ""),
            ("AUTO_SEL_SET", ""),
            ("SEL_CLASS", ""),
            ("BUY_TYPE", "A"),
            ("ACCS_TYPE", "01"),
        ])

        # ── Step 1: makeOrderNo.do ────────────────────
        resp1 = await self.client.session.post(
            f"{EL_BASE_URL}/makeOrderNo.do",
            data={"q": self._enc(frmauto)},
        )
        r1 = await resp1.json()
        if "q" not in r1:
            raise DhPension720PurchaseError(f"makeOrderNo 응답 오류: {r1}")

        p1 = self._parse(self._dec(r1["q"]))
        order_no = p1.get("orderNo", "")
        if not order_no:
            raise DhPension720PurchaseError("주문번호 생성 실패")
        _LOGGER.info(f"[PURCHASE] orderNo={order_no}")

        # ── Step 2: connPro.do ────────────────────────
        buy_nos = [f"{g}000000" for g in groups]
        buy_set_types = ["SA"] * ticket_count

        frm = urlencode([
            ("ROUND", current_round),
            ("FLAG", ""),
            ("BUY_KIND", "01"),
            ("BUY_NO", ",".join(buy_nos)),
            ("BUY_CNT", ticket_count),
            ("BUY_SET_TYPE", ",".join(buy_set_types)),
            ("BUY_TYPE", "A"),
            ("ACCS_TYPE", "01"),
            ("orderNo", order_no),
            ("orderDate", p1.get("orderDate", "")),
            ("TRANSACTION_ID", ""),
            ("WIN_DATE", ""),
            ("USER_ID", self.client.username),
            ("PAY_TYPE", ""),
            ("resultErrorCode", ""),
            ("resultErrorMsg", ""),
            ("resultOrderNo", ""),
            ("WORKING_FLAG", "false"),
            ("NUM_CHANGE_TYPE", ""),
            ("auto_process", ""),
            ("set_type", "SA"),
            ("classnum", ""),
            ("selnum", ""),
            ("buytype", "A"),
            ("num1", ""),
            ("num2", ""),
            ("num3", ""),
            ("num4", ""),
            ("num5", ""),
            ("num6", ""),
            ("DSEC", "0"),
            ("CLOSE_DATE", ""),
            ("verifyYN", "N"),
            ("curdeposit", "0"),
            ("curpay", "0"),
        ])

        resp2 = await self.client.session.post(
            f"{EL_BASE_URL}/connPro.do",
            data={"q": self._enc(frm)},
        )
        r2 = await resp2.json()
        if "q" not in r2:
            raise DhPension720PurchaseError(f"connPro 응답 오류: {r2}")

        p2 = self._parse(self._dec(r2["q"]))
        result_code = p2.get("resultCode", "")
        sale_cnt = int(p2.get("saleCnt", "0"))
        sale_ticket = p2.get("saleTicket", "")
        fail_cnt = int(p2.get("failCnt", "0"))
        fail_ticket = p2.get("failTicket", "")

        _LOGGER.info(
            f"[PURCHASE] resultCode={result_code}, "
            f"saleCnt={sale_cnt}, failCnt={fail_cnt}"
        )

        if result_code == "120":
            raise DhPension720PurchaseError(f"구매 전체 실패: {fail_ticket}")
        if result_code not in ("100", "110"):
            raise DhPension720PurchaseError(
                f"구매 실패 (code={result_code})"
            )
        if result_code == "110":
            _LOGGER.warning(
                f"[PURCHASE] 일부 실패: {fail_cnt}건 - {fail_ticket}"
            )

        # ── Step 3: checkDeposit.do ───────────────────
        deposit = 0
        try:
            resp3 = await self.client.session.post(
                f"{EL_BASE_URL}/checkDeposit.do",
                data={"q": self._enc(frmauto)},
            )
            r3 = await resp3.json()
            if "q" in r3:
                p3 = self._parse(self._dec(r3["q"]))
                deposit = int(p3.get("deposit", "0"))
        except Exception as e:
            _LOGGER.warning(f"[PURCHASE] checkDeposit 오류 (무시): {e}")

        return DhPension720BuyData(
            round_no=current_round,
            ticket_count=sale_cnt,
            tickets=sale_ticket,
            fail_count=fail_cnt,
            fail_tickets=fail_ticket,
            deposit=deposit,
            amount=sale_cnt * 1000,
        )

    # ------------------------------------------------------------------
    # History (www.dhlottery.co.kr 경유)
    # ------------------------------------------------------------------

    async def async_get_buy_history(self) -> List[DhPension720BuyHistoryData]:
        """구매 이력 조회"""
        try:
            items = await self.client.async_get_buy_list("P720")
            return [
                DhPension720BuyHistoryData(
                    round_no=item.get("round", 0),
                    issue_dt=item.get("issueDt", ""),
                    barcode=item.get("barcode", ""),
                    ticket_count=item.get("ticketCount", 0),
                    amount=item.get("amount", 0),
                    result=item.get("result", "미추첨"),
                )
                for item in items
            ]
        except Exception as e:
            _LOGGER.error(f"구매 이력 조회 오류: {e}")
            raise DhPension720Error(f"구매 이력 조회 실패: {e}")
