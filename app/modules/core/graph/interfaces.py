"""
GraphRAG 인터페이스 정의 (Protocol 기반)
다양한 그래프 백엔드를 플러그인 형태로 교체 가능

기존 IReranker, ICacheManager 패턴과 동일한 구조로,
runtime_checkable Protocol을 사용하여 duck typing 지원.
"""
from typing import Any, Protocol, runtime_checkable

from .models import Entity, GraphSearchResult, Relation


@runtime_checkable
class IGraphStore(Protocol):
    """
    그래프 저장소 인터페이스 (Protocol 기반)

    구현 예시:
    - NetworkXGraphStore: NetworkX 기반 인메모리 그래프
    - Neo4jGraphStore: Neo4j 그래프 데이터베이스 (프로덕션)
    - MockGraphStore: 테스트용 모의 저장소
    """

    async def add_entity(self, entity: Entity) -> None:
        """
        엔티티 추가

        Args:
            entity: 추가할 엔티티
        """
        ...

    async def add_relation(self, relation: Relation) -> None:
        """
        관계 추가

        Args:
            relation: 추가할 관계
        """
        ...

    async def get_entity(self, entity_id: str) -> Entity | None:
        """
        엔티티 조회

        Args:
            entity_id: 엔티티 ID

        Returns:
            엔티티 또는 None
        """
        ...

    async def get_neighbors(
        self,
        entity_id: str,
        relation_types: list[str] | None = None,
        max_depth: int = 1,
    ) -> GraphSearchResult:
        """
        이웃 엔티티 조회 (관계 기반 탐색)

        Args:
            entity_id: 시작 엔티티 ID
            relation_types: 필터링할 관계 유형 (None이면 전체)
            max_depth: 탐색 깊이 (기본값: 1)

        Returns:
            연결된 엔티티와 관계
        """
        ...

    async def search(
        self,
        query: str,
        entity_types: list[str] | None = None,
        top_k: int = 10,
    ) -> GraphSearchResult:
        """
        그래프 검색

        Args:
            query: 검색 쿼리
            entity_types: 필터링할 엔티티 유형
            top_k: 최대 결과 수

        Returns:
            검색 결과
        """
        ...

    async def clear(self) -> None:
        """그래프 전체 삭제"""
        ...

    def get_stats(self) -> dict[str, Any]:
        """
        그래프 통계 반환

        Returns:
            노드 수, 엣지 수 등의 통계
        """
        ...


@runtime_checkable
class IEntityExtractor(Protocol):
    """
    엔티티 추출기 인터페이스

    구현 예시:
    - LLMEntityExtractor: LLM 기반 엔티티 추출 (향후 구현)
    - RuleBasedEntityExtractor: 규칙 기반 추출
    """

    async def extract(self, text: str) -> list[Entity]:
        """
        텍스트에서 엔티티 추출

        Args:
            text: 원본 텍스트

        Returns:
            추출된 엔티티 목록
        """
        ...


@runtime_checkable
class IRelationExtractor(Protocol):
    """
    관계 추출기 인터페이스

    구현 예시:
    - LLMRelationExtractor: LLM 기반 관계 추출 (향후 구현)
    - PatternRelationExtractor: 패턴 기반 추출
    """

    async def extract(self, text: str, entities: list[Entity]) -> list[Relation]:
        """
        텍스트에서 관계 추출

        Args:
            text: 원본 텍스트
            entities: 이미 추출된 엔티티 목록

        Returns:
            추출된 관계 목록
        """
        ...
