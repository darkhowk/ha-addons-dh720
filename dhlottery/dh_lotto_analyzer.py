"""동행복권 로또 analysis 및 통계 모듈"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Optional
from collections import Counter

from dh_lottery_client import DhLotteryClient, DhLotteryError
from dh_lotto_645 import DhLotto645

_LOGGER = logging.getLogger(__name__)


class DhLottoAnalyzerError(DhLotteryError):
    """로또 analysis 예외 클래스입니다."""


@dataclass
class NumberFrequency:
    """number별 출현 빈도 데터"""
    number: int
    count: int
    percentage: float


@dataclass
class PurchaseStatistics:
    """purchase 통계 데터"""
    total_purchase_count: int  # 총 purchase 횟수
    total_purchase_amount: int  # 총 purchase 금액
    total_winning_count: int  # 총 winning 횟수
    total_winning_amount: int  # 총 winning 금액
    win_rate: float  # winning률
    roi: float  # 수익률 (return on investment)
    rank_distribution: Dict[int, int]  # 등수별 winning 횟수


@dataclass
class HotColdNumbers:
    """Hot & Cold number analysis"""
    hot_numbers: List[int]  # recent 자주 나온 number (상위 10개)
    cold_numbers: List[int]  # recent 잘 안 나온 number (하위 10개)
    most_frequent: List[NumberFrequency]  # 전체 기간 최다 출현 number


class DhLottoAnalyzer:
    """동행복권 로또 analysis 클래스"""

    def __init__(self, client: DhLotteryClient):
        """DhLottoAnalyzer 클래스 초기화합니다."""
        self.client = client
        self.lotto_645 = DhLotto645(client)

    async def async_analyze_number_frequency(
        self, recent_rounds: int = 50
    ) -> List[NumberFrequency]:
        """
        recent Nround winningnumber analysis하여 number별 출현 빈도 계산합니다.
        
        Args:
            recent_rounds: analysis할 recent round 수 (기본 50회)
            
        Returns:
            number별 출현 빈도 리스트 (출현 횟수 내림차순)
        """
        try:
            # 최신 round number query
            latest_round_no = await self.lotto_645.async_get_latest_round_no()
            
            # number 수집
            all_numbers = []
            for round_no in range(
                max(1, latest_round_no - recent_rounds + 1), latest_round_no + 1
            ):
                try:
                    winning_data = await self.lotto_645.async_get_round_info(round_no)
                    all_numbers.extend(winning_data.numbers)
                    # 보너스 number는 제외
                except Exception as ex:
                    _LOGGER.warning(f"round {round_no} query failed: {ex}")
                    continue

            # 빈도 계산
            total_draws = len(all_numbers) / 6  # 총 추첨 횟수
            number_counts = Counter(all_numbers)
            
            frequencies = []
            for number in range(1, 46):
                count = number_counts.get(number, 0)
                percentage = (count / total_draws * 100) if total_draws > 0 else 0
                frequencies.append(
                    NumberFrequency(
                        number=number, count=count, percentage=round(percentage, 2)
                    )
                )
            
            # 출현 횟수로 내림차순 정렬
            frequencies.sort(key=lambda x: x.count, reverse=True)
            return frequencies

        except Exception as ex:
            raise DhLottoAnalyzerError(f"number  analysis failed: {ex}") from ex

    async def async_get_hot_cold_numbers(
        self, recent_rounds: int = 20
    ) -> HotColdNumbers:
        """
        Hot & Cold number analysis합니다.
        
        Args:
            recent_rounds: recent analysis round (기본 20회)
            
        Returns:
            Hot & Cold number analysis 결과
        """
        try:
            # 전체 빈도 analysis (50round)
            all_frequency = await self.async_analyze_number_frequency(50)
            
            # recent 빈도 analysis
            recent_frequency = await self.async_analyze_number_frequency(recent_rounds)
            
            # Hot numbers (recent 자주 나온 상위 10개)
            hot_numbers = [f.number for f in recent_frequency[:10]]
            
            # Cold numbers (recent 안 나온 하위 10개)
            cold_numbers = [f.number for f in recent_frequency[-10:]]
            
            # 전체 기간 최다 출현 number (상위 10개)
            most_frequent = all_frequency[:10]
            
            return HotColdNumbers(
                hot_numbers=hot_numbers,
                cold_numbers=cold_numbers,
                most_frequent=most_frequent,
            )

        except Exception as ex:
            raise DhLottoAnalyzerError(f"Hot/Cold number analysis failed: {ex}") from ex

    async def async_get_purchase_statistics(
        self, days: int = 365
    ) -> PurchaseStatistics:
        """
        사용자 purchase 통계 analysis합니다.
        
        Args:
            days: analysis할 기간 (기본 365일)
            
        Returns:
            purchase 통계 데터
        """
        try:
            import datetime

            # purchase history query
            end_date = datetime.datetime.now()
            start_date = end_date - datetime.timedelta(days=days)
            
            result = await self.client.async_get_with_login(
                "mypage/selectMyLotteryledger.do",
                params={
                    "srchStrDt": start_date.strftime("%Y%m%d"),
                    "srchEndDt": end_date.strftime("%Y%m%d"),
                    "ltGdsCd": "LO40",  #  6/45
                    "pageNum": 1,
                    "recordCountPerPage": 1000,
                    "_": int(datetime.datetime.now().timestamp() * 1000),
                },
            )
            
            # Handle case where result is None or empty
            if result is None:
                result = {}
            
            items = result.get("list", [])
            
            # 통계 계산
            total_purchase_count = 0
            total_winning_count = 0
            total_winning_amount = 0
            rank_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            
            for item in items:
                # None 값 명시적으로 0으로 변환
                quantity = item.get("prchsQty") or 0
                if not isinstance(quantity, int):
                    quantity = 0
                total_purchase_count += quantity
                
                # None 값 명시적으로 0으로 변환
                winning_amount = item.get("ltWnAmt") or 0
                if not isinstance(winning_amount, int):
                    winning_amount = 0
                    
                if winning_amount > 0:
                    total_winning_count += 1
                    total_winning_amount += winning_amount
                    
                    # 등수 파악 (금액 기준 추정)
                    if winning_amount >= 1000000000:  # 1등: 10억 상
                        rank_distribution[1] += 1
                    elif winning_amount >= 10000000:  # 2등: 1천만 상
                        rank_distribution[2] += 1
                    elif winning_amount >= 1000000:  # 3등: 100만 상
                        rank_distribution[3] += 1
                    elif winning_amount >= 50000:  # 4등: 5만 상
                        rank_distribution[4] += 1
                    else:  # 5등: 5천원
                        rank_distribution[5] += 1
            
            total_purchase_amount = total_purchase_count * 1000
            win_rate = (
                (total_winning_count / total_purchase_count * 100)
                if total_purchase_count > 0
                else 0
            )
            roi = (
                ((total_winning_amount - total_purchase_amount) / total_purchase_amount * 100)
                if total_purchase_amount > 0
                else 0
            )
            
            return PurchaseStatistics(
                total_purchase_count=total_purchase_count,
                total_purchase_amount=total_purchase_amount,
                total_winning_count=total_winning_count,
                total_winning_amount=total_winning_amount,
                win_rate=round(win_rate, 2),
                roi=round(roi, 2),
                rank_distribution=rank_distribution,
            )

        except Exception as ex:
            raise DhLottoAnalyzerError(f"purchase  analysis failed: {ex}") from ex

    @staticmethod
    def generate_random_numbers(count: int = 6) -> List[int]:
        """
        중복 없는 랜덤 로또 number 생성합니다.
        
        Args:
            count: 생성할 number 개수 (기본 6개)
            
        Returns:
            정렬된 랜덤 number 리스트
        """
        import random
        
        if count < 1 or count > 45:
            raise ValueError("number  1~45  .")
        
        numbers = random.sample(range(1, 46), count)
        return sorted(numbers)

    async def async_check_winning(
        self, my_numbers: List[int], round_no: Optional[int] = None
    ) -> Dict[str, any]:
        """
        내 number winning되었는지 확인합니다.
        
        Args:
            my_numbers: 내 선택한 number (6개)
            round_no: 확인할 round (None면 최신 round)
            
        Returns:
            winning 결과 (등수, 일치 개수, 보너스 일치 여부 등)
        """
        try:
            if len(my_numbers) != 6:
                raise ValueError("number  6 .")
            
            # round 정보 query
            if round_no is None:
                round_no = await self.lotto_645.async_get_latest_round_no()
            
            winning_data = await self.lotto_645.async_get_round_info(round_no)
            
            # 일치 개수 계산
            matching_count = len(set(my_numbers) & set(winning_data.numbers))
            bonus_match = winning_data.bonus_num in my_numbers
            
            # 등수 결정
            rank = 0
            if matching_count == 6:
                rank = 1
            elif matching_count == 5 and bonus_match:
                rank = 2
            elif matching_count == 5:
                rank = 3
            elif matching_count == 4:
                rank = 4
            elif matching_count == 3:
                rank = 5
            
            return {
                "round_no": round_no,
                "my_numbers": sorted(my_numbers),
                "winning_numbers": winning_data.numbers,
                "bonus_number": winning_data.bonus_num,
                "matching_count": matching_count,
                "bonus_match": bonus_match,
                "rank": rank,
                "is_winner": rank > 0,
            }

        except Exception as ex:
            raise DhLottoAnalyzerError(f"winning  failed: {ex}") from ex
