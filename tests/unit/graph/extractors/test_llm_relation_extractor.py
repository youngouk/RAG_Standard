# tests/unit/graph/extractors/test_llm_relation_extractor.py
"""
LLMRelationExtractor 단위 테스트

TDD: 엔티티 간 관계 추출 검증
생성일: 2026-01-05
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.core.graph.models import Entity, Relation


class TestLLMRelationExtractorInit:
    """초기화 테스트"""

    def test_init_with_llm_client(self):
        """LLM 클라이언트로 초기화"""
        from app.modules.core.graph.extractors import LLMRelationExtractor

        mock_llm = MagicMock()
        extractor = LLMRelationExtractor(llm_client=mock_llm)

        assert extractor._llm_client is mock_llm


class TestLLMRelationExtractorExtract:
    """관계 추출 테스트"""

    @pytest.fixture
    def sample_entities(self):
        """샘플 엔티티"""
        return [
            Entity(id="e1", name="A 업체", type="company"),
            Entity(id="e2", name="B 업체", type="company"),
            Entity(id="e3", name="서울", type="location"),
        ]

    @pytest.fixture
    def mock_llm_client(self):
        """LLM 응답 모킹"""
        client = MagicMock()
        client.generate = AsyncMock(return_value='''
        [
            {"source": "A 업체", "target": "B 업체", "type": "partnership", "weight": 0.9},
            {"source": "A 업체", "target": "서울", "type": "located_in", "weight": 1.0}
        ]
        ''')
        return client

    @pytest.mark.asyncio
    async def test_extract_relations_from_text(self, mock_llm_client, sample_entities):
        """텍스트에서 관계 추출"""
        from app.modules.core.graph.extractors import LLMRelationExtractor

        extractor = LLMRelationExtractor(llm_client=mock_llm_client)
        text = "A 업체는 B 업체와 파트너십을 맺고 서울에 위치해 있습니다."

        relations = await extractor.extract(text, sample_entities)

        assert len(relations) == 2
        assert all(isinstance(r, Relation) for r in relations)
        assert relations[0].type == "partnership"

    @pytest.mark.asyncio
    async def test_extract_with_no_entities_returns_empty(self, mock_llm_client):
        """엔티티 없으면 빈 리스트 반환"""
        from app.modules.core.graph.extractors import LLMRelationExtractor

        extractor = LLMRelationExtractor(llm_client=mock_llm_client)

        relations = await extractor.extract("텍스트", [])

        assert relations == []

    @pytest.mark.asyncio
    async def test_extract_handles_llm_error_gracefully(self, sample_entities):
        """LLM 오류 시 빈 리스트 반환"""
        from app.modules.core.graph.extractors import LLMRelationExtractor

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(side_effect=Exception("API Error"))

        extractor = LLMRelationExtractor(llm_client=mock_llm)

        relations = await extractor.extract("텍스트", sample_entities)

        assert relations == []


class TestLLMRelationExtractorProtocol:
    """IRelationExtractor 프로토콜 준수 테스트"""

    def test_implements_protocol(self):
        """프로토콜 구현 확인"""
        from app.modules.core.graph.extractors import LLMRelationExtractor
        from app.modules.core.graph.interfaces import IRelationExtractor

        mock_llm = MagicMock()
        extractor = LLMRelationExtractor(llm_client=mock_llm)

        assert isinstance(extractor, IRelationExtractor)
