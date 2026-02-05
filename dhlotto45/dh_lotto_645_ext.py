"""
Lotto 6/45 Public API Extension
Provides winning details using public API
"""

import logging
from dataclasses import dataclass
from typing import Optional
import aiohttp

_LOGGER = logging.getLogger(__name__)

PUBLIC_API_URL = "https://www.dhlottery.co.kr/common.do"


@dataclass
class Lotto645WinningDetails:
    """Lotto 6/45 winning details from public API"""
    round_no: int
    draw_date: str
    # Winning numbers
    numbers: list[int]
    bonus_num: int
    # Sales
    total_sales: int  # Total sales amount (totSellamnt)
    # 1st prize
    first_prize_amount: int  # 1st prize per winner (firstWinamnt)
    first_prize_winners: int  # Number of 1st prize winners (firstPrzwnerCo)
    first_prize_total: int  # Total 1st prize amount (firstAccumamnt)
    # Additional prizes (if available in response)
    second_prize_amount: Optional[int] = None
    second_prize_winners: Optional[int] = None
    third_prize_amount: Optional[int] = None
    third_prize_winners: Optional[int] = None
    fourth_prize_amount: Optional[int] = None
    fourth_prize_winners: Optional[int] = None
    fifth_prize_amount: Optional[int] = None
    fifth_prize_winners: Optional[int] = None


async def get_lotto645_winning_details(round_no: Optional[int] = None) -> Lotto645WinningDetails:
    """
    Get Lotto 6/45 winning details from public API
    
    Args:
        round_no: Round number (None for latest)
        
    Returns:
        Lotto645WinningDetails object
        
    Example response:
    {
        "totSellamnt": 111840714000,
        "returnValue": "success",
        "drwNoDate": "2024-05-11",
        "firstWinamnt": 1396028764,
        "firstPrzwnerCo": 19,
        "firstAccumamnt": 26524546516,
        "drwNo": 1119,
        "drwtNo1": 1, "drwtNo2": 9, "drwtNo3": 12,
        "drwtNo4": 13, "drwtNo5": 20, "drwtNo6": 45,
        "bnusNo": 3
    }
    """
    params = {"method": "getLottoNumber"}
    if round_no:
        params["drwNo"] = round_no
    
    try:
        # Use comprehensive headers to avoid bot detection
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.dhlottery.co.kr/gameResult.do?method=byWin",
            "X-Requested-With": "XMLHttpRequest",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }
        
        timeout = aiohttp.ClientTimeout(total=10)
        connector = aiohttp.TCPConnector(ssl=False)
        
        async with aiohttp.ClientSession(connector=connector, headers=headers, timeout=timeout) as session:
            async with session.get(PUBLIC_API_URL, params=params, allow_redirects=True) as resp:
                if resp.status != 200:
                    raise Exception(f"API request failed: {resp.status}")
                
                # Try to parse as JSON
                try:
                    data = await resp.json()
                except Exception:
                    # API returned non-JSON (probably HTML redirect or blocking)
                    raise Exception(f"API returned non-JSON response (status: {resp.status})")
                
                if data.get("returnValue") != "success":
                    raise Exception(f"API error: {data.get('returnValue', 'unknown')}")
                
                # Parse response
                return Lotto645WinningDetails(
                    round_no=data["drwNo"],
                    draw_date=data["drwNoDate"],
                    numbers=[
                        data["drwtNo1"],
                        data["drwtNo2"],
                        data["drwtNo3"],
                        data["drwtNo4"],
                        data["drwtNo5"],
                        data["drwtNo6"],
                    ],
                    bonus_num=data["bnusNo"],
                    total_sales=data["totSellamnt"],
                    first_prize_amount=data["firstWinamnt"],
                    first_prize_winners=data["firstPrzwnerCo"],
                    first_prize_total=data["firstAccumamnt"],
                )
    
    except Exception as ex:
        _LOGGER.error(f"Failed to get lotto645 winning details: {ex}")
        raise
