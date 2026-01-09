"""
VectorGraphHybridSearch 단위 테스트

벡터 검색과 그래프 검색을 RRF(Reciprocal Rank Fusion)로 결합하는
하이브리드 검색 전략의 단위 테스트입니다.

테스트 카테고리:
- Init: 초기화 및 설정 테스트
- Search: 검색 기능 테스트 (벡터+그래프 결합)
- RRF: RRF 점수 계산 테스트
- Config: 설정 반환 테스트

TDD Red 상태: 구현체(VectorGraphHybridSearch)가 없으므로 테스트 실패 예상

생성일: 2026-01-05
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.core.graph.interfaces import Entity, GraphSearchResult
from app.modules.core.retrieval.hybrid_search.interfaces import (
    HybridSearchResult,
    IHybridSearchStrategy,
)
from app.modules.core.retrieval.interfaces import IRetriever, SearchResult


class TestVectorGraphHybridSearchInit:
    """VectorGraphHybridSearch 초기화 테스트"""

    def test_init_with_valid_components(self) -> None:
        """유효한 컴포넌트로 초기화 성공"""
        # Given - Mock 객체 생성
        mock_retriever = MagicMock(spec=IRetriever)
        mock_graph_store = MagicMock()  # IGraphStore를 모방
        config: dict[str, Any] = {
            "vector_weight": 0.6,
            "graph_weight": 0.4,
            "rrf_k": 60,
        }

        # When - VectorGraphHybridSearch 임포트 및 인스턴스 생성
        from app.modules.core.retrieval.hybrid_search.vector_graph_search import (
            VectorGraphHybridSearch,
        )

        hybrid_search = VectorGraphHybridSearch(
            retriever=mock_retriever,
            graph_store=mock_graph_store,
            config=config,
        )

        # Then - 인스턴스 생성 확인
        assert hybrid_search is not None
        assert isinstance(hybrid_search, IHybridSearchStrategy)

    def test_init_without_graph_store_uses_vector_only_mode(self) -> None:
        """graph_store 없이 초기화 시 벡터 전용 모드로 동작"""
        # Given
        mock_retriever = MagicMock(spec=IRetriever)
        config: dict[str, Any] = {
            "vector_weight": 1.0,
            "graph_weight": 0.0,
        }

        # When
        from app.modules.core.retrieval.hybrid_search.vector_graph_search import (
            VectorGraphHybridSearch,
        )

        hybrid_search = VectorGraphHybridSearch(
            retriever=mock_retriever,
            graph_store=None,
            config=config,
        )

        # Then - 그래프 저장소가 None으로 설정되어야 함
        assert hybrid_search is not None
        assert hybrid_search._graph_store is None

    def test_init_with_default_weights(self) -> None:
        """기본 가중치로 초기화 (설정 없는 경우)"""
        # Given
        mock_retriever = MagicMock(spec=IRetriever)
        mock_graph_store = MagicMock()
        config: dict[str, Any] = {}  # 빈 설정

        # When
        from app.modules.core.retrieval.hybrid_search.vector_graph_search import (
            VectorGraphHybridSearch,
        )

        hybrid_search = VectorGraphHybridSearch(
            retriever=mock_retriever,
            graph_store=mock_graph_store,
            config=config,
        )

        # Then - 기본 가중치 적용 확인
        result_config = hybrid_search.get_config()
        assert result_config["vector_weight"] == 0.6  # 기본값
        assert result_config["graph_weight"] == 0.4  # 기본값
        assert result_config["rrf_k"] == 60  # 기본값


class TestVectorGraphHybridSearchSearch:
    """VectorGraphHybridSearch 검색 기능 테스트"""

    @pytest.fixture
    def mock_retriever(self) -> AsyncMock:
        """Mock Retriever 생성"""
        mock = AsyncMock(spec=IRetriever)
        # 1. 문서 (SearchResult) Mock
        mock.search.return_value = [
            SearchResult(
                id="doc1",
                content="강남 맛집 정보",
                score=0.9,
                metadata={"source": "vector"},
            ),
            SearchResult(
                id="doc2",
                content="홍대 카페 정보",
                score=0.8,
                metadata={"source": "vector"},
            ),
            SearchResult(
                id="doc3",
                content="서초 서점 정보",
                score=0.7,
                metadata={"source": "vector"},
            ),
        ]
        return mock

    @pytest.fixture
    def mock_graph_store(self) -> AsyncMock:
        """Mock GraphStore 생성"""
        mock = AsyncMock()
        # 2. 그래프 검색 결과 Mock
        mock.search.return_value = GraphSearchResult(
            entities=[
                Entity(
                    id="e1",
                    name="강남 A식당",
                    type="company",
                    properties={"doc_id": "doc1"},
                ),
                Entity(
                    id="e2",
                    name="강남 B식당",
                    type="company",
                    properties={"doc_id": "doc4"},  # 벡터 결과에 없는 문서
                ),
            ],
            relations=[],
            score=0.85,
        )
        return mock

    @pytest.fixture
    def hybrid_search_instance(
        self, mock_retriever: AsyncMock, mock_graph_store: AsyncMock
    ) -> Any:
        """하이브리드 검색 인스턴스 픽스처"""
        from app.modules.core.retrieval.hybrid_search.vector_graph_search import (
            VectorGraphHybridSearch,
        )

        return VectorGraphHybridSearch(
            retriever=mock_retriever,
            graph_store=mock_graph_store,
            config={
                "vector_weight": 0.6,
                "graph_weight": 0.4,
                "rrf_k": 60,
            },
        )

    @pytest.mark.asyncio
    async def test_search_combines_vector_and_graph_results(
        self, mock_retriever: AsyncMock, mock_graph_store: AsyncMock
    ) -> None:
        """벡터와 그래프 검색 결과가 결합됨"""
        from app.modules.core.retrieval.hybrid_search.vector_graph_search import (
            VectorGraphHybridSearch,
        )

        config = {
            "vector_weight": 0.5,
            "graph_weight": 0.5,
            "rrf_k": 60,
        }
        hybrid_search_instance = VectorGraphHybridSearch(
            retriever=mock_retriever,
            graph_store=mock_graph_store,
            config=config,
        )

        # When
        result = await hybrid_search_instance.search("강남 맛집", top_k=5)

        # Then - 결과 타입 확인
        assert isinstance(result, HybridSearchResult)
        assert len(result.documents) > 0
        assert result.vector_count > 0
        # 양쪽 검색이 호출되어야 함
        mock_retriever.search.assert_called_once()
        mock_graph_store.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_respects_weight_parameters(
        self, mock_retriever: AsyncMock, mock_graph_store: AsyncMock
    ) -> None:
        """가중치 파라미터가 검색 결과에 반영됨"""
        # Given
        from app.modules.core.retrieval.hybrid_search.vector_graph_search import (
            VectorGraphHybridSearch,
        )

        hybrid_search = VectorGraphHybridSearch(
            retriever=mock_retriever,
            graph_store=mock_graph_store,
            config={"vector_weight": 0.5, "graph_weight": 0.5},
        )

        # When - 벡터 중심 검색
        result_vector_heavy = await hybrid_search.search(
            "강남",
            top_k=5,
            vector_weight=0.9,
            graph_weight=0.1,
        )

        # When - 그래프 중심 검색 (새로운 Mock 객체 필요)
        mock_retriever.reset_mock()
        mock_graph_store.reset_mock()

        result_graph_heavy = await hybrid_search.search(
            "강남",
            top_k=5,
            vector_weight=0.1,
            graph_weight=0.9,
        )

        # Then - 두 결과 모두 유효해야 함
        assert isinstance(result_vector_heavy, HybridSearchResult)
        assert isinstance(result_graph_heavy, HybridSearchResult)
        # 메타데이터에 가중치 정보 포함
        assert "vector_weight" in result_vector_heavy.metadata
        assert "graph_weight" in result_graph_heavy.metadata

    @pytest.mark.asyncio
    async def test_search_with_graph_disabled_returns_vector_only(
        self, mock_retriever: AsyncMock
    ) -> None:
        """graph_store가 없으면 벡터 검색만 수행"""
        # Given
        from app.modules.core.retrieval.hybrid_search.vector_graph_search import (
            VectorGraphHybridSearch,
        )

        hybrid_search = VectorGraphHybridSearch(
            retriever=mock_retriever,
            graph_store=None,  # 그래프 저장소 없음
            config={"vector_weight": 1.0, "graph_weight": 0.0},
        )

        # When
        result = await hybrid_search.search("테스트", top_k=5)

        # Then
        assert result.vector_count > 0
        assert result.graph_count == 0
        mock_retriever.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_returns_documents_sorted_by_rrf_score(
        self, hybrid_search_instance: Any
    ) -> None:
        """검색 결과가 RRF 점수 순으로 정렬됨"""
        # When
        result = await hybrid_search_instance.search("강남", top_k=10)

        # Then - hybrid_score가 내림차순 정렬되어야 함
        if len(result.documents) > 1:
            scores = [doc.metadata.get("hybrid_score", 0) for doc in result.documents]
            for i in range(len(scores) - 1):
                assert scores[i] >= scores[i + 1], "결과가 RRF 점수 순으로 정렬되지 않음"

    @pytest.mark.asyncio
    async def test_search_handles_empty_vector_results(
        self, mock_graph_store: AsyncMock
    ) -> None:
        """벡터 검색 결과가 비어있어도 정상 동작"""
        # Given - 빈 벡터 검색 결과
        empty_retriever = AsyncMock(spec=IRetriever)
        empty_retriever.search.return_value = []

        from app.modules.core.retrieval.hybrid_search.vector_graph_search import (
            VectorGraphHybridSearch,
        )

        hybrid_search = VectorGraphHybridSearch(
            retriever=empty_retriever,
            graph_store=mock_graph_store,
            config={"vector_weight": 0.6, "graph_weight": 0.4},
        )

        # When
        result = await hybrid_search.search("강남", top_k=5)

        # Then - 빈 결과여도 오류 없이 반환
        assert isinstance(result, HybridSearchResult)
        assert result.vector_count == 0

    @pytest.mark.asyncio
    async def test_search_handles_empty_graph_results(
        self, mock_retriever: AsyncMock
    ) -> None:
        """그래프 검색 결과가 비어있어도 정상 동작"""
        # Given - 빈 그래프 검색 결과
        empty_graph_store = AsyncMock()
        empty_graph_store.search.return_value = GraphSearchResult(
            entities=[],
            relations=[],
            score=0.0,
        )

        from app.modules.core.retrieval.hybrid_search.vector_graph_search import (
            VectorGraphHybridSearch,
        )

        hybrid_search = VectorGraphHybridSearch(
            retriever=mock_retriever,
            graph_store=empty_graph_store,
            config={"vector_weight": 0.6, "graph_weight": 0.4},
        )

        # When
        result = await hybrid_search.search("강남", top_k=5)

        # Then - 벡터 결과만 반환
        assert isinstance(result, HybridSearchResult)
        assert result.graph_count == 0
        assert result.vector_count > 0


class TestVectorGraphHybridSearchRRF:
    """RRF(Reciprocal Rank Fusion) 알고리즘 테스트

    RRF 공식: score = sum(1 / (k + rank)) where k=60 (default)
    - 각 검색 소스에서의 랭크를 기반으로 점수 계산
    - 가중치를 적용하여 최종 점수 산출
    """

    @pytest.fixture
    def hybrid_search_for_rrf(self) -> Any:
        """RRF 테스트용 하이브리드 검색 인스턴스"""
        mock_retriever = AsyncMock(spec=IRetriever)
        mock_graph_store = AsyncMock()

        from app.modules.core.retrieval.hybrid_search.vector_graph_search import (
            VectorGraphHybridSearch,
        )

        return VectorGraphHybridSearch(
            retriever=mock_retriever,
            graph_store=mock_graph_store,
            config={
                "vector_weight": 0.6,
                "graph_weight": 0.4,
                "rrf_k": 60,
            },
        )

    def test_calculate_rrf_scores_basic(self, hybrid_search_for_rrf: Any) -> None:
        """RRF 점수 기본 계산 테스트"""
        # Given - 두 검색 결과의 랭크
        vector_ranks = {"doc1": 1, "doc2": 2, "doc3": 3}
        graph_ranks = {"doc1": 2, "doc3": 1, "doc4": 3}

        # When
        rrf_scores = hybrid_search_for_rrf._calculate_rrf_scores(
            vector_ranks=vector_ranks,
            graph_ranks=graph_ranks,
            vector_weight=0.6,
            graph_weight=0.4,
            k=60,
        )

        # Then - doc1은 양쪽에서 발견되어 가장 높은 점수
        assert "doc1" in rrf_scores
        assert "doc3" in rrf_scores
        assert "doc4" in rrf_scores
        assert rrf_scores["doc1"] > rrf_scores.get("doc2", 0)

    def test_calculate_rrf_scores_formula_verification(
        self, hybrid_search_for_rrf: Any
    ) -> None:
        """RRF 공식 검증: score = sum(weight * 1/(k + rank))"""
        # Given - 단순 랭크로 공식 검증
        vector_ranks = {"doc1": 1}  # vector 랭크 1
        graph_ranks = {"doc1": 1}  # graph 랭크 1
        k = 60
        vector_weight = 0.6
        graph_weight = 0.4

        # Expected score for doc1:
        # = vector_weight * 1/(k + 1) + graph_weight * 1/(k + 1)
        # = 0.6 * 1/61 + 0.4 * 1/61
        # = 1.0 * 1/61
        # ≈ 0.01639
        expected_score = vector_weight * (1.0 / (k + 1)) + graph_weight * (1.0 / (k + 1))

        # When
        rrf_scores = hybrid_search_for_rrf._calculate_rrf_scores(
            vector_ranks=vector_ranks,
            graph_ranks=graph_ranks,
            vector_weight=vector_weight,
            graph_weight=graph_weight,
            k=k,
        )

        # Then - 계산된 점수가 예상 점수와 일치
        assert rrf_scores["doc1"] == pytest.approx(expected_score, rel=1e-5)

    def test_calculate_rrf_scores_only_vector(self, hybrid_search_for_rrf: Any) -> None:
        """벡터 검색에서만 발견된 문서의 RRF 점수"""
        # Given
        vector_ranks = {"doc1": 1}
        graph_ranks: dict[str, int] = {}  # 그래프에서는 발견되지 않음
        k = 60
        vector_weight = 0.6
        graph_weight = 0.4

        # Expected: 벡터 점수만
        expected_score = vector_weight * (1.0 / (k + 1))

        # When
        rrf_scores = hybrid_search_for_rrf._calculate_rrf_scores(
            vector_ranks=vector_ranks,
            graph_ranks=graph_ranks,
            vector_weight=vector_weight,
            graph_weight=graph_weight,
            k=k,
        )

        # Then
        assert rrf_scores["doc1"] == pytest.approx(expected_score, rel=1e-5)

    def test_calculate_rrf_scores_only_graph(self, hybrid_search_for_rrf: Any) -> None:
        """그래프 검색에서만 발견된 문서의 RRF 점수"""
        # Given
        vector_ranks: dict[str, int] = {}
        graph_ranks = {"doc1": 1}
        k = 60
        vector_weight = 0.6
        graph_weight = 0.4

        # Expected: 그래프 점수만
        expected_score = graph_weight * (1.0 / (k + 1))

        # When
        rrf_scores = hybrid_search_for_rrf._calculate_rrf_scores(
            vector_ranks=vector_ranks,
            graph_ranks=graph_ranks,
            vector_weight=vector_weight,
            graph_weight=graph_weight,
            k=k,
        )

        # Then
        assert rrf_scores["doc1"] == pytest.approx(expected_score, rel=1e-5)

    def test_calculate_rrf_scores_ranking_order(
        self, hybrid_search_for_rrf: Any
    ) -> None:
        """랭크가 낮을수록(상위) 높은 RRF 점수"""
        # Given - 다양한 랭크의 문서
        vector_ranks = {"doc1": 1, "doc2": 5, "doc3": 10}
        graph_ranks = {}
        k = 60
        vector_weight = 1.0
        graph_weight = 0.0

        # When
        rrf_scores = hybrid_search_for_rrf._calculate_rrf_scores(
            vector_ranks=vector_ranks,
            graph_ranks=graph_ranks,
            vector_weight=vector_weight,
            graph_weight=graph_weight,
            k=k,
        )

        # Then - 상위 랭크(낮은 숫자)가 높은 점수
        assert rrf_scores["doc1"] > rrf_scores["doc2"]
        assert rrf_scores["doc2"] > rrf_scores["doc3"]

    def test_calculate_rrf_scores_with_different_k_values(
        self, hybrid_search_for_rrf: Any
    ) -> None:
        """k 값에 따른 RRF 점수 변화"""
        # Given
        vector_ranks = {"doc1": 1}
        graph_ranks: dict[str, int] = {}
        vector_weight = 1.0
        graph_weight = 0.0

        # When - 다양한 k 값으로 점수 계산
        score_k_60 = hybrid_search_for_rrf._calculate_rrf_scores(
            vector_ranks, graph_ranks, vector_weight, graph_weight, k=60
        )["doc1"]

        score_k_100 = hybrid_search_for_rrf._calculate_rrf_scores(
            vector_ranks, graph_ranks, vector_weight, graph_weight, k=100
        )["doc1"]

        # Then - k가 클수록 점수가 낮아짐 (1/(k+rank))
        assert score_k_60 > score_k_100


class TestVectorGraphHybridSearchConfig:
    """VectorGraphHybridSearch 설정 테스트"""

    def test_get_config_returns_current_settings(self) -> None:
        """get_config가 현재 설정을 올바르게 반환"""
        # Given
        mock_retriever = MagicMock(spec=IRetriever)
        config = {
            "vector_weight": 0.7,
            "graph_weight": 0.3,
            "rrf_k": 50,
        }

        from app.modules.core.retrieval.hybrid_search.vector_graph_search import (
            VectorGraphHybridSearch,
        )

        hybrid_search = VectorGraphHybridSearch(
            retriever=mock_retriever,
            graph_store=None,
            config=config,
        )

        # When
        result_config = hybrid_search.get_config()

        # Then
        assert result_config["vector_weight"] == 0.7
        assert result_config["graph_weight"] == 0.3
        assert result_config["rrf_k"] == 50
        assert result_config["graph_enabled"] is False  # graph_store가 None이므로

    def test_get_config_includes_graph_enabled_status(self) -> None:
        """get_config에 그래프 활성화 상태 포함"""
        # Given
        mock_retriever = MagicMock(spec=IRetriever)
        mock_graph_store = MagicMock()

        from app.modules.core.retrieval.hybrid_search.vector_graph_search import (
            VectorGraphHybridSearch,
        )

        # 그래프 저장소 있는 경우
        hybrid_with_graph = VectorGraphHybridSearch(
            retriever=mock_retriever,
            graph_store=mock_graph_store,
            config={},
        )

        # 그래프 저장소 없는 경우
        hybrid_without_graph = VectorGraphHybridSearch(
            retriever=mock_retriever,
            graph_store=None,
            config={},
        )

        # When
        config_with_graph = hybrid_with_graph.get_config()
        config_without_graph = hybrid_without_graph.get_config()

        # Then
        assert config_with_graph["graph_enabled"] is True
        assert config_without_graph["graph_enabled"] is False


class TestVectorGraphHybridSearchEdgeCases:
    """VectorGraphHybridSearch 엣지 케이스 테스트"""

    @pytest.mark.asyncio
    async def test_search_with_zero_top_k(self) -> None:
        """top_k=0인 경우 빈 결과 반환"""
        # Given
        mock_retriever = AsyncMock(spec=IRetriever)
        mock_retriever.search.return_value = []

        from app.modules.core.retrieval.hybrid_search.vector_graph_search import (
            VectorGraphHybridSearch,
        )

        hybrid_search = VectorGraphHybridSearch(
            retriever=mock_retriever,
            graph_store=None,
            config={},
        )

        # When
        result = await hybrid_search.search("test", top_k=0)

        # Then
        assert len(result.documents) == 0

    @pytest.mark.asyncio
    async def test_search_with_empty_query(self) -> None:
        """빈 쿼리로 검색"""
        # Given
        mock_retriever = AsyncMock(spec=IRetriever)
        mock_retriever.search.return_value = []

        from app.modules.core.retrieval.hybrid_search.vector_graph_search import (
            VectorGraphHybridSearch,
        )

        hybrid_search = VectorGraphHybridSearch(
            retriever=mock_retriever,
            graph_store=None,
            config={},
        )

        # When
        result = await hybrid_search.search("", top_k=5)

        # Then - 빈 결과 반환 (오류 없이)
        assert isinstance(result, HybridSearchResult)

    def test_weight_normalization(self) -> None:
        """가중치가 정규화되어야 함 (합이 1이 아닌 경우)"""
        # Given
        mock_retriever = MagicMock(spec=IRetriever)
        config = {
            "vector_weight": 3.0,  # 비정상적으로 큰 값
            "graph_weight": 2.0,
        }

        from app.modules.core.retrieval.hybrid_search.vector_graph_search import (
            VectorGraphHybridSearch,
        )

        hybrid_search = VectorGraphHybridSearch(
            retriever=mock_retriever,
            graph_store=None,
            config=config,
        )

        # Then - 설정은 원본 값 유지 (정규화는 검색 시 적용)
        result_config = hybrid_search.get_config()
        # 내부적으로 가중치가 저장되었는지 확인
        assert "vector_weight" in result_config
        assert "graph_weight" in result_config
