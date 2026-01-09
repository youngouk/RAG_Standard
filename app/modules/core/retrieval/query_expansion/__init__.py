"""
Query Expansion Module

쿼리 확장(Query Expansion) 시스템:
- 단일 쿼리를 다중 변형 쿼리로 확장하여 검색 품질 향상
- GPT-5-nano 기반 지능형 쿼리 생성
- 결과 병합 및 중복 제거

주요 구성 요소:
- IQueryExpansionEngine: Query Expansion 인터페이스
- GPT5QueryExpansionEngine: GPT-5-nano 구현체 (레거시 래핑)
- ExpandedQuery: 확장된 쿼리 데이터 클래스
"""

from .gpt5_engine import GPT5QueryExpansionEngine
from .interface import (
    ExpandedQuery,
    IQueryExpansionEngine,
    QueryComplexity,
    SearchIntent,
)

__all__ = [
    "IQueryExpansionEngine",
    "ExpandedQuery",
    "QueryComplexity",
    "SearchIntent",
    "GPT5QueryExpansionEngine",
]
