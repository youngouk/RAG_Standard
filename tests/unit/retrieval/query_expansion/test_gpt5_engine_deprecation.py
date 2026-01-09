"""
GPT5QueryExpansionEngine llm_factory 필수화 테스트

Phase 2.0: llm_factory 필수 파라미터 검증
- llm_factory 없이 초기화 시 ValueError 발생
- llm_factory와 함께 초기화 시 정상 동작
"""

from unittest.mock import MagicMock

import pytest


class TestGPT5EngineRequiredLLMFactory:
    """GPT5QueryExpansionEngine llm_factory 필수 검증 테스트"""

    def test_init_without_llm_factory_raises_value_error(self) -> None:
        """llm_factory 없이 초기화하면 ValueError 발생"""
        from app.modules.core.retrieval.query_expansion.gpt5_engine import (
            GPT5QueryExpansionEngine,
        )

        # llm_factory 없이 초기화 시 ValueError
        with pytest.raises(ValueError) as exc_info:
            GPT5QueryExpansionEngine(api_key="test-key")

        # 에러 메시지에 llm_factory 관련 내용 포함
        assert "llm_factory" in str(exc_info.value).lower()
        assert "필수" in str(exc_info.value)

    def test_init_without_llm_factory_default_raises_value_error(self) -> None:
        """기본값(None)으로 초기화하면 ValueError 발생"""
        from app.modules.core.retrieval.query_expansion.gpt5_engine import (
            GPT5QueryExpansionEngine,
        )

        # llm_factory=None으로 명시적 호출도 ValueError
        with pytest.raises(ValueError) as exc_info:
            GPT5QueryExpansionEngine(llm_factory=None)

        assert "llm_factory" in str(exc_info.value).lower()

    def test_init_with_llm_factory_success(self) -> None:
        """llm_factory와 함께 초기화하면 정상 동작"""
        from app.modules.core.retrieval.query_expansion.gpt5_engine import (
            GPT5QueryExpansionEngine,
        )

        mock_factory = MagicMock()

        # llm_factory와 함께 초기화 - 정상 동작
        engine = GPT5QueryExpansionEngine(
            llm_factory=mock_factory,
        )
        assert isinstance(engine, GPT5QueryExpansionEngine)
        assert engine.llm_factory is mock_factory

    def test_init_with_llm_factory_and_optional_params(self) -> None:
        """llm_factory와 선택적 파라미터 함께 초기화"""
        from app.modules.core.retrieval.query_expansion.gpt5_engine import (
            GPT5QueryExpansionEngine,
        )

        mock_factory = MagicMock()
        mock_cb_factory = MagicMock()

        engine = GPT5QueryExpansionEngine(
            llm_factory=mock_factory,
            num_expansions=10,
            max_tokens=1000,
            temperature=0.5,
            provider="openai",
            circuit_breaker_factory=mock_cb_factory,
        )

        assert engine.llm_factory is mock_factory
        assert engine.num_expansions == 10
        assert engine.max_tokens == 1000
        assert engine.temperature == 0.5
        assert engine.provider == "openai"
        assert engine.circuit_breaker_factory is mock_cb_factory


class TestGPT5EngineFromConfigRequiredLLMFactory:
    """GPT5QueryExpansionEngine.from_config() llm_factory 필수 검증"""

    def test_from_config_without_llm_factory_raises_value_error(self) -> None:
        """from_config()에서 llm_factory 없이 호출하면 ValueError"""
        from app.modules.core.retrieval.query_expansion.gpt5_engine import (
            GPT5QueryExpansionEngine,
        )

        config = {"query_expansion": {"enabled": True}}

        with pytest.raises(ValueError) as exc_info:
            GPT5QueryExpansionEngine.from_config(config)

        assert "llm_factory" in str(exc_info.value).lower()
        assert "필수" in str(exc_info.value)

    def test_from_config_with_llm_factory_success(self) -> None:
        """from_config()에서 llm_factory와 함께 호출하면 정상 동작"""
        from app.modules.core.retrieval.query_expansion.gpt5_engine import (
            GPT5QueryExpansionEngine,
        )

        mock_factory = MagicMock()
        config = {
            "query_expansion": {
                "enabled": True,
                "multi_query": {
                    "num_expansions": 7,
                    "max_tokens": 800,
                    "temperature": 0.6,
                },
                "llm": {
                    "provider": "google",
                },
            }
        }

        engine = GPT5QueryExpansionEngine.from_config(config, llm_factory=mock_factory)

        assert engine.llm_factory is mock_factory
        assert engine.num_expansions == 7
        assert engine.max_tokens == 800
        assert engine.temperature == 0.6
        assert engine.provider == "google"
