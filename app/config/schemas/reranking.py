"""
Reranking 설정 스키마 v2.0

3단계 계층 구조:
- approach: 리랭킹 기술 방식 (llm, cross-encoder, late-interaction)
- provider: 서비스 제공자 (google, openai, jina, cohere, openrouter)
- model: 개별 provider 설정에서 지정

approach-provider 유효 조합:
- llm: google, openai, openrouter (LLM 기반 리랭킹)
- cross-encoder: jina, cohere (전용 리랭킹 API)
- late-interaction: jina (ColBERT 방식)
"""

from typing import Literal

from pydantic import Field, model_validator

from .base import BaseConfig


# ========================================
# Provider별 설정 스키마
# ========================================


class GoogleProviderConfig(BaseConfig):
    """Google (Gemini) provider 설정"""

    model: str = Field(
        default="gemini-flash-lite-latest",
        description="Gemini 모델명",
    )
    max_documents: int = Field(
        default=20,
        ge=1,
        le=100,
        description="리랭킹할 최대 문서 수",
    )
    timeout: int = Field(
        default=15,
        ge=5,
        le=60,
        description="타임아웃 (초)",
    )


class OpenAIProviderConfig(BaseConfig):
    """OpenAI provider 설정"""

    model: str = Field(
        default="gpt-5-nano",
        description="OpenAI 모델명",
    )
    max_documents: int = Field(
        default=20,
        ge=1,
        le=100,
        description="리랭킹할 최대 문서 수",
    )
    timeout: int = Field(
        default=15,
        ge=5,
        le=60,
        description="타임아웃 (초)",
    )
    verbosity: Literal["low", "medium", "high"] = Field(
        default="low",
        description="응답 상세도",
    )
    reasoning_effort: Literal["minimal", "moderate", "extensive"] = Field(
        default="minimal",
        description="추론 노력 수준",
    )


class JinaProviderConfig(BaseConfig):
    """Jina provider 설정 (cross-encoder, late-interaction 공용)"""

    model: str = Field(
        default="jina-reranker-v2-base-multilingual",
        description="Jina 모델명 (jina-reranker-* 또는 jina-colbert-*)",
    )
    top_n: int = Field(
        default=10,
        ge=1,
        le=100,
        description="반환할 상위 결과 수",
    )
    timeout: int = Field(
        default=30,
        ge=5,
        le=120,
        description="타임아웃 (초)",
    )
    max_documents: int = Field(
        default=20,
        ge=1,
        le=100,
        description="리랭킹할 최대 문서 수",
    )


class CohereProviderConfig(BaseConfig):
    """Cohere provider 설정"""

    model: str = Field(
        default="rerank-multilingual-v3.0",
        description="Cohere 모델명",
    )
    top_n: int = Field(
        default=10,
        ge=1,
        le=100,
        description="반환할 상위 결과 수",
    )
    timeout: int = Field(
        default=30,
        ge=5,
        le=120,
        description="타임아웃 (초)",
    )


class OpenRouterProviderConfig(BaseConfig):
    """OpenRouter provider 설정"""

    model: str = Field(
        default="google/gemini-2.5-flash-lite",
        description="OpenRouter 모델명 (provider/model 형식)",
    )
    max_documents: int = Field(
        default=20,
        ge=1,
        le=100,
        description="리랭킹할 최대 문서 수",
    )
    timeout: int = Field(
        default=15,
        ge=5,
        le=60,
        description="타임아웃 (초)",
    )


# ========================================
# 메인 설정 스키마
# ========================================

# approach-provider 유효 조합 정의
VALID_APPROACH_PROVIDERS: dict[str, list[str]] = {
    "llm": ["google", "openai", "openrouter"],
    "cross-encoder": ["jina", "cohere"],
    "late-interaction": ["jina"],
}


class RerankingConfigV2(BaseConfig):
    """
    Reranking 설정 v2.0 - 3단계 계층 구조

    예시:
        reranking:
          enabled: true
          approach: "cross-encoder"
          provider: "jina"
          jina:
            model: "jina-reranker-v2-base-multilingual"
            top_n: 10
    """

    enabled: bool = Field(
        default=True,
        description="리랭킹 활성화 여부",
    )

    approach: Literal["llm", "cross-encoder", "late-interaction"] = Field(
        default="cross-encoder",
        description="리랭킹 기술 방식",
    )

    provider: Literal["google", "openai", "jina", "cohere", "openrouter"] = Field(
        default="jina",
        description="서비스 제공자",
    )

    # Provider별 설정 (선택적)
    google: GoogleProviderConfig | None = Field(
        default=None,
        description="Google (Gemini) 설정",
    )
    openai: OpenAIProviderConfig | None = Field(
        default=None,
        description="OpenAI 설정",
    )
    jina: JinaProviderConfig | None = Field(
        default=None,
        description="Jina 설정",
    )
    cohere: CohereProviderConfig | None = Field(
        default=None,
        description="Cohere 설정",
    )
    openrouter: OpenRouterProviderConfig | None = Field(
        default=None,
        description="OpenRouter 설정",
    )

    @model_validator(mode="after")
    def validate_approach_provider_combination(self) -> "RerankingConfigV2":
        """approach-provider 조합 유효성 검증"""
        valid_providers = VALID_APPROACH_PROVIDERS.get(self.approach, [])
        if self.provider not in valid_providers:
            raise ValueError(
                f"approach '{self.approach}'에서 provider '{self.provider}'는 사용할 수 없습니다. "
                f"유효한 provider: {valid_providers}"
            )
        return self


# 하위 호환성을 위한 별칭
RerankingConfig = RerankingConfigV2
