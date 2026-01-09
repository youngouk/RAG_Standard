"""
Query Expansion Engine Interface

쿼리 확장 시스템의 표준 인터페이스 정의
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any


class QueryComplexity(str, Enum):
    """쿼리 복잡도 레벨"""

    SIMPLE = "simple"  # 단순 사실 확인
    MEDIUM = "medium"  # 일반적인 질문
    COMPLEX = "complex"  # 복잡한 추론 필요
    CONTEXTUAL = "contextual"  # 맥락 의존적


class SearchIntent(str, Enum):
    """검색 의도 분류"""

    FACTUAL = "factual"  # 사실 확인
    PROCEDURAL = "procedural"  # 절차/방법
    CONCEPTUAL = "conceptual"  # 개념 이해
    COMPARATIVE = "comparative"  # 비교 분석
    PROBLEM_SOLVING = "problem_solving"  # 문제 해결


@dataclass
class ExpandedQuery:
    """
    확장된 쿼리 데이터 클래스

    Attributes:
        original: 원본 쿼리
        expansions: 확장된 쿼리 리스트
        complexity: 복잡도 레벨
        intent: 검색 의도
        metadata: 추가 메타데이터 (토큰 수, 생성 시간 등)
    """

    original: str
    expansions: list[str]
    complexity: QueryComplexity
    intent: SearchIntent
    metadata: dict[str, Any]

    def __post_init__(self) -> None:
        """데이터 검증"""
        if not self.original:
            raise ValueError("Original query cannot be empty")

        if not self.expansions:
            # 확장 실패 시 원본 쿼리만 사용
            self.expansions = [self.original]

        # 중복 제거 (대소문자 구분하여 유사도 체크)
        seen = set()
        unique_expansions = []
        for query in self.expansions:
            normalized = query.lower().strip()
            if normalized not in seen:
                seen.add(normalized)
                unique_expansions.append(query)

        self.expansions = unique_expansions

    @property
    def all_queries(self) -> list[str]:
        """원본 + 확장 쿼리 전체 리스트"""
        return [self.original] + [q for q in self.expansions if q != self.original]

    @property
    def expansion_count(self) -> int:
        """확장된 쿼리 개수"""
        return len(self.expansions)


class IQueryExpansionEngine(ABC):
    """
    Query Expansion Engine 인터페이스

    쿼리 확장 엔진의 표준 계약을 정의합니다.
    구현체는 다양한 LLM (GPT-5, Claude, Gemini 등)을 사용할 수 있습니다.
    """

    @abstractmethod
    async def expand(self, query: str, num_expansions: int = 5, **kwargs: Any) -> ExpandedQuery:
        """
        쿼리를 다중 변형으로 확장

        Args:
            query: 원본 사용자 쿼리
            num_expansions: 생성할 확장 쿼리 개수 (기본값: 5)
            **kwargs: 추가 옵션
                - max_tokens: 최대 토큰 수
                - temperature: 생성 다양성 (0.0-1.0)
                - use_cache: 캐시 사용 여부

        Returns:
            ExpandedQuery: 확장된 쿼리 객체

        Raises:
            ValueError: 입력 쿼리가 비어있거나 num_expansions가 유효하지 않은 경우
            RuntimeError: LLM 호출 실패 등 런타임 오류
        """
        pass

    @abstractmethod
    async def analyze_complexity(self, query: str) -> QueryComplexity:
        """
        쿼리 복잡도 분석

        Args:
            query: 분석할 쿼리

        Returns:
            QueryComplexity: 복잡도 레벨
        """
        pass

    @abstractmethod
    async def detect_intent(self, query: str) -> SearchIntent:
        """
        검색 의도 탐지

        Args:
            query: 분석할 쿼리

        Returns:
            SearchIntent: 검색 의도 분류
        """
        pass

    @abstractmethod
    def get_stats(self) -> dict[str, Any]:
        """
        엔진 통계 정보 반환

        Returns:
            Dict: 통계 정보
                - total_expansions: 총 확장 요청 수
                - cache_hits: 캐시 히트 수
                - cache_misses: 캐시 미스 수
                - avg_response_time: 평균 응답 시간 (초)
                - error_rate: 에러 발생률
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        엔진 상태 확인

        Returns:
            bool: 정상 동작 여부
        """
        pass
