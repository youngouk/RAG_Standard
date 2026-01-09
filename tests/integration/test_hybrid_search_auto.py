"""
하이브리드 검색 자동 활성화 통합 테스트
설정만으로 하이브리드 검색이 자동 활성화되는지 검증
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.core.retrieval.interfaces import SearchResult
from app.modules.core.retrieval.orchestrator import RetrievalOrchestrator


class TestHybridSearchAutoIntegration:
    """하이브리드 검색 자동 활성화 통합 테스트"""

    @pytest.fixture
    def mock_retriever(self):
        """Mock Retriever"""
        retriever = MagicMock()
        retriever.search = AsyncMock(return_value=[
            SearchResult(
                id="vec-1",
                content="벡터 검색 결과",
                score=0.9,
                metadata={"source": "vector"},
            )
        ])
        return retriever

    @pytest.fixture
    def mock_graph_store(self):
        """Mock GraphStore"""
        store = MagicMock()
        store.search = AsyncMock(return_value=[])
        return store

    @pytest.fixture
    def mock_hybrid_strategy(self):
        """Mock HybridStrategy"""
        strategy = MagicMock()
        strategy.search = AsyncMock(return_value=MagicMock(
            documents=[
                SearchResult(
                    id="hybrid-1",
                    content="하이브리드 검색 결과",
                    score=0.95,
                    metadata={"source": "hybrid"},
                )
            ],
            vector_count=1,
            graph_count=0,
        ))
        return strategy

    @pytest.fixture
    def auto_enabled_config(self):
        """auto_enable=true 설정"""
        return {
            "graph_rag": {
                "hybrid_search": {
                    "enabled": True,
                    "auto_enable": True,  # 자동 활성화
                    "vector_weight": 0.6,
                    "graph_weight": 0.4,
                }
            }
        }

    @pytest.fixture
    def auto_disabled_config(self):
        """auto_enable=false 설정"""
        return {
            "graph_rag": {
                "hybrid_search": {
                    "enabled": True,
                    "auto_enable": False,  # 자동 비활성화
                    "vector_weight": 0.6,
                    "graph_weight": 0.4,
                }
            }
        }

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_auto_enable_activates_hybrid_search(
        self, mock_retriever, mock_graph_store, mock_hybrid_strategy, auto_enabled_config
    ):
        """
        E2E: auto_enable=true 시 use_graph=None으로 호출해도 하이브리드 검색 실행
        """
        # Given
        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            graph_store=mock_graph_store,
            hybrid_strategy=mock_hybrid_strategy,
            config=auto_enabled_config,
        )

        # When - use_graph 미지정 (None = 자동 결정)
        results = await orchestrator.search_and_rerank("테스트 쿼리")

        # Then
        assert orchestrator._auto_use_graph is True
        mock_hybrid_strategy.search.assert_called_once()
        mock_retriever.search.assert_not_called()
        assert len(results) == 1
        assert results[0].metadata.get("source") == "hybrid"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_auto_disable_uses_vector_only(
        self, mock_retriever, mock_graph_store, mock_hybrid_strategy, auto_disabled_config
    ):
        """
        E2E: auto_enable=false 시 use_graph=None으로 호출하면 벡터 검색만 실행
        """
        # Given
        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            graph_store=mock_graph_store,
            hybrid_strategy=mock_hybrid_strategy,
            config=auto_disabled_config,
        )

        # When - use_graph 미지정 (None = 자동 결정 → auto_enable=false이므로 벡터만)
        results = await orchestrator.search_and_rerank("테스트 쿼리")

        # Then
        assert orchestrator._auto_use_graph is False
        mock_retriever.search.assert_called_once()
        mock_hybrid_strategy.search.assert_not_called()
        assert len(results) == 1
        assert results[0].metadata.get("source") == "vector"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_explicit_use_graph_overrides_auto(
        self, mock_retriever, mock_graph_store, mock_hybrid_strategy, auto_disabled_config
    ):
        """
        E2E: use_graph=True 명시 시 auto_enable 설정 무시하고 하이브리드 검색 실행
        """
        # Given
        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            graph_store=mock_graph_store,
            hybrid_strategy=mock_hybrid_strategy,
            config=auto_disabled_config,  # auto_enable=false
        )

        # When - use_graph=True 명시
        await orchestrator.search_and_rerank("테스트 쿼리", use_graph=True)

        # Then
        mock_hybrid_strategy.search.assert_called_once()
        mock_retriever.search.assert_not_called()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_explicit_use_graph_false_overrides_auto(
        self, mock_retriever, mock_graph_store, mock_hybrid_strategy, auto_enabled_config
    ):
        """
        E2E: use_graph=False 명시 시 auto_enable=true여도 벡터 검색만 실행
        """
        # Given
        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            graph_store=mock_graph_store,
            hybrid_strategy=mock_hybrid_strategy,
            config=auto_enabled_config,  # auto_enable=true
        )

        # When - use_graph=False 명시
        await orchestrator.search_and_rerank("테스트 쿼리", use_graph=False)

        # Then
        mock_retriever.search.assert_called_once()
        mock_hybrid_strategy.search.assert_not_called()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_stats_tracks_hybrid_search_count(
        self, mock_retriever, mock_graph_store, mock_hybrid_strategy, auto_enabled_config
    ):
        """
        E2E: 하이브리드 검색 횟수가 통계에 기록되는지 확인
        """
        # Given
        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            graph_store=mock_graph_store,
            hybrid_strategy=mock_hybrid_strategy,
            config=auto_enabled_config,
        )

        # When - 3번 검색
        await orchestrator.search_and_rerank("쿼리 1")
        await orchestrator.search_and_rerank("쿼리 2")
        await orchestrator.search_and_rerank("쿼리 3")

        # Then
        assert orchestrator.stats["hybrid_search_count"] == 3
        assert orchestrator.stats["total_requests"] == 3
