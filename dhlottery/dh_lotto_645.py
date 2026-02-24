import datetime
import json
import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import List, Dict, Optional


from dh_lottery_client import DhLotteryClient, DhLotteryError

_LOGGER = logging.getLogger(__name__)


class DhLotto645Error(DhLotteryError):
    """DH Lotto 645 exception class."""


class DhLotto645SelMode(StrEnum):
    """Lottery purchase mode enumeration."""

    AUTO = "auto"
    MANUAL = "manual"
    SEMI_AUTO = "semi_auto"

    @staticmethod
    def value_of(value: str) -> "DhLotto645SelMode":
        """Convert value to lottery purchase mode."""
        if value == "1":
            return DhLotto645SelMode.MANUAL
        if value == "2":
            return DhLotto645SelMode.SEMI_AUTO
        if value == "3":
            return DhLotto645SelMode.AUTO
        raise ValueError(f"Invalid value: {value}")

    def to_value(self) -> str:
        """Convert lottery purchase mode to value."""
        if self == DhLotto645SelMode.AUTO:
            return "0"
        if self == DhLotto645SelMode.MANUAL:
            return "1"
        if self == DhLotto645SelMode.SEMI_AUTO:
            return "2"
        raise ValueError(f"Invalid value: {self}")

    @staticmethod
    def value_of_text(text: str) -> "DhLotto645SelMode":
        """Convert text to lottery purchase mode."""
        # Korean text mappings
        if "반자동" in text or "semi" in text.lower():
            return DhLotto645SelMode.SEMI_AUTO
        if "자동" in text or "auto" in text.lower():
            return DhLotto645SelMode.AUTO
        if "수동" in text or "manual" in text.lower():
            return DhLotto645SelMode.MANUAL
        raise ValueError(f"Invalid text: {text}")

    def __str__(self):
        """Convert lottery purchase mode to Korean string."""
        if self == DhLotto645SelMode.AUTO:
            return "자동"
        if self == DhLotto645SelMode.MANUAL:
            return "수동"
        if self == DhLotto645SelMode.SEMI_AUTO:
            return "반자동"
        raise ValueError(f"Invalid value: {self}")


class DhLotto645:
    """DH Lottery Lotto 6/45 purchase class."""

    @dataclass
    class WinningData:
        """Lottery winning information data class."""

        round_no: int
        numbers: List[int]
        bonus_num: int
        draw_date: str

    @dataclass
    class Slot:
        """Lottery slot information data class."""

        mode: DhLotto645SelMode = DhLotto645SelMode.AUTO
        numbers: List[int] = field(default_factory=lambda: [])

    @dataclass(order=True)
    class Game:
        """Lottery game information data class."""

        slot: str
        mode: DhLotto645SelMode = DhLotto645SelMode.AUTO
        numbers: List[int] = field(default_factory=lambda: [])

    @dataclass
    class BuyData:
        """Lottery purchase result data class."""

        round_no: int
        barcode: str
        issue_dt: str
        games: List["DhLotto645.Game"] = field(default_factory=lambda: [])

        def to_dict(self) -> Dict:
            """Convert data to dictionary format."""
            return {
                "round_no": self.round_no,
                "barcode": self.barcode,
                "issue_dt": self.issue_dt,
                "games": [game.__dict__ for game in self.games],
            }

    @dataclass
    class BuyHistoryData:
        """Lottery purchase history data class."""

        round_no: int
        barcode: str
        result: str
        games: List["DhLotto645.Game"] = field(default_factory=lambda: [])

    def __init__(self, client: DhLotteryClient):
        """Initialize DhLotto645 class."""
        self.client = client

    async def async_get_round_info(self, round_no: Optional[int] = None) -> WinningData:
        """Get specific round lottery information."""
        params = {
            "_": int(datetime.datetime.now().timestamp() * 1000),
        }
        if round_no:
            params["srchLtEpsd"] = round_no
        data = await self.client.async_get('lt645/selectPstLt645Info.do', params)
        items = data.get('list', [])

        if not items or len(items) == 0:
            raise DhLotto645Error(f"Failed to query round information. (round: {round_no})")
        item = items[0]

        return DhLotto645.WinningData(
            round_no=item.get('ltEpsd'),
            numbers=[
                item.get("tm1WnNo"),
                item.get("tm2WnNo"),
                item.get("tm3WnNo"),
                item.get("tm4WnNo"),
                item.get("tm5WnNo"),
                item.get("tm6WnNo"),
            ],
            bonus_num=item.get("bnsWnNo"),
            draw_date=item.get("ltRflYmd"),
        )

    async def async_get_latest_round_no(self) -> int:
        """Get latest lottery round number."""
        latest_round = await self.async_get_round_info()
        return latest_round.round_no

    async def async_buy(self, items: List[Slot], max_games: Optional[int] = None) -> BuyData:
        """
        Purchase lottery tickets.
        example: {"loginYn":"Y","result":{"oltInetUserId":"006094875","issueTime":"17:55:27","issueDay":"2024/05/28",
        "resultCode":"100","barCode4":"63917","barCode5":"56431","barCode6":"42167","barCode1":"59865","barCode2":"36399",
        "resultMsg":"SUCCESS","barCode3":"04155","buyRound":"1122","arrGameChoiceNum":["A|09|12|30|33|35|433"],
        "weekDay":"","payLimitDate":null,"drawDate":null,"nBuyAmount":1000}}
        """

        _LOGGER.debug(f"Buy Lotto, items: {items}")

        def deduplicate_numbers(_items: List["DhLotto645.Slot"]) -> None:
            """Remove duplicates from purchase numbers."""
            for _item in _items:
                _item.numbers = list(set(_item.numbers))

        async def _verify_and_get_buy_count(_items: List["DhLotto645.Slot"]) -> int:
            """Verify if purchase is possible and return purchasable count."""

            def _check_buy_time() -> None:
                """Check if purchase time is valid."""
                _now = datetime.datetime.now()
                if _now.hour < 6:
                    raise DhLotto645Error(
                        "[ERROR] Purchase time not available. (Purchase available from 6:00 to 24:00)"
                    )
                if _now.weekday() == 5 and _now.hour > 20:
                    raise DhLotto645Error(
                        "[ERROR] Purchase time not available. (Saturday purchase until 20:00, Sunday from 6:00)"
                    )

            def _check_item_count() -> None:
                """Check purchase information item count."""
                if len(_items) == 0:
                    raise DhLotto645Error("[ERROR] No purchase numbers provided.")
                if len(_items) > 5:
                    raise DhLotto645Error("[ERROR] Maximum 5 games can be purchased.")
                for _idx, _item in enumerate(_items):
                    if (
                        _item.mode == DhLotto645SelMode.MANUAL
                        and len(_item.numbers) > 6
                    ):
                        raise DhLotto645Error(
                            f"[ERROR] Game {_idx + 1}: Maximum 6 numbers allowed."
                        )

            async def _async_check_weekly_limit() -> int:
                """Check weekly purchase limit."""
                _history_items = await self.client.async_get_buy_list('LO40')
                __this_week_buy_count = sum(
                    [
                        _item.get("prchsQty", 0)
                        for _item in _history_items
                        if _item.get("ltWnResult") == "미추첨"
                    ]
                )
                if __this_week_buy_count >= 5:
                    raise DhLotto645Error("[ERROR] 주간 구매 한도(5게임)에 도달했습니다. 다음 주에 다시 구매해주세요.")
                return __this_week_buy_count

            async def _async_check_balance() -> None:
                """Check if balance is sufficient."""
                if _buy_count * 1000 > _balance.purchase_available:
                    raise DhLotto645Error(
                        f"[ERROR] Insufficient balance. (Balance: {_balance.purchase_available})"
                    )
                _LOGGER.debug(
                    f"Buy count: {_buy_count}, deposit: {_buy_count * 1000}/{_balance.purchase_available}"
                )

            _check_buy_time()
            _check_item_count()
            _this_week_buy_count = await _async_check_weekly_limit()
            _available_count = 5 - _this_week_buy_count
            _LOGGER.debug(f"Available count: {_available_count}")

            _balance = await self.client.async_get_balance()
            _buy_count = min(len(items), _available_count)
            if max_games is not None:
                _buy_count = min(_buy_count, max_games)  # 수동 1게임 등 최대 장수 제한
            await _async_check_balance()
            return _buy_count

        async def get_user_ready_socket() -> str:
            """Get user ready socket."""
            _resp = await self.client.session.post(
                url="https://ol.dhlottery.co.kr/olotto/game/egovUserReadySocket.json"
            )
            return json.loads(await _resp.text())["ready_ip"]

        def make_param(tickets: List["DhLotto645.Slot"]) -> str:
            """Create lottery purchase information."""
            return json.dumps(
                [
                    {
                        "genType": t.mode.to_value(),
                        "arrGameChoiceNum": (
                            None
                            if t.mode == DhLotto645SelMode.AUTO
                            else ",".join(map(str, sorted(t.numbers)))
                        ),
                        "alpabet": "ABCDE"[i],
                    }
                    for i, t in enumerate(tickets)
                ]
            )

        def parse_result(result: Dict) -> DhLotto645.BuyData:
            """Parse purchase result.
            example: ["A|01|02|04|27|39|443", "B|11|23|25|27|28|452"]
            """
            return DhLotto645.BuyData(
                round_no=int(result["buyRound"]),
                issue_dt=f'{result["issueDay"]} {result["weekDay"]} {result["issueTime"]}',
                barcode=f'{result["barCode1"]} {result["barCode2"]} {result["barCode3"]} '
                f'{result["barCode4"]} {result["barCode5"]} {result["barCode6"]}',
                games=[
                    DhLotto645.Game(
                        slot=_item[0],
                        mode=DhLotto645SelMode.value_of(_item[-1]),
                        numbers=[int(x) for x in _item[2:-1].split("|")],
                    )
                    for _item in result["arrGameChoiceNum"]
                ],
            )

        try:
            _LOGGER.info(f"[PURCHASE] Before deduplicate - items: {[(item.mode, item.numbers) for item in items]}")
            deduplicate_numbers(items)
            _LOGGER.info(f"[PURCHASE] After deduplicate - items: {[(item.mode, item.numbers) for item in items]}")
            buy_count = await _verify_and_get_buy_count(items)
            buy_items = items[:buy_count]
            live_round = str(await self.async_get_latest_round_no() + 1)
            direct = (await get_user_ready_socket())
            param = make_param(buy_items)
            _LOGGER.info(f"[PURCHASE] Sending to server - param: {param}")
            _LOGGER.info(f"[PURCHASE] buy_items before param: {[(item.mode, item.numbers) for item in buy_items]}")
            resp = await self.client.session.post(
                url="https://ol.dhlottery.co.kr/olotto/game/execBuy.do",
                data={
                    "round": live_round,
                    "direct": direct,
                    "nBuyAmount": str(1000 * len(buy_items)),
                    "param": param,
                    "gameCnt": len(buy_items),
                    "saleMdaDcd": "10",
                },
                timeout=10,
            )
            response = await resp.json()
            if response["result"]["resultCode"] != "100":
                raise DhLotto645Error(
                    f"[ERROR] 6/45 purchase failed. (Reason: {response['result']['resultMsg']})"
                )
            return parse_result(response["result"])
        except DhLotteryError:
            raise
        except Exception as ex:
            raise DhLotto645Error(
                f"[ERROR] 6/45 purchase failed. (Reason: {str(ex)})"
            ) from ex

    async def async_get_buy_history_this_week(self) -> list[BuyHistoryData]:
        """Query purchase history for the last week."""

        async def async_get_receipt(
            _order_no: str, _barcode: str
        ) -> List[DhLotto645.Game]:
            """Get receipt."""
            _resp = await self.client.async_get_with_login('mypage/lotto645TicketDetail.do',
                params={"ntslOrdrNo": _order_no, "barcd": _barcode, "_": int(datetime.datetime.now().timestamp() * 1000)},
            )
            ticket = _resp.get("ticket")
            game_dtl = ticket.get("game_dtl") if ticket else []
            _slots: List[DhLotto645.Game] = []
            for game in game_dtl:
                _slots.append(
                    DhLotto645.Game(
                        slot=game.get("idx"),
                        mode=DhLotto645SelMode.value_of(str(game.get("type", 3))),
                        numbers=game.get("num", []),
                    )
                )
            return _slots

        try:
            results = await self.client.async_get_buy_list("LO40")
            items: List[DhLotto645.BuyHistoryData] = []
            for result in results:
                order_no = result.get("ntslOrdrNo")
                barcode = result.get("gmInfo")
                items.append(
                    DhLotto645.BuyHistoryData(
                        round_no=result.get("ltEpsd"),
                        barcode=barcode,
                        result=result.get("ltWnResult"),
                        games=await async_get_receipt(order_no, barcode),
                    )
                )
                if sum([len(item.games) for item in items]) >= 5:
                    break
            return items
        except Exception as ex:
            raise DhLotteryError(
                "[ERROR] Failed to query recent purchase history."
            ) from ex
