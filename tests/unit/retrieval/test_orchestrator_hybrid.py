"""
RetrievalOrchestrator 하이브리드 검색 통합 테스트

벡터+그래프 하이브리드 검색이 RetrievalOrchestrator와
올바르게 통합되는지 테스트합니다.

테스트 카테고리:
- Init: graph_store, hybrid_strategy 파라미터 초기화 테스트
- HybridSearch: use_graph=True로 하이브리드 검색 테스트
- BackwardCompatibility: 기존 코드와의 호환성 테스트

생성일: 2026-01-05
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.core.graph.interfaces import Entity, GraphSearchResult
from app.modules.core.retrieval.interfaces import IRetriever, SearchResult
from app.modules.core.retrieval.orchestrator import RetrievalOrchestrator


class TestOrchestratorHybridInit:
    """RetrievalOrchestrator 하이브리드 검색 초기화 테스트"""

    def test_init_with_graph_store_creates_hybrid_strategy(self) -> None:
        """graph_store 제공 시 하이브리드 전략 자동 생성"""
        # Given
        mock_retriever = MagicMock(spec=IRetriever)
        mock_graph_store = MagicMock()

        config: dict[str, Any] = {
            "hybrid_search": {
                "enabled": True,
                "vector_weight": 0.6,
                "graph_weight": 0.4,
            }
        }

        # When
        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            graph_store=mock_graph_store,
            config=config,
        )

        # Then
        assert orchestrator.graph_store is mock_graph_store
        assert orchestrator._hybrid_strategy is not None

    def test_init_with_hybrid_strategy_direct_injection(self) -> None:
        """hybrid_strategy 직접 주입 시 우선 사용"""
        # Given
        mock_retriever = MagicMock(spec=IRetriever)
        mock_graph_store = MagicMock()
        mock_hybrid_strategy = MagicMock()

        # When
        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            graph_store=mock_graph_store,
            hybrid_strategy=mock_hybrid_strategy,
            config={},
        )

        # Then - 직접 주입된 전략 사용
        assert orchestrator._hybrid_strategy is mock_hybrid_strategy

    def test_init_without_graph_store_no_hybrid_strategy(self) -> None:
        """graph_store 없으면 하이브리드 전략 없음"""
        # Given
        mock_retriever = MagicMock(spec=IRetriever)

        # When
        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            graph_store=None,
            config={},
        )

        # Then
        assert orchestrator.graph_store is None
        assert orchestrator._hybrid_strategy is None

    def test_init_with_hybrid_disabled_in_config(self) -> None:
        """config에서 hybrid_search.enabled=False면 전략 생성 안 함"""
        # Given
        mock_retriever = MagicMock(spec=IRetriever)
        mock_graph_store = MagicMock()

        # graph_rag.hybrid_search 구조 사용 (YAML 설정 구조)
        config: dict[str, Any] = {
            "graph_rag": {
                "hybrid_search": {
                    "enabled": False,  # 명시적 비활성화
                }
            }
        }

        # When
        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            graph_store=mock_graph_store,
            config=config,
        )

        # Then - graph_store는 있지만 전략은 없음
        assert orchestrator.graph_store is mock_graph_store
        assert orchestrator._hybrid_strategy is None

    def test_stats_includes_hybrid_search_count(self) -> None:
        """통계에 hybrid_search_count 포함"""
        # Given
        mock_retriever = MagicMock(spec=IRetriever)

        # When
        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            config={},
        )

        # Then
        assert "hybrid_search_count" in orchestrator.stats
        assert orchestrator.stats["hybrid_search_count"] == 0


class TestOrchestratorHybridSearch:
    """RetrievalOrchestrator 하이브리드 검색 테스트"""

    @pytest.fixture
    def mock_retriever(self) -> AsyncMock:
        """Mock Retriever"""
        mock = AsyncMock(spec=IRetriever)
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
        ]
        return mock

    @pytest.fixture
    def mock_graph_store(self) -> AsyncMock:
        """Mock GraphStore"""
        mock = AsyncMock()
        mock.search.return_value = GraphSearchResult(
            entities=[
                Entity(
                    id="e1",
                    name="강남 A식당",
                    type="company",
                    properties={"doc_id": "doc1"},
                ),
            ],
            relations=[],
            score=0.85,
        )
        return mock

    @pytest.fixture
    def mock_reranker(self) -> AsyncMock:
        """Mock Reranker"""
        mock = AsyncMock()
        mock.rerank.side_effect = lambda q, docs, top_k: docs[:top_k]
        return mock

    @pytest.mark.asyncio
    async def test_search_with_use_graph_true(
        self, mock_retriever: AsyncMock, mock_graph_store: AsyncMock
    ) -> None:
        """use_graph=True로 하이브리드 검색 수행"""
        # Given
        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            graph_store=mock_graph_store,
            config={
                "hybrid_search": {
                    "enabled": True,
                    "vector_weight": 0.6,
                    "graph_weight": 0.4,
                }
            },
        )

        # When
        results = await orchestrator.search_and_rerank(
            query="강남 맛집",
            top_k=5,
            use_graph=True,
        )

        # Then
        assert len(results) > 0
        assert orchestrator.stats["hybrid_search_count"] == 1
        # 벡터 검색도 호출됨 (하이브리드 전략 내부)
        mock_retriever.search.assert_called()

    @pytest.mark.asyncio
    async def test_search_with_use_graph_false(
        self, mock_retriever: AsyncMock, mock_graph_store: AsyncMock
    ) -> None:
        """use_graph=False로 벡터 검색만 수행"""
        # Given
        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            graph_store=mock_graph_store,
            config={"hybrid_search": {"enabled": True}},
        )

        # When
        results = await orchestrator.search_and_rerank(
            query="강남 맛집",
            top_k=5,
            use_graph=False,  # 그래프 검색 비활성화
        )

        # Then
        assert len(results) > 0
        assert orchestrator.stats["hybrid_search_count"] == 0  # 하이브리드 검색 안 함
        assert orchestrator.stats["retrieval_count"] == 1  # 벡터 검색만

    @pytest.mark.asyncio
    async def test_search_without_hybrid_strategy(
        self, mock_retriever: AsyncMock
    ) -> None:
        """하이브리드 전략 없으면 use_graph=True여도 벡터 검색만"""
        # Given - graph_store 없음
        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            graph_store=None,
            config={},
        )

        # When
        results = await orchestrator.search_and_rerank(
            query="강남 맛집",
            top_k=5,
            use_graph=True,  # 하지만 전략이 없어서 벡터 검색만 수행
        )

        # Then
        assert len(results) > 0
        assert orchestrator.stats["hybrid_search_count"] == 0
        assert orchestrator.stats["retrieval_count"] == 1

    @pytest.mark.asyncio
    async def test_search_with_reranking_after_hybrid(
        self,
        mock_retriever: AsyncMock,
        mock_graph_store: AsyncMock,
        mock_reranker: AsyncMock,
    ) -> None:
        """하이브리드 검색 후 리랭킹 수행"""
        # Given
        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            reranker=mock_reranker,
            graph_store=mock_graph_store,
            config={"hybrid_search": {"enabled": True}},
        )

        # When
        results = await orchestrator.search_and_rerank(
            query="강남 맛집",
            top_k=5,
            use_graph=True,
            rerank_enabled=True,
        )

        # Then
        assert len(results) > 0
        mock_reranker.rerank.assert_called_once()

    @pytest.mark.asyncio
    async def test_hybrid_search_results_format(
        self, mock_retriever: AsyncMock, mock_graph_store: AsyncMock
    ) -> None:
        """하이브리드 검색 결과가 SearchResult 형식"""
        # Given
        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            graph_store=mock_graph_store,
            config={"hybrid_search": {"enabled": True}},
        )

        # When
        results = await orchestrator.search_and_rerank(
            query="강남",
            top_k=5,
            use_graph=True,
        )

        # Then - 모든 결과가 SearchResult 타입
        for result in results:
            assert isinstance(result, SearchResult)
            assert hasattr(result, "id")
            assert hasattr(result, "content")
            assert hasattr(result, "score")


class TestOrchestratorBackwardCompatibility:
    """RetrievalOrchestrator 하위 호환성 테스트"""

    @pytest.fixture
    def mock_retriever(self) -> AsyncMock:
        """Mock Retriever"""
        mock = AsyncMock(spec=IRetriever)
        mock.search.return_value = [
            SearchResult(
                id="doc1",
                content="테스트 문서",
                score=0.9,
                metadata={},
            ),
        ]
        return mock

    @pytest.mark.asyncio
    async def test_existing_code_works_without_graph_params(
        self, mock_retriever: AsyncMock
    ) -> None:
        """기존 코드가 새 파라미터 없이도 동작"""
        # Given - 기존 방식으로 초기화
        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            reranker=None,
            cache=None,
        )

        # When - 기존 방식으로 검색
        results = await orchestrator.search_and_rerank(
            query="테스트",
            top_k=5,
        )

        # Then - 정상 동작
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_search_method_adapter_works(
        self, mock_retriever: AsyncMock
    ) -> None:
        """레거시 search() 어댑터 정상 동작"""
        # Given
        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            config={},
        )

        # When - 레거시 인터페이스 사용
        results = await orchestrator.search("테스트", {"limit": 5})

        # Then
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_default_use_graph_is_false(
        self, mock_retriever: AsyncMock
    ) -> None:
        """use_graph 기본값은 False"""
        # Given
        mock_graph_store = AsyncMock()

        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            graph_store=mock_graph_store,
            config={"hybrid_search": {"enabled": True}},
        )

        # When - use_graph 파라미터 없이 호출
        await orchestrator.search_and_rerank(
            query="테스트",
            top_k=5,
        )

        # Then - 벡터 검색만 수행 (use_graph 기본값 False)
        assert orchestrator.stats["hybrid_search_count"] == 0
        assert orchestrator.stats["retrieval_count"] == 1


class TestOrchestratorHybridWithCache:
    """RetrievalOrchestrator 하이브리드 검색 + 캐시 테스트"""

    @pytest.fixture
    def mock_cache(self) -> AsyncMock:
        """Mock CacheManager"""
        mock = AsyncMock()
        mock.get.return_value = None  # 캐시 미스
        mock.generate_cache_key.return_value = "test_cache_key"
        return mock

    @pytest.mark.asyncio
    async def test_hybrid_results_cached(self) -> None:
        """하이브리드 검색 결과도 캐시됨"""
        # Given
        mock_retriever = AsyncMock(spec=IRetriever)
        mock_retriever.search.return_value = [
            SearchResult(id="doc1", content="테스트", score=0.9, metadata={}),
        ]

        mock_graph_store = AsyncMock()
        mock_graph_store.search.return_value = GraphSearchResult(
            entities=[],
            relations=[],
            score=0.0,
        )

        mock_cache = AsyncMock()
        mock_cache.get.return_value = None
        mock_cache.generate_cache_key.return_value = "cache_key"

        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            cache=mock_cache,
            graph_store=mock_graph_store,
            config={"hybrid_search": {"enabled": True}},
        )

        # When
        await orchestrator.search_and_rerank(
            query="테스트",
            top_k=5,
            use_graph=True,
        )

        # Then - 캐시 저장 호출
        mock_cache.set.assert_called_once()
