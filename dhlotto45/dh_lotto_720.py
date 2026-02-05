"""
Pension Lottery 720+ Module
Support for Korean pension lottery (annuity lottery)
"""

import logging
import datetime
from dataclasses import dataclass
from typing import Optional, List
from dh_lottery_client import DhLotteryClient, DhLotteryError

_LOGGER = logging.getLogger(__name__)


class DhLotto720Error(DhLotteryError):
    """Pension Lottery 720+ exception class"""


@dataclass
class Lotto720WinningData:
    """Pension lottery 720+ winning data"""
    round_no: int  # Round number
    draw_date: str  # Draw date
    # 1st prize info
    first_prize_number: str  # 1st prize number (7 digits: group + 6 digits)
    first_prize_amount: int  # 1st prize amount (monthly pension)
    # Bonus number
    bonus_number: Optional[str] = None


@dataclass
class Lotto720BuyData:
    """Pension lottery 720+ purchase result"""
    round_no: int
    barcode: str
    issue_dt: str
    numbers: List[str]  # List of 7-digit numbers purchased


@dataclass
class Lotto720BuyHistoryData:
    """Pension lottery 720+ purchase history"""
    round_no: int
    barcode: str
    result: str
    numbers: List[str]  # List of 7-digit numbers


class DhLotto720:
    """Pension Lottery 720+ class"""
    
    def __init__(self, client: DhLotteryClient):
        """Initialize DhLotto720 class"""
        self.client = client
    
    async def async_get_round_info(self, round_no: Optional[int] = None) -> Lotto720WinningData:
        """
        Get pension lottery round information
        
        Args:
            round_no: Round number (None for latest)
            
        Returns:
            Lotto720WinningData object
        """
        params = {
            "_": int(datetime.datetime.now().timestamp() * 1000),
        }
        if round_no:
            params["srchLtEpsd"] = round_no
        
        try:
            data = await self.client.async_get('lt720/selectPstLt720Info.do', params)
            items = data.get('list', [])
            
            if not items or len(items) == 0:
                raise DhLotto720Error(f"Failed to get round info (round: {round_no})")
            
            item = items[0]
            
            # Extract winning number (format: group + 6 digits, e.g., "1234567")
            # The API returns winning number in format like "ltNo1WnNo"
            group = item.get("ltNo1WnNo", "")  # Group number (1 digit)
            win_no = item.get("tm1WnNo", "")   # Winning 6 digits
            
            # Combine to 7-digit string
            first_prize_number = f"{group}{win_no}"
            
            # Get prize amount (monthly pension)
            # Pension lottery pays monthly for 20 years
            first_prize_amount = 700  # 7 million won per month (default)
            
            # Try to get from API if available
            if "tm1PrzAmt" in item:
                first_prize_amount = item.get("tm1PrzAmt", 700)
            
            return Lotto720WinningData(
                round_no=item.get('ltEpsd'),
                draw_date=item.get("ltRflYmd", ""),
                first_prize_number=first_prize_number,
                first_prize_amount=first_prize_amount,
                bonus_number=item.get("bnsWnNo"),
            )
        
        except Exception as ex:
            raise DhLotto720Error(f"Failed to get pension lottery info: {ex}") from ex
    
    async def async_get_latest_round_no(self) -> int:
        """Get latest round number"""
        latest_round = await self.async_get_round_info()
        return latest_round.round_no
    
    async def async_buy(self, count: int = 1) -> Lotto720BuyData:
        """
        Purchase pension lottery 720+ tickets
        
        Args:
            count: Number of tickets to purchase (1-5)
            
        Returns:
            Lotto720BuyData object with purchase details
            
        Notes:
            - Thursday 17:00-22:00: Sales closed
            - Maximum 5 tickets per week
            - Automatic number generation only (no manual selection)
        """
        
        _LOGGER.info(f"Purchasing {count} pension lottery ticket(s)...")
        
        def _check_buy_time() -> None:
            """Check if purchase is allowed at current time"""
            now = datetime.datetime.now()
            
            # Cannot purchase before 6 AM
            if now.hour < 6:
                raise DhLotto720Error(
                    "Purchase not available. (Available: 6 AM - 5 PM Thursday)"
                )
            
            # Thursday 17:00-22:00: Sales closed
            if now.weekday() == 3:  # Thursday
                if 17 <= now.hour < 22:
                    raise DhLotto720Error(
                        "Purchase not available. Thursday 5 PM - 10 PM sales are closed. "
                        "(Drawing at 7 PM, sales resume at 10 PM)"
                    )
        
        def _check_item_count() -> None:
            """Validate purchase count"""
            if count < 1:
                raise DhLotto720Error("At least 1 ticket required")
            if count > 5:
                raise DhLotto720Error("Maximum 5 tickets allowed")
        
        async def _check_weekly_limit() -> int:
            """Check weekly purchase limit"""
            history_items = await self.client.async_get_buy_list('LT40')  # LT40 = Pension 720+
            this_week_buy_count = sum(
                [
                    item.get("prchsQty", 0)
                    for item in history_items
                    if item.get("ltWnResult") == "미추첨"
                ]
            )
            if this_week_buy_count >= 5:
                raise DhLotto720Error("Weekly purchase limit reached (5 tickets)")
            return this_week_buy_count
        
        async def _check_balance() -> None:
            """Check if balance is sufficient"""
            balance = await self.client.async_get_balance()
            required_amount = buy_count * 1000
            if required_amount > balance.purchase_available:
                raise DhLotto720Error(
                    f"Insufficient balance. (Balance: {balance.purchase_available:,} KRW)"
                )
            _LOGGER.info(f"Buy count: {buy_count}, required: {required_amount:,}/{balance.purchase_available:,}")
        
        async def get_user_ready_socket() -> str:
            """Get user ready socket IP"""
            resp = await self.client.session.post(
                url="https://ol.dhlottery.co.kr/olotto/game/egovUserReadySocket.json"
            )
            import json
            return json.loads(await resp.text())["ready_ip"]
        
        def parse_result(result: dict) -> Lotto720BuyData:
            """Parse purchase result"""
            # Extract purchased numbers from result
            numbers = []
            if "arrGameChoiceNum" in result:
                for item in result["arrGameChoiceNum"]:
                    # Format: "A|1234567|0" -> extract 1234567
                    parts = item.split("|")
                    if len(parts) >= 2:
                        numbers.append(parts[1])
            
            return Lotto720BuyData(
                round_no=int(result["buyRound"]),
                issue_dt=f'{result["issueDay"]} {result.get("weekDay", "")} {result["issueTime"]}',
                barcode=f'{result["barCode1"]} {result["barCode2"]} {result["barCode3"]} '
                        f'{result["barCode4"]} {result["barCode5"]} {result["barCode6"]}',
                numbers=numbers,
            )
        
        try:
            # Validate purchase
            _check_buy_time()
            _check_item_count()
            this_week_buy_count = await _check_weekly_limit()
            available_count = 5 - this_week_buy_count
            buy_count = min(count, available_count)
            await _check_balance()
            
            # Get current round
            live_round = str(await self.async_get_latest_round_no() + 1)
            
            # Get socket
            direct = await get_user_ready_socket()
            
            # Prepare purchase data
            # Pension lottery uses automatic generation only (mode=0)
            import json
            param = json.dumps([
                {
                    "genType": "0",  # 0 = Auto (연금복권은 자동만 가능)
                    "arrGameChoiceNum": None,
                    "alpabet": "ABCDE"[i],
                }
                for i in range(buy_count)
            ])
            
            _LOGGER.info(f"Executing pension lottery purchase: {buy_count} ticket(s), round {live_round}")
            
            # Execute purchase
            resp = await self.client.session.post(
                url="https://ol.dhlottery.co.kr/olotto/game/execBuy.do",
                data={
                    "round": live_round,
                    "direct": direct,
                    "nBuyAmount": str(1000 * buy_count),
                    "param": param,
                    "gameCnt": buy_count,
                    "saleMdaDcd": "10",  # 10 = online purchase
                },
                timeout=10,
            )
            
            response = await resp.json()
            
            if response["result"]["resultCode"] != "100":
                raise DhLotto720Error(
                    f"Purchase failed. (Message: {response['result']['resultMsg']})"
                )
            
            _LOGGER.info("Pension lottery purchase successful!")
            return parse_result(response["result"])
        
        except DhLotto720Error:
            raise
        except Exception as ex:
            raise DhLotto720Error(f"Purchase failed: {ex}") from ex
    
    async def async_get_buy_history_this_week(self) -> List[Lotto720BuyHistoryData]:
        """Get pension lottery purchase history from last week"""
        
        async def async_get_receipt(order_no: str, barcode: str) -> List[str]:
            """Get receipt details (purchased numbers)"""
            resp = await self.client.async_get_with_login(
                'mypage/lotto720TicketDetail.do',
                params={
                    "ntslOrdrNo": order_no,
                    "barcd": barcode,
                    "_": int(datetime.datetime.now().timestamp() * 1000)
                },
            )
            ticket = resp.get("ticket")
            game_dtl = ticket.get("game_dtl") if ticket else []
            
            numbers = []
            for game in game_dtl:
                # Extract 7-digit number
                num = game.get("num", [])
                if num:
                    # Format: list of digits -> "1234567"
                    numbers.append("".join(map(str, num)))
            
            return numbers
        
        try:
            results = await self.client.async_get_buy_list("LT40")  # LT40 = Pension 720+
            items: List[Lotto720BuyHistoryData] = []
            
            for result in results:
                order_no = result.get("ntslOrdrNo")
                barcode = result.get("gmInfo")
                
                items.append(
                    Lotto720BuyHistoryData(
                        round_no=result.get("ltEpsd"),
                        barcode=barcode,
                        result=result.get("ltWnResult"),
                        numbers=await async_get_receipt(order_no, barcode),
                    )
                )
                
                if len(items) >= 5:  # Limit to recent 5 purchases
                    break
            
            return items
        
        except Exception as ex:
            raise DhLotto720Error(
                "Failed to get purchase history"
            ) from ex
