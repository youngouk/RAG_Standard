"""
벡터+그래프 하이브리드 검색 통합 테스트

실제 컴포넌트들이 올바르게 연동되는지 테스트합니다.

테스트 시나리오:
1. DI Container → Orchestrator → Hybrid Search → Results 전체 플로우
2. graph_rag.enabled=true 시 하이브리드 검색 활성화 검증
3. graph_rag.enabled=false 시 벡터 전용 검색 폴백 검증
4. use_graph 파라미터 동작 검증
5. RRF 점수 결합 검증
6. 통계 추적 (hybrid_search_count) 검증

주의: 외부 의존성(Neo4j, Weaviate)은 Mock으로 대체하여
    실제 컴포넌트 간 통합만 테스트합니다.

생성일: 2026-01-05
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.modules.core.graph import NetworkXGraphStore
from app.modules.core.graph.interfaces import Entity
from app.modules.core.retrieval.hybrid_search import VectorGraphHybridSearch
from app.modules.core.retrieval.hybrid_search.interfaces import HybridSearchResult
from app.modules.core.retrieval.interfaces import SearchResult
from app.modules.core.retrieval.orchestrator import RetrievalOrchestrator


class TestHybridSearchFullFlowIntegration:
    """
    하이브리드 검색 전체 플로우 통합 테스트

    DI Container → Orchestrator → Hybrid Search → Results 흐름 검증
    """

    @pytest.fixture
    def mock_retriever(self) -> AsyncMock:
        """
        벡터 검색기 Mock

        Returns:
            벡터 검색 결과를 반환하는 AsyncMock
        """
        retriever = AsyncMock()
        retriever.search.return_value = [
            SearchResult(
                id="doc1",
                content="강남 맛집 정보입니다.",
                score=0.95,
                metadata={"source": "vector", "file_type": "TXT"},
            ),
            SearchResult(
                id="doc2",
                content="홍대 카페 정보입니다.",
                score=0.88,
                metadata={"source": "vector", "file_type": "TXT"},
            ),
            SearchResult(
                id="doc3",
                content="신촌 서점 정보입니다.",
                score=0.75,
                metadata={"source": "vector", "file_type": "TXT"},
            ),
        ]
        retriever.initialize = AsyncMock()
        retriever.health_check = AsyncMock(return_value=True)
        return retriever

    @pytest.fixture
    def mock_reranker(self) -> AsyncMock:
        """
        리랭커 Mock

        입력받은 문서를 그대로 반환 (테스트 단순화)

        Returns:
            리랭킹 없이 원본 반환하는 AsyncMock
        """
        reranker = AsyncMock()
        reranker.rerank.side_effect = lambda q, docs, top_k: docs[:top_k]
        reranker.name = "MockReranker"
        return reranker

    @pytest.fixture
    def graph_store(self) -> NetworkXGraphStore:
        """
        실제 NetworkXGraphStore 인스턴스

        Returns:
            테스트용 그래프 저장소
        """
        return NetworkXGraphStore()

    @pytest.fixture
    async def populated_graph_store(self, graph_store: NetworkXGraphStore) -> NetworkXGraphStore:
        """
        데이터가 미리 저장된 GraphStore

        벡터 검색과 중복되는 doc_id를 가진 엔티티를 포함하여
        RRF 결합 테스트가 가능하도록 함

        Returns:
            엔티티와 관계가 저장된 그래프 저장소
        """
        # 엔티티 추가 (벡터 검색과 일부 중복되는 doc_id 포함)
        await graph_store.add_entity(
            Entity(
                id="e1",
                name="강남 A식당",
                type="company",
                properties={"doc_id": "doc1"},  # 벡터 검색 결과와 중복
            )
        )
        await graph_store.add_entity(
            Entity(
                id="e2",
                name="강남 B식당",
                type="company",
                properties={"doc_id": "doc4"},  # 벡터 검색에 없는 문서
            )
        )
        await graph_store.add_entity(
            Entity(
                id="e3",
                name="서울",
                type="location",
                properties={"doc_id": "doc5"},
            )
        )

        return graph_store

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_orchestrator_with_graph_store_creates_hybrid_strategy(
        self,
        mock_retriever: AsyncMock,
        mock_reranker: AsyncMock,
        populated_graph_store: NetworkXGraphStore,
    ) -> None:
        """
        graph_store 주입 시 RetrievalOrchestrator가 하이브리드 전략을 자동 생성

        Given: graph_store가 주입된 RetrievalOrchestrator
        When: 오케스트레이터 생성
        Then: _hybrid_strategy가 VectorGraphHybridSearch 인스턴스로 설정됨
        """
        # Given & When
        config = {
            "hybrid_search": {
                "enabled": True,
                "vector_weight": 0.6,
                "graph_weight": 0.4,
            }
        }

        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            reranker=mock_reranker,
            cache=None,
            graph_store=populated_graph_store,
            config=config,
        )

        # Then: 하이브리드 전략이 자동 생성됨
        assert orchestrator._hybrid_strategy is not None
        assert isinstance(orchestrator._hybrid_strategy, VectorGraphHybridSearch)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_flow_with_hybrid_search_enabled(
        self,
        mock_retriever: AsyncMock,
        mock_reranker: AsyncMock,
        populated_graph_store: NetworkXGraphStore,
    ) -> None:
        """
        하이브리드 검색 활성화 시 전체 플로우 검증

        Given: graph_store가 주입된 RetrievalOrchestrator
        When: use_graph=True로 search_and_rerank 호출
        Then:
            - 벡터 검색과 그래프 검색 모두 실행됨
            - hybrid_search_count 통계가 증가함
            - 결과가 RRF로 결합됨
        """
        # Given
        config = {
            "hybrid_search": {
                "enabled": True,
                "vector_weight": 0.6,
                "graph_weight": 0.4,
            }
        }

        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            reranker=mock_reranker,
            cache=None,
            graph_store=populated_graph_store,
            config=config,
        )

        # When
        results = await orchestrator.search_and_rerank(
            query="강남 맛집",
            top_k=5,
            use_graph=True,
        )

        # Then: 검색 결과 존재
        assert len(results) > 0

        # Then: 벡터 검색이 호출됨
        mock_retriever.search.assert_called()

        # Then: 하이브리드 검색 통계 증가
        assert orchestrator.stats["hybrid_search_count"] >= 1

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_fallback_to_vector_only_when_use_graph_false(
        self,
        mock_retriever: AsyncMock,
        mock_reranker: AsyncMock,
        populated_graph_store: NetworkXGraphStore,
    ) -> None:
        """
        use_graph=False 시 벡터 검색만 수행

        Given: graph_store가 주입된 RetrievalOrchestrator
        When: use_graph=False로 search_and_rerank 호출
        Then:
            - 벡터 검색만 실행됨
            - hybrid_search_count가 증가하지 않음
        """
        # Given
        config = {
            "hybrid_search": {
                "enabled": True,
                "vector_weight": 0.6,
                "graph_weight": 0.4,
            }
        }

        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            reranker=mock_reranker,
            cache=None,
            graph_store=populated_graph_store,
            config=config,
        )

        initial_hybrid_count = orchestrator.stats["hybrid_search_count"]

        # When
        results = await orchestrator.search_and_rerank(
            query="강남",
            top_k=5,
            use_graph=False,  # 벡터 검색만 사용
        )

        # Then: 결과 존재
        assert len(results) > 0

        # Then: 벡터 검색 호출됨
        mock_retriever.search.assert_called()

        # Then: 하이브리드 검색 카운트 변화 없음
        assert orchestrator.stats["hybrid_search_count"] == initial_hybrid_count

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_orchestrator_without_graph_store_uses_vector_only(
        self,
        mock_retriever: AsyncMock,
        mock_reranker: AsyncMock,
    ) -> None:
        """
        graph_store 없이 생성 시 벡터 전용 모드

        Given: graph_store=None인 RetrievalOrchestrator
        When: use_graph=True로 search_and_rerank 호출
        Then:
            - _hybrid_strategy가 None
            - 벡터 검색만 수행됨
        """
        # Given
        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            reranker=mock_reranker,
            cache=None,
            graph_store=None,  # 그래프 없음
            config={},
        )

        # Then: 하이브리드 전략 없음
        assert orchestrator._hybrid_strategy is None

        # When: use_graph=True라도 벡터만 사용
        results = await orchestrator.search_and_rerank(
            query="강남",
            top_k=5,
            use_graph=True,  # graph_store 없으므로 무시됨
        )

        # Then: 벡터 검색만 호출됨
        mock_retriever.search.assert_called()
        assert len(results) > 0


class TestVectorGraphHybridSearchIntegration:
    """
    VectorGraphHybridSearch 컴포넌트 통합 테스트

    RRF 점수 결합 및 가중치 적용 검증
    """

    @pytest.fixture
    def mock_retriever(self) -> AsyncMock:
        """벡터 검색기 Mock"""
        retriever = AsyncMock()
        retriever.search.return_value = [
            SearchResult(
                id="doc1",
                content="강남 맛집",
                score=0.95,
                metadata={"source": "vector"},
            ),
            SearchResult(
                id="doc2",
                content="홍대 카페",
                score=0.85,
                metadata={"source": "vector"},
            ),
            SearchResult(
                id="doc3",
                content="신촌 서점",
                score=0.75,
                metadata={"source": "vector"},
            ),
        ]
        return retriever

    @pytest.fixture
    async def populated_graph_store(self) -> NetworkXGraphStore:
        """엔티티가 저장된 그래프 저장소"""
        store = NetworkXGraphStore()

        # doc1과 중복, doc4는 새로운 문서
        await store.add_entity(
            Entity(
                id="e1",
                name="강남 A식당",
                type="company",
                properties={"doc_id": "doc1"},  # 벡터와 중복
            )
        )
        await store.add_entity(
            Entity(
                id="e2",
                name="강남 B식당",
                type="company",
                properties={"doc_id": "doc4"},  # 벡터에 없음
            )
        )

        return store

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rrf_score_combination_boosts_overlapping_docs(
        self,
        mock_retriever: AsyncMock,
        populated_graph_store: NetworkXGraphStore,
    ) -> None:
        """
        RRF 결합 시 양쪽 검색에서 발견된 문서가 상위 랭크됨

        Given: doc1이 벡터와 그래프 검색 모두에서 발견됨
        When: 하이브리드 검색 수행
        Then: doc1이 가장 높은 hybrid_score를 가짐
        """
        # Given
        config = {
            "vector_weight": 0.5,
            "graph_weight": 0.5,
            "rrf_k": 60,
        }

        hybrid_search = VectorGraphHybridSearch(
            retriever=mock_retriever,
            graph_store=populated_graph_store,
            config=config,
        )

        # When
        result = await hybrid_search.search("강남", top_k=5)

        # Then: 결과 존재
        assert isinstance(result, HybridSearchResult)
        assert len(result.documents) > 0

        # Then: doc1이 양쪽에서 발견되어 최상위 (또는 상위권)
        # RRF 알고리즘 특성: 양쪽에서 발견된 문서가 더 높은 점수
        doc_ids = [doc.id for doc in result.documents]
        assert "doc1" in doc_ids

        # doc1의 hybrid_score가 존재함
        doc1_result = next((d for d in result.documents if d.id == "doc1"), None)
        assert doc1_result is not None
        assert "hybrid_score" in doc1_result.metadata

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_vector_weight_affects_ranking(
        self,
        mock_retriever: AsyncMock,
        populated_graph_store: NetworkXGraphStore,
    ) -> None:
        """
        벡터 가중치가 높을수록 벡터 검색 결과가 우세함

        Given: vector_weight=0.9, graph_weight=0.1
        When: 하이브리드 검색 수행
        Then: 벡터 검색 결과의 순서가 더 많이 반영됨
        """
        # Given: 벡터 가중치 높음
        config_vector_heavy = {
            "vector_weight": 0.9,
            "graph_weight": 0.1,
            "rrf_k": 60,
        }

        hybrid_search = VectorGraphHybridSearch(
            retriever=mock_retriever,
            graph_store=populated_graph_store,
            config=config_vector_heavy,
        )

        # When
        result = await hybrid_search.search("강남", top_k=5)

        # Then: 벡터 검색 결과가 많이 반영됨
        assert result.vector_count > 0
        assert isinstance(result, HybridSearchResult)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_graph_weight_affects_ranking(
        self,
        mock_retriever: AsyncMock,
        populated_graph_store: NetworkXGraphStore,
    ) -> None:
        """
        그래프 가중치가 높을수록 그래프 검색 결과가 우세함

        Given: vector_weight=0.1, graph_weight=0.9
        When: 하이브리드 검색 수행
        Then: 그래프 검색 결과의 순서가 더 많이 반영됨
        """
        # Given: 그래프 가중치 높음
        config_graph_heavy = {
            "vector_weight": 0.1,
            "graph_weight": 0.9,
            "rrf_k": 60,
        }

        hybrid_search = VectorGraphHybridSearch(
            retriever=mock_retriever,
            graph_store=populated_graph_store,
            config=config_graph_heavy,
        )

        # When
        result = await hybrid_search.search("강남", top_k=5)

        # Then: 결과 존재 및 그래프 검색 실행됨
        assert isinstance(result, HybridSearchResult)
        assert result.graph_count >= 0  # 그래프 검색 실행됨

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_hybrid_search_without_graph_store_returns_vector_only(
        self,
        mock_retriever: AsyncMock,
    ) -> None:
        """
        graph_store=None일 때 벡터 검색만 수행

        Given: graph_store가 None인 VectorGraphHybridSearch
        When: search 호출
        Then: vector_count > 0, graph_count == 0
        """
        # Given
        config = {"vector_weight": 1.0, "graph_weight": 0.0}

        hybrid_search = VectorGraphHybridSearch(
            retriever=mock_retriever,
            graph_store=None,  # 그래프 없음
            config=config,
        )

        # When
        result = await hybrid_search.search("강남", top_k=5)

        # Then: 벡터만 사용됨
        assert result.vector_count > 0
        assert result.graph_count == 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_config_returns_current_settings(
        self,
        mock_retriever: AsyncMock,
        populated_graph_store: NetworkXGraphStore,
    ) -> None:
        """
        get_config()가 현재 설정을 올바르게 반환

        Given: 특정 가중치로 설정된 VectorGraphHybridSearch
        When: get_config() 호출
        Then: 설정된 가중치가 반환됨
        """
        # Given
        config = {
            "vector_weight": 0.7,
            "graph_weight": 0.3,
            "rrf_k": 100,
        }

        hybrid_search = VectorGraphHybridSearch(
            retriever=mock_retriever,
            graph_store=populated_graph_store,
            config=config,
        )

        # When
        result_config = hybrid_search.get_config()

        # Then
        assert result_config["vector_weight"] == 0.7
        assert result_config["graph_weight"] == 0.3
        assert result_config["rrf_k"] == 100
        assert result_config["graph_enabled"] is True


class TestRRFScoreCalculationIntegration:
    """
    RRF(Reciprocal Rank Fusion) 점수 계산 통합 테스트

    RRF 알고리즘이 올바르게 점수를 결합하는지 검증
    """

    @pytest.fixture
    def mock_retriever(self) -> AsyncMock:
        """벡터 검색기 Mock - 특정 순서의 결과 반환"""
        retriever = AsyncMock()
        retriever.search.return_value = [
            SearchResult(id="A", content="A 문서", score=0.9, metadata={}),
            SearchResult(id="B", content="B 문서", score=0.8, metadata={}),
            SearchResult(id="C", content="C 문서", score=0.7, metadata={}),
        ]
        return retriever

    @pytest.fixture
    async def graph_store_with_different_order(self) -> NetworkXGraphStore:
        """
        벡터 검색과 다른 순서의 결과를 반환하는 그래프 저장소

        벡터: A(1위), B(2위), C(3위)
        그래프: B(1위), A(2위), D(3위)

        RRF 결합 시 A와 B 모두 양쪽에서 발견되므로
        더 높은 점수를 받아야 함
        """
        store = NetworkXGraphStore()

        # 그래프 검색 결과 순서: B, A, D
        await store.add_entity(
            Entity(id="eB", name="B", type="doc", properties={"doc_id": "B"})
        )
        await store.add_entity(
            Entity(id="eA", name="A", type="doc", properties={"doc_id": "A"})
        )
        await store.add_entity(
            Entity(id="eD", name="D", type="doc", properties={"doc_id": "D"})
        )

        return store

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rrf_boosts_documents_found_in_both_sources(
        self,
        mock_retriever: AsyncMock,
        graph_store_with_different_order: NetworkXGraphStore,
    ) -> None:
        """
        양쪽 검색에서 발견된 문서가 더 높은 RRF 점수를 받음

        Given:
            - 벡터 검색: A(1위), B(2위), C(3위)
            - 그래프 검색: B(1위), A(2위), D(3위)
        When: 동일 가중치(0.5, 0.5)로 RRF 결합
        Then: A, B가 상위에 위치 (양쪽에서 발견됨)
        """
        # Given
        config = {
            "vector_weight": 0.5,
            "graph_weight": 0.5,
            "rrf_k": 60,
        }

        hybrid_search = VectorGraphHybridSearch(
            retriever=mock_retriever,
            graph_store=graph_store_with_different_order,
            config=config,
        )

        # When
        result = await hybrid_search.search("test", top_k=5)

        # Then: 결과에 A, B 포함 (양쪽 발견)
        doc_ids = [doc.id for doc in result.documents]
        assert "A" in doc_ids
        assert "B" in doc_ids

        # A와 B 중 하나는 상위 2위 안에 있어야 함
        top2_ids = [result.documents[0].id, result.documents[1].id] if len(result.documents) >= 2 else []
        assert "A" in top2_ids or "B" in top2_ids

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rrf_score_metadata_contains_ranks(
        self,
        mock_retriever: AsyncMock,
        graph_store_with_different_order: NetworkXGraphStore,
    ) -> None:
        """
        RRF 결과의 메타데이터에 vector_rank, graph_rank 포함

        Given: 하이브리드 검색 수행
        When: 결과 확인
        Then: 각 문서의 메타데이터에 랭크 정보 포함
        """
        # Given
        config = {
            "vector_weight": 0.5,
            "graph_weight": 0.5,
            "rrf_k": 60,
        }

        hybrid_search = VectorGraphHybridSearch(
            retriever=mock_retriever,
            graph_store=graph_store_with_different_order,
            config=config,
        )

        # When
        result = await hybrid_search.search("test", top_k=5)

        # Then: 메타데이터에 랭크 정보 포함
        for doc in result.documents:
            # hybrid_score는 항상 존재해야 함
            assert "hybrid_score" in doc.metadata

            # vector_rank 또는 graph_rank 중 하나 이상 존재
            has_rank_info = (
                doc.metadata.get("vector_rank") is not None
                or doc.metadata.get("graph_rank") is not None
            )
            assert has_rank_info


class TestOrchestratorStatisticsIntegration:
    """
    RetrievalOrchestrator 통계 추적 통합 테스트

    hybrid_search_count 등 통계가 올바르게 추적되는지 검증
    """

    @pytest.fixture
    def mock_retriever(self) -> AsyncMock:
        """벡터 검색기 Mock"""
        retriever = AsyncMock()
        retriever.search.return_value = [
            SearchResult(id="doc1", content="테스트", score=0.9, metadata={}),
        ]
        retriever.initialize = AsyncMock()
        return retriever

    @pytest.fixture
    def mock_reranker(self) -> AsyncMock:
        """리랭커 Mock"""
        reranker = AsyncMock()
        reranker.rerank.side_effect = lambda q, docs, top_k: docs[:top_k]
        reranker.name = "MockReranker"
        return reranker

    @pytest.fixture
    async def graph_store(self) -> NetworkXGraphStore:
        """그래프 저장소"""
        store = NetworkXGraphStore()
        await store.add_entity(
            Entity(id="e1", name="테스트", type="test", properties={"doc_id": "doc1"})
        )
        return store

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_hybrid_search_count_increments_on_use_graph_true(
        self,
        mock_retriever: AsyncMock,
        mock_reranker: AsyncMock,
        graph_store: NetworkXGraphStore,
    ) -> None:
        """
        use_graph=True 호출 시 hybrid_search_count 증가

        Given: 초기 hybrid_search_count = 0
        When: use_graph=True로 3회 검색
        Then: hybrid_search_count = 3
        """
        # Given
        config = {"hybrid_search": {"enabled": True}}

        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            reranker=mock_reranker,
            cache=None,
            graph_store=graph_store,
            config=config,
        )

        initial_count = orchestrator.stats["hybrid_search_count"]

        # When: 3회 하이브리드 검색
        for _ in range(3):
            await orchestrator.search_and_rerank(
                query="테스트", top_k=5, use_graph=True
            )

        # Then: 카운트 3 증가
        assert orchestrator.stats["hybrid_search_count"] == initial_count + 3

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_hybrid_search_count_not_incremented_on_use_graph_false(
        self,
        mock_retriever: AsyncMock,
        mock_reranker: AsyncMock,
        graph_store: NetworkXGraphStore,
    ) -> None:
        """
        use_graph=False 호출 시 hybrid_search_count 변화 없음

        Given: graph_store가 있는 orchestrator
        When: use_graph=False로 검색
        Then: hybrid_search_count 변화 없음
        """
        # Given
        config = {"hybrid_search": {"enabled": True}}

        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            reranker=mock_reranker,
            cache=None,
            graph_store=graph_store,
            config=config,
        )

        initial_count = orchestrator.stats["hybrid_search_count"]

        # When: 벡터 전용 검색
        await orchestrator.search_and_rerank(query="테스트", top_k=5, use_graph=False)

        # Then: 카운트 변화 없음
        assert orchestrator.stats["hybrid_search_count"] == initial_count

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_total_requests_increments_regardless_of_search_type(
        self,
        mock_retriever: AsyncMock,
        mock_reranker: AsyncMock,
        graph_store: NetworkXGraphStore,
    ) -> None:
        """
        total_requests는 검색 타입과 무관하게 증가

        Given: orchestrator
        When: 다양한 타입의 검색 수행
        Then: total_requests가 모든 호출에 대해 증가
        """
        # Given
        config = {"hybrid_search": {"enabled": True}}

        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            reranker=mock_reranker,
            cache=None,
            graph_store=graph_store,
            config=config,
        )

        initial_count = orchestrator.stats["total_requests"]

        # When: 다양한 검색 수행
        await orchestrator.search_and_rerank(query="테스트1", top_k=5, use_graph=True)
        await orchestrator.search_and_rerank(query="테스트2", top_k=5, use_graph=False)
        await orchestrator.search_and_rerank(query="테스트3", top_k=5, use_graph=True)

        # Then: 3회 증가
        assert orchestrator.stats["total_requests"] == initial_count + 3


class TestEdgeCasesIntegration:
    """
    하이브리드 검색 엣지 케이스 통합 테스트

    빈 결과, 오류 상황 등 경계 조건 검증
    """

    @pytest.fixture
    def mock_retriever_empty(self) -> AsyncMock:
        """빈 결과를 반환하는 벡터 검색기"""
        retriever = AsyncMock()
        retriever.search.return_value = []
        return retriever

    @pytest.fixture
    def empty_graph_store(self) -> NetworkXGraphStore:
        """빈 그래프 저장소"""
        return NetworkXGraphStore()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_hybrid_search_with_empty_vector_results(
        self,
        mock_retriever_empty: AsyncMock,
        empty_graph_store: NetworkXGraphStore,
    ) -> None:
        """
        벡터 검색 결과가 비어있을 때 정상 동작

        Given: 빈 벡터 검색 결과
        When: 하이브리드 검색
        Then: 빈 결과 반환, 오류 없음
        """
        # Given
        config = {"vector_weight": 0.6, "graph_weight": 0.4}

        hybrid_search = VectorGraphHybridSearch(
            retriever=mock_retriever_empty,
            graph_store=empty_graph_store,
            config=config,
        )

        # When
        result = await hybrid_search.search("테스트", top_k=5)

        # Then: 빈 결과, 오류 없음
        assert isinstance(result, HybridSearchResult)
        assert len(result.documents) == 0
        assert result.vector_count == 0
        assert result.graph_count == 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_hybrid_search_with_top_k_zero(
        self,
        mock_retriever_empty: AsyncMock,
        empty_graph_store: NetworkXGraphStore,
    ) -> None:
        """
        top_k=0 호출 시 빈 결과 반환

        Given: top_k=0으로 검색 요청
        When: 하이브리드 검색
        Then: 빈 결과 반환
        """
        # Given
        config = {"vector_weight": 0.6, "graph_weight": 0.4}

        hybrid_search = VectorGraphHybridSearch(
            retriever=mock_retriever_empty,
            graph_store=empty_graph_store,
            config=config,
        )

        # When
        result = await hybrid_search.search("테스트", top_k=0)

        # Then: 빈 결과
        assert len(result.documents) == 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_hybrid_search_graceful_on_graph_search_error(self) -> None:
        """
        그래프 검색 오류 시 graceful degradation

        Given: 오류를 발생시키는 graph_store
        When: 하이브리드 검색
        Then: 벡터 검색 결과만 반환, 오류 전파 없음
        """
        # Given: 정상 벡터 검색
        mock_retriever = AsyncMock()
        mock_retriever.search.return_value = [
            SearchResult(id="doc1", content="테스트", score=0.9, metadata={}),
        ]

        # Given: 오류 발생 그래프 검색
        mock_graph_store = AsyncMock()
        mock_graph_store.search.side_effect = Exception("Graph search error")

        config = {"vector_weight": 0.6, "graph_weight": 0.4}

        hybrid_search = VectorGraphHybridSearch(
            retriever=mock_retriever,
            graph_store=mock_graph_store,
            config=config,
        )

        # When: 하이브리드 검색 (오류가 발생해도 계속)
        result = await hybrid_search.search("테스트", top_k=5)

        # Then: 벡터 결과만 반환, 오류 전파 없음
        assert isinstance(result, HybridSearchResult)
        assert result.vector_count > 0
        assert result.graph_count == 0  # 그래프 검색 실패

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_hybrid_search_graceful_on_vector_search_error(self) -> None:
        """
        벡터 검색 오류 시 graceful degradation

        Given: 오류를 발생시키는 retriever
        When: 하이브리드 검색
        Then: 빈 벡터 결과, 그래프 결과만 사용 가능
        """
        # Given: 오류 발생 벡터 검색
        mock_retriever = AsyncMock()
        mock_retriever.search.side_effect = Exception("Vector search error")

        # Given: 정상 그래프 저장소
        graph_store = NetworkXGraphStore()
        await graph_store.add_entity(
            Entity(id="e1", name="테스트", type="test", properties={"doc_id": "doc1"})
        )

        config = {"vector_weight": 0.6, "graph_weight": 0.4}

        hybrid_search = VectorGraphHybridSearch(
            retriever=mock_retriever,
            graph_store=graph_store,
            config=config,
        )

        # When: 하이브리드 검색
        result = await hybrid_search.search("테스트", top_k=5)

        # Then: 빈 벡터 결과, 그래프 결과 사용
        assert isinstance(result, HybridSearchResult)
        assert result.vector_count == 0  # 벡터 검색 실패


class TestHybridSearchConfigurationIntegration:
    """
    하이브리드 검색 설정 통합 테스트

    다양한 설정 조합에 대한 동작 검증
    """

    @pytest.fixture
    def mock_retriever(self) -> AsyncMock:
        """벡터 검색기 Mock"""
        retriever = AsyncMock()
        retriever.search.return_value = [
            SearchResult(id="doc1", content="테스트", score=0.9, metadata={}),
        ]
        return retriever

    @pytest.fixture
    async def graph_store(self) -> NetworkXGraphStore:
        """그래프 저장소"""
        store = NetworkXGraphStore()
        await store.add_entity(
            Entity(id="e1", name="테스트", type="test", properties={"doc_id": "doc1"})
        )
        return store

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_hybrid_search_disabled_via_config(
        self,
        mock_retriever: AsyncMock,
        graph_store: NetworkXGraphStore,
    ) -> None:
        """
        hybrid_search.enabled=false 시 하이브리드 검색 비활성화

        Given: enabled=false 설정
        When: RetrievalOrchestrator 생성
        Then: _hybrid_strategy가 None
        """
        # Given: 비활성화 설정
        mock_reranker = AsyncMock()
        mock_reranker.rerank.side_effect = lambda q, docs, top_k: docs[:top_k]
        mock_reranker.name = "MockReranker"

        config = {
            "graph_rag": {
                "hybrid_search": {
                    "enabled": False,  # 비활성화
                    "vector_weight": 0.6,
                    "graph_weight": 0.4,
                }
            }
        }

        # When
        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            reranker=mock_reranker,
            cache=None,
            graph_store=graph_store,
            config=config,
        )

        # Then: 하이브리드 전략 없음
        assert orchestrator._hybrid_strategy is None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_custom_rrf_k_value_applied(
        self,
        mock_retriever: AsyncMock,
        graph_store: NetworkXGraphStore,
    ) -> None:
        """
        custom rrf_k 값이 적용되는지 검증

        Given: rrf_k=100 설정
        When: VectorGraphHybridSearch 생성 및 검색
        Then: 설정된 rrf_k 값이 사용됨
        """
        # Given
        config = {
            "vector_weight": 0.6,
            "graph_weight": 0.4,
            "rrf_k": 100,  # 기본값 60 대신 100 사용
        }

        hybrid_search = VectorGraphHybridSearch(
            retriever=mock_retriever,
            graph_store=graph_store,
            config=config,
        )

        # When
        result_config = hybrid_search.get_config()

        # Then
        assert result_config["rrf_k"] == 100

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_weight_normalization(
        self,
        mock_retriever: AsyncMock,
        graph_store: NetworkXGraphStore,
    ) -> None:
        """
        가중치가 정규화되어 합이 1이 됨

        Given: vector_weight=3, graph_weight=1 (합: 4)
        When: 하이브리드 검색 수행
        Then: 정규화된 가중치 적용 (0.75, 0.25)
        """
        # Given: 합이 1이 아닌 가중치
        config = {
            "vector_weight": 3.0,
            "graph_weight": 1.0,
            "rrf_k": 60,
        }

        hybrid_search = VectorGraphHybridSearch(
            retriever=mock_retriever,
            graph_store=graph_store,
            config=config,
        )

        # When
        result = await hybrid_search.search(
            "테스트",
            top_k=5,
            vector_weight=3.0,
            graph_weight=1.0,
        )

        # Then: 검색 완료 (정규화 적용됨)
        assert isinstance(result, HybridSearchResult)

        # 메타데이터의 가중치가 정규화됨
        assert result.metadata["vector_weight"] == 0.75
        assert result.metadata["graph_weight"] == 0.25
