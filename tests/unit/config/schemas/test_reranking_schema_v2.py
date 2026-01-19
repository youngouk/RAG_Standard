"""
RerankingConfig v2 스키마 테스트
3단계 계층 구조 (approach/provider/model) 검증
"""

import pytest
from pydantic import ValidationError


class TestRerankingApproach:
    """approach 필드 검증 테스트"""

    def test_valid_approaches(self):
        """유효한 approach 값 허용"""
        from app.config.schemas.reranking import RerankingConfigV2

        # 각 approach에 맞는 유효한 provider와 함께 테스트
        test_cases = [
            ("llm", "google"),
            ("cross-encoder", "jina"),
            ("late-interaction", "jina"),
        ]
        for approach, provider in test_cases:
            config = RerankingConfigV2(approach=approach, provider=provider)
            assert config.approach == approach

    def test_invalid_approach_raises_error(self):
        """유효하지 않은 approach 값 거부"""
        from app.config.schemas.reranking import RerankingConfigV2

        with pytest.raises(ValidationError):
            RerankingConfigV2(approach="invalid", provider="jina")


class TestRerankingProvider:
    """provider 필드 검증 테스트"""

    def test_valid_providers(self):
        """유효한 provider 값 허용"""
        from app.config.schemas.reranking import RerankingConfigV2

        # 각 provider에 맞는 유효한 approach와 함께 테스트
        test_cases = [
            ("llm", "google"),
            ("llm", "openai"),
            ("llm", "openrouter"),
            ("cross-encoder", "jina"),
            ("cross-encoder", "cohere"),
        ]
        for approach, provider in test_cases:
            config = RerankingConfigV2(approach=approach, provider=provider)
            assert config.provider == provider

    def test_invalid_provider_raises_error(self):
        """유효하지 않은 provider 값 거부"""
        from app.config.schemas.reranking import RerankingConfigV2

        with pytest.raises(ValidationError):
            RerankingConfigV2(approach="llm", provider="invalid")


class TestApproachProviderCombination:
    """approach-provider 조합 검증 테스트"""

    def test_llm_approach_valid_providers(self):
        """llm approach: google, openai, openrouter만 허용"""
        from app.config.schemas.reranking import RerankingConfigV2

        # 유효한 조합
        for provider in ["google", "openai", "openrouter"]:
            config = RerankingConfigV2(approach="llm", provider=provider)
            assert config.provider == provider

    def test_llm_approach_invalid_provider_raises_error(self):
        """llm approach에서 jina/cohere 사용 시 에러"""
        from app.config.schemas.reranking import RerankingConfigV2

        with pytest.raises(ValidationError, match="llm.*jina"):
            RerankingConfigV2(approach="llm", provider="jina")

    def test_cross_encoder_approach_valid_providers(self):
        """cross-encoder approach: jina, cohere만 허용"""
        from app.config.schemas.reranking import RerankingConfigV2

        for provider in ["jina", "cohere"]:
            config = RerankingConfigV2(approach="cross-encoder", provider=provider)
            assert config.provider == provider

    def test_cross_encoder_approach_invalid_provider_raises_error(self):
        """cross-encoder approach에서 google/openai 사용 시 에러"""
        from app.config.schemas.reranking import RerankingConfigV2

        with pytest.raises(ValidationError, match="cross-encoder.*google"):
            RerankingConfigV2(approach="cross-encoder", provider="google")

    def test_late_interaction_approach_only_jina(self):
        """late-interaction approach: jina만 허용"""
        from app.config.schemas.reranking import RerankingConfigV2

        config = RerankingConfigV2(approach="late-interaction", provider="jina")
        assert config.provider == "jina"

        with pytest.raises(ValidationError, match="late-interaction.*google"):
            RerankingConfigV2(approach="late-interaction", provider="google")


class TestProviderConfigs:
    """provider별 세부 설정 테스트"""

    def test_google_provider_config(self):
        """Google provider 설정 검증"""
        from app.config.schemas.reranking import (
            GoogleProviderConfig,
            RerankingConfigV2,
        )

        config = RerankingConfigV2(
            approach="llm",
            provider="google",
            google=GoogleProviderConfig(
                model="gemini-flash-lite-latest",
                max_documents=20,
                timeout=15,
            ),
        )
        assert config.google.model == "gemini-flash-lite-latest"
        assert config.google.max_documents == 20

    def test_jina_provider_config(self):
        """Jina provider 설정 검증 (cross-encoder와 late-interaction 모두 지원)"""
        from app.config.schemas.reranking import (
            JinaProviderConfig,
            RerankingConfigV2,
        )

        # cross-encoder 용
        config = RerankingConfigV2(
            approach="cross-encoder",
            provider="jina",
            jina=JinaProviderConfig(
                model="jina-reranker-v2-base-multilingual",
                top_n=10,
            ),
        )
        assert config.jina.model == "jina-reranker-v2-base-multilingual"

        # late-interaction 용
        config2 = RerankingConfigV2(
            approach="late-interaction",
            provider="jina",
            jina=JinaProviderConfig(
                model="jina-colbert-v2",
                top_n=10,
            ),
        )
        assert config2.jina.model == "jina-colbert-v2"

    def test_openai_provider_config(self):
        """OpenAI provider 설정 검증"""
        from app.config.schemas.reranking import (
            OpenAIProviderConfig,
            RerankingConfigV2,
        )

        config = RerankingConfigV2(
            approach="llm",
            provider="openai",
            openai=OpenAIProviderConfig(
                model="gpt-5-nano",
                max_documents=20,
                timeout=15,
                verbosity="low",
                reasoning_effort="minimal",
            ),
        )
        assert config.openai.model == "gpt-5-nano"
        assert config.openai.verbosity == "low"


class TestDefaultValues:
    """기본값 테스트"""

    def test_default_approach_is_cross_encoder(self):
        """기본 approach는 cross-encoder"""
        from app.config.schemas.reranking import RerankingConfigV2

        config = RerankingConfigV2(provider="jina")
        assert config.approach == "cross-encoder"

    def test_default_provider_is_jina(self):
        """기본 provider는 jina"""
        from app.config.schemas.reranking import RerankingConfigV2

        config = RerankingConfigV2()
        assert config.provider == "jina"

    def test_enabled_default_is_true(self):
        """enabled 기본값은 True"""
        from app.config.schemas.reranking import RerankingConfigV2

        config = RerankingConfigV2()
        assert config.enabled is True
