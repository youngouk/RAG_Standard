"""
RerankerFactory 단위 테스트

설정 기반 리랭커 생성 검증.
TDD 방식으로 작성 - 테스트 먼저, 구현 나중.
"""

from unittest.mock import patch

import pytest


class TestRerankerFactory:
    """RerankerFactory 테스트"""

    def test_supported_rerankers_registry_exists(self):
        """지원 리랭커 레지스트리가 존재하는지 확인"""
        from app.modules.core.retrieval.rerankers.factory import SUPPORTED_RERANKERS

        assert isinstance(SUPPORTED_RERANKERS, dict)
        assert len(SUPPORTED_RERANKERS) > 0

    def test_get_supported_rerankers(self):
        """지원 리랭커 목록 조회"""
        from app.modules.core.retrieval.rerankers.factory import RerankerFactory

        rerankers = RerankerFactory.get_supported_rerankers()
        assert "gemini-flash" in rerankers
        assert "jina" in rerankers
        assert "jina-colbert" in rerankers

    def test_list_rerankers_by_type(self):
        """타입별 리랭커 목록 조회"""
        from app.modules.core.retrieval.rerankers.factory import RerankerFactory

        # LLM 타입 리랭커
        llm_rerankers = RerankerFactory.list_rerankers_by_type("llm")
        assert "gemini-flash" in llm_rerankers

        # API 타입 리랭커
        api_rerankers = RerankerFactory.list_rerankers_by_type("api")
        assert "jina" in api_rerankers

        # ColBERT 타입 리랭커
        colbert_rerankers = RerankerFactory.list_rerankers_by_type("colbert")
        assert "jina-colbert" in colbert_rerankers

    def test_get_reranker_info(self):
        """특정 리랭커 정보 조회"""
        from app.modules.core.retrieval.rerankers.factory import RerankerFactory

        # Gemini Flash 정보 조회
        gemini_info = RerankerFactory.get_reranker_info("gemini-flash")
        assert gemini_info is not None
        assert gemini_info["type"] == "llm"
        assert "default_config" in gemini_info

        # 존재하지 않는 리랭커
        invalid_info = RerankerFactory.get_reranker_info("invalid-reranker")
        assert invalid_info is None

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"})
    def test_create_gemini_reranker(self):
        """Gemini 리랭커 생성 테스트"""
        from app.modules.core.retrieval.rerankers.factory import RerankerFactory

        config = {
            "reranking": {
                "provider": "gemini-flash",
                "gemini": {
                    "model": "gemini-flash-lite-latest",
                    "max_documents": 20,
                    "timeout": 15,
                },
            }
        }
        reranker = RerankerFactory.create(config)
        assert reranker is not None
        assert reranker.__class__.__name__ == "GeminiFlashReranker"

    @patch.dict("os.environ", {"JINA_API_KEY": "test-key"})
    def test_create_jina_reranker(self):
        """Jina 리랭커 생성 테스트"""
        from app.modules.core.retrieval.rerankers.factory import RerankerFactory

        config = {
            "reranking": {
                "provider": "jina",
                "jina": {
                    "model": "jina-reranker-v2-base-multilingual",
                },
            }
        }
        reranker = RerankerFactory.create(config)
        assert reranker is not None
        assert reranker.__class__.__name__ == "JinaReranker"

    @patch.dict("os.environ", {"JINA_API_KEY": "test-key"})
    def test_create_colbert_reranker(self):
        """ColBERT 리랭커 생성 테스트"""
        from app.modules.core.retrieval.rerankers.factory import RerankerFactory

        config = {
            "reranking": {
                "provider": "jina-colbert",
                "colbert": {
                    "model": "jina-colbert-v2",
                    "top_n": 10,
                },
            }
        }
        reranker = RerankerFactory.create(config)
        assert reranker is not None
        assert reranker.__class__.__name__ == "JinaColBERTReranker"

    def test_create_with_invalid_provider_raises_error(self):
        """유효하지 않은 프로바이더로 생성 시 에러"""
        from app.modules.core.retrieval.rerankers.factory import RerankerFactory

        config = {
            "reranking": {
                "provider": "invalid-provider",
            }
        }
        with pytest.raises(ValueError, match="지원하지 않는 리랭커"):
            RerankerFactory.create(config)

    @patch.dict("os.environ", {}, clear=True)
    def test_create_gemini_without_api_key_raises_error(self):
        """API 키 없이 Gemini 리랭커 생성 시 에러"""
        from app.modules.core.retrieval.rerankers.factory import RerankerFactory

        # GOOGLE_API_KEY가 없는 환경에서
        config = {
            "reranking": {
                "provider": "gemini-flash",
            }
        }
        with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
            RerankerFactory.create(config)

    @patch.dict("os.environ", {}, clear=True)
    def test_create_jina_without_api_key_raises_error(self):
        """API 키 없이 Jina 리랭커 생성 시 에러"""
        from app.modules.core.retrieval.rerankers.factory import RerankerFactory

        config = {
            "reranking": {
                "provider": "jina",
            }
        }
        with pytest.raises(ValueError, match="JINA_API_KEY"):
            RerankerFactory.create(config)

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"})
    def test_create_with_default_provider(self):
        """프로바이더 미지정 시 기본값(gemini-flash) 사용"""
        from app.modules.core.retrieval.rerankers.factory import RerankerFactory

        # provider가 없는 설정
        config = {"reranking": {}}
        reranker = RerankerFactory.create(config)
        assert reranker.__class__.__name__ == "GeminiFlashReranker"

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"})
    def test_create_uses_default_config_when_not_specified(self):
        """세부 설정 미지정 시 기본값 사용"""
        from app.modules.core.retrieval.rerankers.factory import RerankerFactory

        config = {
            "reranking": {
                "provider": "gemini-flash",
                # gemini 섹션 생략 - 기본값 사용해야 함
            }
        }
        reranker = RerankerFactory.create(config)
        assert reranker is not None
        # 기본 모델명 확인
        assert reranker.model == "gemini-flash-lite-latest"
