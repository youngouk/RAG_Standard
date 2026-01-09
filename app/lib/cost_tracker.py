"""
Cost Tracker Module - LLM API 비용 추적
"""

from typing import Any

from ..lib.logger import get_logger

logger = get_logger(__name__)


class CostTracker:
    """LLM API 비용 추적 클래스"""

    def __init__(self) -> None:
        self.total_cost = 0.0
        self.usage_stats: dict[str, Any] = {}

    def track_usage(self, provider: str, tokens: int, is_input: bool = True) -> None:
        """
        API 사용량 추적

        Args:
            provider: LLM 제공자 (예: "gemini", "openai")
            tokens: 사용된 토큰 수
            is_input: 입력 토큰 여부 (True) / 출력 토큰 (False)
        """
        if provider not in self.usage_stats:
            self.usage_stats[provider] = {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
            }

        if is_input:
            self.usage_stats[provider]["input_tokens"] += tokens
        else:
            self.usage_stats[provider]["output_tokens"] += tokens

        self.usage_stats[provider]["total_tokens"] += tokens

    def get_stats(self) -> dict[str, Any]:
        """현재 사용 통계 반환"""
        return {
            "total_cost": self.total_cost,
            "usage": self.usage_stats,
        }

    def reset(self) -> None:
        """통계 초기화"""
        self.total_cost = 0.0
        self.usage_stats = {}


# 전역 인스턴스
cost_tracker = CostTracker()
