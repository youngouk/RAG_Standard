"""
KnowledgeGraphBuilder 단위 테스트
엔티티 추출 → 관계 추출 → 그래프 저장 파이프라인 검증
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.core.graph.models import Entity, Relation


class TestKnowledgeGraphBuilderInit:
    """초기화 테스트"""

    def test_init_with_components(self):
        """컴포넌트로 초기화"""
        from app.modules.core.graph.builder import KnowledgeGraphBuilder

        mock_store = MagicMock()
        mock_entity_extractor = MagicMock()
        mock_relation_extractor = MagicMock()

        builder = KnowledgeGraphBuilder(
            graph_store=mock_store,
            entity_extractor=mock_entity_extractor,
            relation_extractor=mock_relation_extractor,
        )

        assert builder._graph_store is mock_store


class TestKnowledgeGraphBuilderBuild:
    """그래프 빌드 테스트"""

    @pytest.fixture
    def mock_components(self):
        """모킹된 컴포넌트"""
        store = MagicMock()
        store.add_entity = AsyncMock()
        store.add_relation = AsyncMock()

        entity_extractor = MagicMock()
        entity_extractor.extract = AsyncMock(return_value=[
            Entity(id="e1", name="A", type="company"),
            Entity(id="e2", name="B", type="company"),
        ])

        relation_extractor = MagicMock()
        relation_extractor.extract = AsyncMock(return_value=[
            Relation(source_id="e1", target_id="e2", type="partnership"),
        ])

        return {
            "store": store,
            "entity_extractor": entity_extractor,
            "relation_extractor": relation_extractor,
        }

    @pytest.mark.asyncio
    async def test_build_from_text(self, mock_components):
        """텍스트에서 지식 그래프 빌드"""
        from app.modules.core.graph.builder import KnowledgeGraphBuilder

        builder = KnowledgeGraphBuilder(
            graph_store=mock_components["store"],
            entity_extractor=mock_components["entity_extractor"],
            relation_extractor=mock_components["relation_extractor"],
        )

        result = await builder.build("A와 B는 파트너입니다.")

        assert result["entities_count"] == 2
        assert result["relations_count"] == 1
        assert mock_components["store"].add_entity.call_count == 2
        assert mock_components["store"].add_relation.call_count == 1

    @pytest.mark.asyncio
    async def test_build_from_documents(self, mock_components):
        """여러 문서에서 지식 그래프 빌드"""
        from app.modules.core.graph.builder import KnowledgeGraphBuilder

        builder = KnowledgeGraphBuilder(
            graph_store=mock_components["store"],
            entity_extractor=mock_components["entity_extractor"],
            relation_extractor=mock_components["relation_extractor"],
        )

        documents = [
            {"content": "문서 1", "metadata": {"id": "doc1"}},
            {"content": "문서 2", "metadata": {"id": "doc2"}},
        ]

        result = await builder.build_from_documents(documents)

        assert result["documents_processed"] == 2
        # 각 문서마다 2 엔티티 × 2 문서 = 4 호출
        assert mock_components["store"].add_entity.call_count == 4
