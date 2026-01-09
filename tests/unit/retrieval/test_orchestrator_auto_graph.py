"""
Orchestrator 자동 하이브리드 검색 테스트
YAML 설정 기반 use_graph 자동 결정 검증
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.core.retrieval.orchestrator import RetrievalOrchestrator


class TestOrchestratorAutoGraph:
    """자동 하이브리드 검색 활성화 테스트"""

    @pytest.fixture
    def mock_retriever(self):
        """Mock Retriever"""
        retriever = MagicMock()
        retriever.search = AsyncMock(return_value=[])
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
            documents=[],
            vector_count=0,
            graph_count=0,
        ))
        return strategy

    def test_auto_use_graph_enabled_when_config_true(
        self, mock_retriever, mock_graph_store, mock_hybrid_strategy
    ):
        """auto_enable=true 시 _auto_use_graph=True"""
        config = {
            "graph_rag": {
                "hybrid_search": {
                    "enabled": True,
                    "auto_enable": True,
                }
            }
        }
        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            graph_store=mock_graph_store,
            hybrid_strategy=mock_hybrid_strategy,
            config=config,
        )
        assert orchestrator._auto_use_graph is True

    def test_auto_use_graph_disabled_when_config_false(
        self, mock_retriever, mock_graph_store, mock_hybrid_strategy
    ):
        """auto_enable=false 시 _auto_use_graph=False"""
        config = {
            "graph_rag": {
                "hybrid_search": {
                    "enabled": True,
                    "auto_enable": False,
                }
            }
        }
        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            graph_store=mock_graph_store,
            hybrid_strategy=mock_hybrid_strategy,
            config=config,
        )
        assert orchestrator._auto_use_graph is False

    def test_auto_use_graph_disabled_when_no_hybrid_strategy(
        self, mock_retriever
    ):
        """hybrid_strategy가 없으면 _auto_use_graph=False"""
        config = {
            "graph_rag": {
                "hybrid_search": {
                    "enabled": True,
                    "auto_enable": True,
                }
            }
        }
        # hybrid_strategy=None, graph_store=None
        # (graph_store가 있으면 자동으로 VectorGraphHybridSearch 생성됨)
        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            graph_store=None,  # 그래프 저장소도 없음
            hybrid_strategy=None,
            config=config,
        )
        # hybrid_strategy가 없으면 False
        assert orchestrator._auto_use_graph is False

    def test_auto_use_graph_disabled_when_hybrid_disabled(
        self, mock_retriever, mock_graph_store, mock_hybrid_strategy
    ):
        """hybrid_search.enabled=false 시 _auto_use_graph=False"""
        config = {
            "graph_rag": {
                "hybrid_search": {
                    "enabled": False,  # 비활성화
                    "auto_enable": True,
                }
            }
        }
        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            graph_store=mock_graph_store,
            hybrid_strategy=mock_hybrid_strategy,
            config=config,
        )
        assert orchestrator._auto_use_graph is False

    @pytest.mark.asyncio
    async def test_search_with_use_graph_none_uses_auto(
        self, mock_retriever, mock_graph_store, mock_hybrid_strategy
    ):
        """use_graph=None 시 auto_use_graph 값 사용"""
        config = {
            "graph_rag": {
                "hybrid_search": {
                    "enabled": True,
                    "auto_enable": True,
                }
            }
        }
        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            graph_store=mock_graph_store,
            hybrid_strategy=mock_hybrid_strategy,
            config=config,
        )

        # use_graph=None으로 호출
        await orchestrator.search_and_rerank("test query", use_graph=None)

        # auto_enable=true이므로 하이브리드 검색 실행
        mock_hybrid_strategy.search.assert_called_once()
        mock_retriever.search.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_with_use_graph_false_overrides_auto(
        self, mock_retriever, mock_graph_store, mock_hybrid_strategy
    ):
        """use_graph=False 시 auto 무시, 벡터 검색만 사용"""
        config = {
            "graph_rag": {
                "hybrid_search": {
                    "enabled": True,
                    "auto_enable": True,
                }
            }
        }
        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            graph_store=mock_graph_store,
            hybrid_strategy=mock_hybrid_strategy,
            config=config,
        )

        # use_graph=False 명시
        await orchestrator.search_and_rerank("test query", use_graph=False)

        # 벡터 검색만 실행
        mock_retriever.search.assert_called_once()
        mock_hybrid_strategy.search.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_with_use_graph_true_overrides_auto(
        self, mock_retriever, mock_graph_store, mock_hybrid_strategy
    ):
        """use_graph=True 시 auto가 False여도 하이브리드 검색 사용"""
        config = {
            "graph_rag": {
                "hybrid_search": {
                    "enabled": True,
                    "auto_enable": False,  # 자동 비활성화
                }
            }
        }
        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            graph_store=mock_graph_store,
            hybrid_strategy=mock_hybrid_strategy,
            config=config,
        )

        # use_graph=True 명시
        await orchestrator.search_and_rerank("test query", use_graph=True)

        # 하이브리드 검색 실행
        mock_hybrid_strategy.search.assert_called_once()
        mock_retriever.search.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_without_use_graph_and_auto_disabled(
        self, mock_retriever, mock_graph_store, mock_hybrid_strategy
    ):
        """use_graph 미지정 + auto_enable=false 시 벡터 검색만"""
        config = {
            "graph_rag": {
                "hybrid_search": {
                    "enabled": True,
                    "auto_enable": False,
                }
            }
        }
        orchestrator = RetrievalOrchestrator(
            retriever=mock_retriever,
            graph_store=mock_graph_store,
            hybrid_strategy=mock_hybrid_strategy,
            config=config,
        )

        # use_graph 미지정 (기본값 None 또는 False)
        await orchestrator.search_and_rerank("test query")

        # auto_enable=false이므로 벡터 검색만 실행
        mock_retriever.search.assert_called_once()
        mock_hybrid_strategy.search.assert_not_called()
