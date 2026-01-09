# tests/unit/graph/extractors/test_llm_entity_extractor.py
"""
LLMEntityExtractor 단위 테스트
TDD: 먼저 테스트 작성, 실패 확인, 최소 구현
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.core.graph.models import Entity


class TestLLMEntityExtractorInit:
    """초기화 테스트"""

    def test_init_with_llm_client(self):
        """LLM 클라이언트로 초기화"""
        from app.modules.core.graph.extractors import LLMEntityExtractor

        mock_llm = MagicMock()
        extractor = LLMEntityExtractor(llm_client=mock_llm)

        assert extractor._llm_client is mock_llm

    def test_init_with_config(self):
        """설정으로 초기화"""
        from app.modules.core.graph.extractors import LLMEntityExtractor

        mock_llm = MagicMock()
        config = {"max_entities": 15, "model": "gemini-flash"}
        extractor = LLMEntityExtractor(llm_client=mock_llm, config=config)

        assert extractor._config["max_entities"] == 15


class TestLLMEntityExtractorExtract:
    """엔티티 추출 테스트"""

    @pytest.fixture
    def mock_llm_client(self):
        """LLM 응답 모킹"""
        client = MagicMock()
        client.generate = AsyncMock(return_value='''
        [
            {"name": "A 업체", "type": "company"},
            {"name": "서울", "type": "location"}
        ]
        ''')
        return client

    @pytest.mark.asyncio
    async def test_extract_entities_from_text(self, mock_llm_client):
        """텍스트에서 엔티티 추출"""
        from app.modules.core.graph.extractors import LLMEntityExtractor

        extractor = LLMEntityExtractor(llm_client=mock_llm_client)
        text = "A 업체는 서울에 위치한 회사입니다."

        entities = await extractor.extract(text)

        assert len(entities) == 2
        assert all(isinstance(e, Entity) for e in entities)
        assert entities[0].name == "A 업체"
        assert entities[0].type == "company"

    @pytest.mark.asyncio
    async def test_extract_empty_text_returns_empty_list(self, mock_llm_client):
        """빈 텍스트는 빈 리스트 반환"""
        from app.modules.core.graph.extractors import LLMEntityExtractor

        extractor = LLMEntityExtractor(llm_client=mock_llm_client)

        entities = await extractor.extract("")

        assert entities == []

    @pytest.mark.asyncio
    async def test_extract_handles_llm_error_gracefully(self):
        """LLM 오류 시 빈 리스트 반환 (graceful degradation)"""
        from app.modules.core.graph.extractors import LLMEntityExtractor

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(side_effect=Exception("API Error"))

        extractor = LLMEntityExtractor(llm_client=mock_llm)

        entities = await extractor.extract("테스트 텍스트")

        assert entities == []

    @pytest.mark.asyncio
    async def test_extract_handles_invalid_json(self):
        """잘못된 JSON 응답 처리"""
        from app.modules.core.graph.extractors import LLMEntityExtractor

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value="잘못된 JSON 응답")

        extractor = LLMEntityExtractor(llm_client=mock_llm)

        entities = await extractor.extract("테스트 텍스트")

        assert entities == []


class TestLLMEntityExtractorProtocol:
    """IEntityExtractor 프로토콜 준수 테스트"""

    def test_implements_protocol(self):
        """프로토콜 구현 확인"""
        from app.modules.core.graph.extractors import LLMEntityExtractor
        from app.modules.core.graph.interfaces import IEntityExtractor

        mock_llm = MagicMock()
        extractor = LLMEntityExtractor(llm_client=mock_llm)

        # runtime_checkable 프로토콜 확인
        assert isinstance(extractor, IEntityExtractor)
