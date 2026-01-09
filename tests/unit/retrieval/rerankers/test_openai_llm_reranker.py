"""
OpenAILLMReranker 단위 테스트

TDD 기반 개발:
- GPT5NanoReranker를 OpenAILLMReranker로 리팩토링
- 모델명 설정 가능 (기본값: gpt-5-nano)
- RerankerFactory 통합 테스트
"""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.core.retrieval.interfaces import SearchResult


class TestOpenAILLMRerankerInitialization:
    """OpenAILLMReranker 초기화 테스트"""

    def test_init_with_default_model(self):
        """기본 모델(gpt-5-nano)로 초기화"""
        from app.modules.core.retrieval.rerankers.openai_llm_reranker import (
            OpenAILLMReranker,
        )

        with patch("openai.OpenAI"):
            reranker = OpenAILLMReranker(api_key="test-key")
            assert reranker.model == "gpt-5-nano"
            assert reranker.max_documents == 20
            assert reranker.timeout == 15

    def test_init_with_custom_model(self):
        """커스텀 모델로 초기화"""
        from app.modules.core.retrieval.rerankers.openai_llm_reranker import (
            OpenAILLMReranker,
        )

        with patch("openai.OpenAI"):
            reranker = OpenAILLMReranker(
                api_key="test-key",
                model="gpt-4o-mini",
                max_documents=30,
                timeout=20,
            )
            assert reranker.model == "gpt-4o-mini"
            assert reranker.max_documents == 30
            assert reranker.timeout == 20

    def test_init_without_api_key_raises_error(self):
        """API 키 없이 초기화 시 에러 발생"""
        from app.modules.core.retrieval.rerankers.openai_llm_reranker import (
            OpenAILLMReranker,
        )

        with pytest.raises(ValueError, match="API key is required"):
            OpenAILLMReranker(api_key="")


class TestOpenAILLMRerankerRerank:
    """OpenAILLMReranker rerank 메서드 테스트"""

    @pytest.fixture
    def mock_reranker(self):
        """목 리랭커 생성"""
        from app.modules.core.retrieval.rerankers.openai_llm_reranker import (
            OpenAILLMReranker,
        )

        with patch("openai.OpenAI") as mock_client:
            reranker = OpenAILLMReranker(api_key="test-key")
            yield reranker, mock_client

    @pytest.fixture
    def sample_results(self):
        """샘플 검색 결과"""
        return [
            SearchResult(
                id="doc1",
                content="Python 프로그래밍 기초 가이드",
                score=0.8,
                metadata={"source": "tutorial"},
            ),
            SearchResult(
                id="doc2",
                content="머신러닝 입문 튜토리얼",
                score=0.7,
                metadata={"source": "ml"},
            ),
            SearchResult(
                id="doc3",
                content="웹 개발 베스트 프랙티스",
                score=0.6,
                metadata={"source": "web"},
            ),
        ]

    @pytest.mark.asyncio
    async def test_rerank_empty_results(self, mock_reranker):
        """빈 결과 리랭킹"""
        reranker, _ = mock_reranker
        result = await reranker.rerank(query="test", results=[], top_k=5)
        assert result == []

    @pytest.mark.asyncio
    async def test_rerank_preserves_original_on_error(self, mock_reranker, sample_results):
        """에러 발생 시 원본 결과 반환 (fail-safe)"""
        reranker, mock_client = mock_reranker

        # API 호출 에러 시뮬레이션
        MagicMock()
        mock_client.return_value.responses.create.side_effect = Exception("API Error")

        result = await reranker.rerank(
            query="Python 프로그래밍",
            results=sample_results,
            top_k=2,
        )

        # 원본 결과가 점수순으로 정렬되어 반환
        assert len(result) == 2
        assert result[0].id == "doc1"  # 최고 점수


class TestOpenAILLMRerankerStats:
    """통계 및 헬스체크 테스트"""

    def test_get_stats_returns_correct_structure(self):
        """통계 정보 구조 검증"""
        from app.modules.core.retrieval.rerankers.openai_llm_reranker import (
            OpenAILLMReranker,
        )

        with patch("openai.OpenAI"):
            reranker = OpenAILLMReranker(api_key="test-key", model="gpt-4o-mini")
            stats = reranker.get_stats()

            assert "provider" in stats
            assert stats["provider"] == "openai-llm"  # 변경된 provider 이름
            assert "model" in stats  # 모델 정보 추가
            assert stats["model"] == "gpt-4o-mini"
            assert "total_requests" in stats
            assert "successful_requests" in stats
            assert "failed_requests" in stats


class TestRerankerFactoryOpenAILLM:
    """RerankerFactory openai-llm 프로바이더 테스트"""

    def test_openai_llm_in_supported_rerankers(self):
        """openai-llm이 지원 리랭커 목록에 있는지 확인"""
        from app.modules.core.retrieval.rerankers.factory import RerankerFactory

        supported = RerankerFactory.get_supported_rerankers()
        assert "openai-llm" in supported

    def test_openai_llm_type_is_llm(self):
        """openai-llm 타입이 llm인지 확인"""
        from app.modules.core.retrieval.rerankers.factory import RerankerFactory

        llm_rerankers = RerankerFactory.list_rerankers_by_type("llm")
        assert "openai-llm" in llm_rerankers

    def test_create_openai_llm_reranker(self, monkeypatch):
        """Factory로 openai-llm 리랭커 생성"""
        from app.modules.core.retrieval.rerankers.factory import RerankerFactory
        from app.modules.core.retrieval.rerankers.openai_llm_reranker import (
            OpenAILLMReranker,
        )

        monkeypatch.setenv("OPENAI_API_KEY", "test-api-key")

        config = {
            "reranking": {
                "provider": "openai-llm",
                "openai_llm": {
                    "model": "gpt-4o-mini",
                    "max_documents": 25,
                    "timeout": 20,
                },
            }
        }

        with patch("openai.OpenAI"):
            reranker = RerankerFactory.create(config)
            assert isinstance(reranker, OpenAILLMReranker)
            assert reranker.model == "gpt-4o-mini"
            assert reranker.max_documents == 25

    def test_create_openai_llm_reranker_missing_api_key(self, monkeypatch):
        """API 키 없을 때 에러 발생"""
        from app.modules.core.retrieval.rerankers.factory import RerankerFactory

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        config = {
            "reranking": {
                "provider": "openai-llm",
            }
        }

        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            RerankerFactory.create(config)
