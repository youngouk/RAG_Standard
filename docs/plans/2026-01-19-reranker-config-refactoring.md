# Reranker 설정 구조 리팩토링 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reranker 설정을 명확한 3단계 계층 구조 (approach/provider/model)로 재설계하여 설정의 일관성과 이해도를 향상시킨다.

**Architecture:**
- `approach`: 리랭킹 기술 방식 선택 (llm, cross-encoder, late-interaction)
- `provider`: 서비스 제공자 선택 (google, openai, jina, cohere)
- 개별 provider 설정에서 model과 세부 옵션 지정
- 레거시 설정(`default_provider`, `providers` 섹션)은 완전히 제거

**Tech Stack:** Python 3.11+, Pydantic, YAML, pytest

---

## Phase 1: 새로운 스키마 정의 (신규 파일, 하위 호환 유지)

### Task 1: 새로운 RerankingConfig 스키마 테스트 작성

**Files:**
- Create: `tests/unit/config/schemas/test_reranking_schema_v2.py`

**Step 1: Write the failing test**

```python
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
        from app.config.schemas.reranking_v2 import RerankingConfigV2

        for approach in ["llm", "cross-encoder", "late-interaction"]:
            config = RerankingConfigV2(approach=approach, provider="jina")
            assert config.approach == approach

    def test_invalid_approach_raises_error(self):
        """유효하지 않은 approach 값 거부"""
        from app.config.schemas.reranking_v2 import RerankingConfigV2

        with pytest.raises(ValidationError):
            RerankingConfigV2(approach="invalid", provider="jina")


class TestRerankingProvider:
    """provider 필드 검증 테스트"""

    def test_valid_providers(self):
        """유효한 provider 값 허용"""
        from app.config.schemas.reranking_v2 import RerankingConfigV2

        for provider in ["google", "openai", "jina", "cohere", "openrouter"]:
            config = RerankingConfigV2(approach="llm", provider=provider)
            assert config.provider == provider

    def test_invalid_provider_raises_error(self):
        """유효하지 않은 provider 값 거부"""
        from app.config.schemas.reranking_v2 import RerankingConfigV2

        with pytest.raises(ValidationError):
            RerankingConfigV2(approach="llm", provider="invalid")


class TestApproachProviderCombination:
    """approach-provider 조합 검증 테스트"""

    def test_llm_approach_valid_providers(self):
        """llm approach: google, openai, openrouter만 허용"""
        from app.config.schemas.reranking_v2 import RerankingConfigV2

        # 유효한 조합
        for provider in ["google", "openai", "openrouter"]:
            config = RerankingConfigV2(approach="llm", provider=provider)
            assert config.provider == provider

    def test_llm_approach_invalid_provider_raises_error(self):
        """llm approach에서 jina/cohere 사용 시 에러"""
        from app.config.schemas.reranking_v2 import RerankingConfigV2

        with pytest.raises(ValidationError, match="llm.*jina"):
            RerankingConfigV2(approach="llm", provider="jina")

    def test_cross_encoder_approach_valid_providers(self):
        """cross-encoder approach: jina, cohere만 허용"""
        from app.config.schemas.reranking_v2 import RerankingConfigV2

        for provider in ["jina", "cohere"]:
            config = RerankingConfigV2(approach="cross-encoder", provider=provider)
            assert config.provider == provider

    def test_late_interaction_approach_only_jina(self):
        """late-interaction approach: jina만 허용"""
        from app.config.schemas.reranking_v2 import RerankingConfigV2

        config = RerankingConfigV2(approach="late-interaction", provider="jina")
        assert config.provider == "jina"

        with pytest.raises(ValidationError, match="late-interaction.*google"):
            RerankingConfigV2(approach="late-interaction", provider="google")


class TestProviderConfigs:
    """provider별 세부 설정 테스트"""

    def test_google_provider_config(self):
        """Google provider 설정 검증"""
        from app.config.schemas.reranking_v2 import (
            RerankingConfigV2,
            GoogleProviderConfig,
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
        from app.config.schemas.reranking_v2 import (
            RerankingConfigV2,
            JinaProviderConfig,
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
        from app.config.schemas.reranking_v2 import (
            RerankingConfigV2,
            OpenAIProviderConfig,
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
        from app.config.schemas.reranking_v2 import RerankingConfigV2

        config = RerankingConfigV2(provider="jina")
        assert config.approach == "cross-encoder"

    def test_default_provider_is_jina(self):
        """기본 provider는 jina"""
        from app.config.schemas.reranking_v2 import RerankingConfigV2

        config = RerankingConfigV2()
        assert config.provider == "jina"

    def test_enabled_default_is_true(self):
        """enabled 기본값은 True"""
        from app.config.schemas.reranking_v2 import RerankingConfigV2

        config = RerankingConfigV2()
        assert config.enabled is True
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/config/schemas/test_reranking_schema_v2.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.config.schemas.reranking_v2'"

**Step 3: Write minimal implementation**

Create file: `app/config/schemas/reranking_v2.py`

```python
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
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/config/schemas/test_reranking_schema_v2.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/unit/config/schemas/test_reranking_schema_v2.py app/config/schemas/reranking_v2.py
git commit -m "기능: RerankingConfig v2 스키마 추가 (approach/provider/model 3단계)"
```

---

### Task 2: RerankerFactory v2 테스트 작성

**Files:**
- Create: `tests/unit/retrieval/rerankers/test_reranker_factory_v2.py`

**Step 1: Write the failing test**

```python
"""
RerankerFactory v2 테스트
새로운 approach/provider/model 구조 지원
"""
from unittest.mock import patch

import pytest


class TestRerankerFactoryV2Registry:
    """리랭커 레지스트리 테스트"""

    def test_approach_registry_exists(self):
        """approach별 리랭커 레지스트리 존재 확인"""
        from app.modules.core.retrieval.rerankers.factory_v2 import APPROACH_REGISTRY

        assert "llm" in APPROACH_REGISTRY
        assert "cross-encoder" in APPROACH_REGISTRY
        assert "late-interaction" in APPROACH_REGISTRY

    def test_provider_registry_exists(self):
        """provider별 리랭커 레지스트리 존재 확인"""
        from app.modules.core.retrieval.rerankers.factory_v2 import PROVIDER_REGISTRY

        assert "google" in PROVIDER_REGISTRY
        assert "openai" in PROVIDER_REGISTRY
        assert "jina" in PROVIDER_REGISTRY


class TestRerankerFactoryV2Create:
    """RerankerFactory v2 생성 테스트"""

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"})
    def test_create_llm_google(self):
        """LLM approach + Google provider 리랭커 생성"""
        from app.modules.core.retrieval.rerankers.factory_v2 import RerankerFactoryV2

        config = {
            "reranking": {
                "approach": "llm",
                "provider": "google",
                "google": {
                    "model": "gemini-flash-lite-latest",
                    "max_documents": 20,
                },
            }
        }
        reranker = RerankerFactoryV2.create(config)
        assert reranker.__class__.__name__ == "GeminiFlashReranker"

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_create_llm_openai(self):
        """LLM approach + OpenAI provider 리랭커 생성"""
        from app.modules.core.retrieval.rerankers.factory_v2 import RerankerFactoryV2

        config = {
            "reranking": {
                "approach": "llm",
                "provider": "openai",
                "openai": {
                    "model": "gpt-5-nano",
                },
            }
        }
        reranker = RerankerFactoryV2.create(config)
        assert reranker.__class__.__name__ == "OpenAILLMReranker"

    @patch.dict("os.environ", {"JINA_API_KEY": "test-key"})
    def test_create_cross_encoder_jina(self):
        """Cross-encoder approach + Jina provider 리랭커 생성"""
        from app.modules.core.retrieval.rerankers.factory_v2 import RerankerFactoryV2

        config = {
            "reranking": {
                "approach": "cross-encoder",
                "provider": "jina",
                "jina": {
                    "model": "jina-reranker-v2-base-multilingual",
                },
            }
        }
        reranker = RerankerFactoryV2.create(config)
        assert reranker.__class__.__name__ == "JinaReranker"

    @patch.dict("os.environ", {"JINA_API_KEY": "test-key"})
    def test_create_late_interaction_jina(self):
        """Late-interaction approach + Jina provider 리랭커 생성"""
        from app.modules.core.retrieval.rerankers.factory_v2 import RerankerFactoryV2

        config = {
            "reranking": {
                "approach": "late-interaction",
                "provider": "jina",
                "jina": {
                    "model": "jina-colbert-v2",
                },
            }
        }
        reranker = RerankerFactoryV2.create(config)
        assert reranker.__class__.__name__ == "JinaColBERTReranker"

    def test_create_with_invalid_combination_raises_error(self):
        """유효하지 않은 approach-provider 조합 시 에러"""
        from app.modules.core.retrieval.rerankers.factory_v2 import RerankerFactoryV2

        config = {
            "reranking": {
                "approach": "llm",
                "provider": "jina",  # LLM approach에서 jina는 불가
            }
        }
        with pytest.raises(ValueError, match="approach.*provider"):
            RerankerFactoryV2.create(config)

    @patch.dict("os.environ", {}, clear=True)
    def test_create_without_api_key_raises_error(self):
        """API 키 없이 생성 시 에러"""
        from app.modules.core.retrieval.rerankers.factory_v2 import RerankerFactoryV2

        config = {
            "reranking": {
                "approach": "llm",
                "provider": "google",
            }
        }
        with pytest.raises(ValueError, match="API.*key"):
            RerankerFactoryV2.create(config)


class TestRerankerFactoryV2Helpers:
    """RerankerFactory v2 헬퍼 메서드 테스트"""

    def test_get_approaches(self):
        """지원하는 approach 목록 조회"""
        from app.modules.core.retrieval.rerankers.factory_v2 import RerankerFactoryV2

        approaches = RerankerFactoryV2.get_approaches()
        assert "llm" in approaches
        assert "cross-encoder" in approaches
        assert "late-interaction" in approaches

    def test_get_providers_for_approach(self):
        """approach별 유효한 provider 목록 조회"""
        from app.modules.core.retrieval.rerankers.factory_v2 import RerankerFactoryV2

        llm_providers = RerankerFactoryV2.get_providers_for_approach("llm")
        assert "google" in llm_providers
        assert "openai" in llm_providers
        assert "jina" not in llm_providers

        ce_providers = RerankerFactoryV2.get_providers_for_approach("cross-encoder")
        assert "jina" in ce_providers
        assert "google" not in ce_providers

    def test_get_approach_description(self):
        """approach 설명 조회"""
        from app.modules.core.retrieval.rerankers.factory_v2 import RerankerFactoryV2

        desc = RerankerFactoryV2.get_approach_description("llm")
        assert "LLM" in desc or "언어 모델" in desc

        desc = RerankerFactoryV2.get_approach_description("cross-encoder")
        assert "Cross" in desc or "인코더" in desc

        desc = RerankerFactoryV2.get_approach_description("late-interaction")
        assert "Late" in desc or "토큰" in desc
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/retrieval/rerankers/test_reranker_factory_v2.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.modules.core.retrieval.rerankers.factory_v2'"

**Step 3: Write minimal implementation**

Create file: `app/modules/core/retrieval/rerankers/factory_v2.py`

```python
"""
RerankerFactory v2 - 3단계 계층 구조 기반 리랭커 팩토리

approach/provider/model 구조로 리랭커를 생성합니다.

approach별 설명:
- llm: 범용 LLM을 사용한 리랭킹 (Gemini, GPT 등)
- cross-encoder: 쿼리+문서를 함께 인코딩하는 전용 리랭커 (Jina Reranker, Cohere)
- late-interaction: 토큰 레벨 상호작용 (ColBERT)

사용 예시:
    from app.modules.core.retrieval.rerankers.factory_v2 import RerankerFactoryV2

    config = {
        "reranking": {
            "approach": "cross-encoder",
            "provider": "jina",
            "jina": {"model": "jina-reranker-v2-base-multilingual"}
        }
    }
    reranker = RerankerFactoryV2.create(config)
"""

import os
from typing import Any

from .....lib.logger import get_logger
from ..interfaces import IReranker
from .colbert_reranker import ColBERTRerankerConfig, JinaColBERTReranker
from .gemini_reranker import GeminiFlashReranker
from .jina_reranker import JinaReranker
from .openai_llm_reranker import OpenAILLMReranker

logger = get_logger(__name__)


# ========================================
# 레지스트리 정의
# ========================================

APPROACH_REGISTRY: dict[str, dict[str, Any]] = {
    "llm": {
        "description": "범용 LLM을 사용한 리랭킹 (언어 이해력 기반)",
        "providers": ["google", "openai", "openrouter"],
    },
    "cross-encoder": {
        "description": "Cross-Encoder 전용 리랭커 (쿼리+문서 쌍 인코딩)",
        "providers": ["jina", "cohere"],
    },
    "late-interaction": {
        "description": "Late-Interaction 리랭커 (토큰 레벨 상호작용, ColBERT)",
        "providers": ["jina"],
    },
}

PROVIDER_REGISTRY: dict[str, dict[str, Any]] = {
    "google": {
        "class": GeminiFlashReranker,
        "api_key_env": "GOOGLE_API_KEY",
        "default_config": {
            "model": "gemini-flash-lite-latest",
            "max_documents": 20,
            "timeout": 15,
        },
    },
    "openai": {
        "class": OpenAILLMReranker,
        "api_key_env": "OPENAI_API_KEY",
        "default_config": {
            "model": "gpt-5-nano",
            "max_documents": 20,
            "timeout": 15,
            "verbosity": "low",
            "reasoning_effort": "minimal",
        },
    },
    "jina": {
        "class_cross_encoder": JinaReranker,
        "class_late_interaction": JinaColBERTReranker,
        "api_key_env": "JINA_API_KEY",
        "default_config": {
            "model": "jina-reranker-v2-base-multilingual",
            "top_n": 10,
            "timeout": 30,
            "max_documents": 20,
        },
        "default_config_colbert": {
            "model": "jina-colbert-v2",
            "top_n": 10,
            "timeout": 10,
            "max_documents": 20,
        },
    },
    "cohere": {
        "class": None,  # TODO: CohereReranker 구현 필요
        "api_key_env": "COHERE_API_KEY",
        "default_config": {
            "model": "rerank-multilingual-v3.0",
            "top_n": 10,
        },
    },
    "openrouter": {
        "class": None,  # TODO: OpenRouterReranker 구현 필요
        "api_key_env": "OPENROUTER_API_KEY",
        "default_config": {
            "model": "google/gemini-2.5-flash-lite",
            "max_documents": 20,
            "timeout": 15,
        },
    },
}


# ========================================
# Factory 클래스
# ========================================


class RerankerFactoryV2:
    """
    3단계 계층 구조 기반 리랭커 팩토리

    approach → provider → model 순으로 설정을 해석하여
    적절한 리랭커 인스턴스를 생성합니다.
    """

    @staticmethod
    def create(config: dict[str, Any]) -> IReranker:
        """
        설정 기반 리랭커 인스턴스 생성

        Args:
            config: 전체 설정 딕셔너리 (reranking 섹션 포함)

        Returns:
            IReranker 인터페이스를 구현한 리랭커 인스턴스

        Raises:
            ValueError: 유효하지 않은 approach-provider 조합 또는 API 키 누락
        """
        reranking_config = config.get("reranking", {})
        approach = reranking_config.get("approach", "cross-encoder")
        provider = reranking_config.get("provider", "jina")

        logger.info(f"🔄 RerankerFactoryV2: approach={approach}, provider={provider}")

        # approach 검증
        if approach not in APPROACH_REGISTRY:
            raise ValueError(
                f"지원하지 않는 approach: {approach}. "
                f"지원 목록: {list(APPROACH_REGISTRY.keys())}"
            )

        # approach-provider 조합 검증
        valid_providers = APPROACH_REGISTRY[approach]["providers"]
        if provider not in valid_providers:
            raise ValueError(
                f"approach '{approach}'에서 provider '{provider}'는 사용할 수 없습니다. "
                f"유효한 provider: {valid_providers}"
            )

        # provider 검증
        if provider not in PROVIDER_REGISTRY:
            raise ValueError(
                f"지원하지 않는 provider: {provider}. "
                f"지원 목록: {list(PROVIDER_REGISTRY.keys())}"
            )

        # 리랭커 생성
        if approach == "llm":
            return RerankerFactoryV2._create_llm_reranker(provider, reranking_config)
        elif approach == "cross-encoder":
            return RerankerFactoryV2._create_cross_encoder_reranker(provider, reranking_config)
        elif approach == "late-interaction":
            return RerankerFactoryV2._create_late_interaction_reranker(provider, reranking_config)
        else:
            raise ValueError(f"알 수 없는 approach: {approach}")

    @staticmethod
    def _create_llm_reranker(provider: str, config: dict[str, Any]) -> IReranker:
        """LLM approach 리랭커 생성"""
        provider_info = PROVIDER_REGISTRY[provider]
        api_key = os.getenv(provider_info["api_key_env"])

        if not api_key:
            raise ValueError(
                f"{provider_info['api_key_env']} 환경변수가 설정되지 않았습니다. "
                f"API key가 필요합니다."
            )

        provider_config = config.get(provider, {})
        defaults = provider_info["default_config"]

        if provider == "google":
            reranker = GeminiFlashReranker(
                api_key=api_key,
                model=provider_config.get("model", defaults["model"]),
                max_documents=provider_config.get("max_documents", defaults["max_documents"]),
                timeout=provider_config.get("timeout", defaults["timeout"]),
            )
        elif provider == "openai":
            reranker = OpenAILLMReranker(
                api_key=api_key,
                model=provider_config.get("model", defaults["model"]),
                max_documents=provider_config.get("max_documents", defaults["max_documents"]),
                timeout=provider_config.get("timeout", defaults["timeout"]),
                verbosity=provider_config.get("verbosity", defaults["verbosity"]),
                reasoning_effort=provider_config.get("reasoning_effort", defaults["reasoning_effort"]),
            )
        else:
            raise ValueError(f"LLM approach에서 {provider}는 아직 지원되지 않습니다.")

        logger.info(f"✅ {reranker.__class__.__name__} 생성 완료")
        return reranker

    @staticmethod
    def _create_cross_encoder_reranker(provider: str, config: dict[str, Any]) -> IReranker:
        """Cross-encoder approach 리랭커 생성"""
        provider_info = PROVIDER_REGISTRY[provider]
        api_key = os.getenv(provider_info["api_key_env"])

        if not api_key:
            raise ValueError(
                f"{provider_info['api_key_env']} 환경변수가 설정되지 않았습니다. "
                f"API key가 필요합니다."
            )

        provider_config = config.get(provider, {})
        defaults = provider_info["default_config"]

        if provider == "jina":
            reranker = JinaReranker(
                api_key=api_key,
                model=provider_config.get("model", defaults["model"]),
                timeout=provider_config.get("timeout", defaults.get("timeout", 30)),
            )
        else:
            raise ValueError(f"Cross-encoder approach에서 {provider}는 아직 지원되지 않습니다.")

        logger.info(f"✅ {reranker.__class__.__name__} 생성 완료")
        return reranker

    @staticmethod
    def _create_late_interaction_reranker(provider: str, config: dict[str, Any]) -> IReranker:
        """Late-interaction approach 리랭커 생성"""
        provider_info = PROVIDER_REGISTRY[provider]
        api_key = os.getenv(provider_info["api_key_env"])

        if not api_key:
            raise ValueError(
                f"{provider_info['api_key_env']} 환경변수가 설정되지 않았습니다. "
                f"API key가 필요합니다."
            )

        provider_config = config.get(provider, {})
        defaults = provider_info.get("default_config_colbert", provider_info["default_config"])

        if provider == "jina":
            colbert_config = ColBERTRerankerConfig(
                enabled=True,
                api_key=api_key,
                model=provider_config.get("model", defaults["model"]),
                timeout=provider_config.get("timeout", defaults.get("timeout", 10)),
                max_documents=provider_config.get("max_documents", defaults.get("max_documents", 20)),
            )
            reranker = JinaColBERTReranker(config=colbert_config)
        else:
            raise ValueError(f"Late-interaction approach에서 {provider}는 아직 지원되지 않습니다.")

        logger.info(f"✅ {reranker.__class__.__name__} 생성 완료")
        return reranker

    # ========================================
    # 헬퍼 메서드
    # ========================================

    @staticmethod
    def get_approaches() -> list[str]:
        """지원하는 approach 목록 반환"""
        return list(APPROACH_REGISTRY.keys())

    @staticmethod
    def get_providers_for_approach(approach: str) -> list[str]:
        """특정 approach에서 사용 가능한 provider 목록 반환"""
        if approach not in APPROACH_REGISTRY:
            return []
        return APPROACH_REGISTRY[approach]["providers"]

    @staticmethod
    def get_approach_description(approach: str) -> str:
        """approach 설명 반환"""
        if approach not in APPROACH_REGISTRY:
            return "알 수 없는 approach"
        return APPROACH_REGISTRY[approach]["description"]

    @staticmethod
    def get_all_providers() -> list[str]:
        """모든 provider 목록 반환"""
        return list(PROVIDER_REGISTRY.keys())
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/retrieval/rerankers/test_reranker_factory_v2.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/unit/retrieval/rerankers/test_reranker_factory_v2.py app/modules/core/retrieval/rerankers/factory_v2.py
git commit -m "기능: RerankerFactoryV2 추가 (approach/provider/model 3단계)"
```

---

## Phase 2: YAML 설정 마이그레이션

### Task 3: 새로운 reranking.yaml 작성

**Files:**
- Backup: `app/config/features/reranking.yaml` → `app/config/features/reranking.yaml.legacy`
- Create: `app/config/features/reranking.yaml` (새 구조)

**Step 1: 레거시 파일 백업**

```bash
cp app/config/features/reranking.yaml app/config/features/reranking.yaml.legacy
```

**Step 2: 새 YAML 작성**

```yaml
# 리랭킹 설정 v2.0
# 3단계 계층 구조: approach → provider → model
#
# ╔═══════════════════════════════════════════════════════════════════════╗
# ║  approach (기술 방식)                                                  ║
# ╠═══════════════════════════════════════════════════════════════════════╣
# ║  - llm:              범용 LLM 기반 리랭킹 (언어 이해력 활용)           ║
# ║  - cross-encoder:    전용 리랭커 API (쿼리+문서 쌍 인코딩)            ║
# ║  - late-interaction: ColBERT 방식 (토큰 레벨 상호작용)                ║
# ╠═══════════════════════════════════════════════════════════════════════╣
# ║  provider (서비스 제공자)                                              ║
# ╠═══════════════════════════════════════════════════════════════════════╣
# ║  llm:              google, openai, openrouter                         ║
# ║  cross-encoder:    jina, cohere                                       ║
# ║  late-interaction: jina                                               ║
# ╚═══════════════════════════════════════════════════════════════════════╝

reranking:
  enabled: true

  # ========================================
  # 기본 설정
  # ========================================
  approach: "late-interaction"  # llm | cross-encoder | late-interaction
  provider: "jina"              # approach에 따라 유효한 provider 선택

  # ========================================
  # Provider별 설정
  # ========================================

  # Google (Gemini) - LLM approach용
  google:
    model: "gemini-flash-lite-latest"
    max_documents: 20
    timeout: 15

  # OpenAI - LLM approach용
  openai:
    model: "gpt-5-nano"
    max_documents: 20
    timeout: 15
    verbosity: "low"
    reasoning_effort: "minimal"

  # OpenRouter - LLM approach용
  openrouter:
    model: "google/gemini-2.5-flash-lite"
    max_documents: 20
    timeout: 15

  # Jina - cross-encoder 및 late-interaction용
  # approach에 따라 적절한 모델 자동 선택
  jina:
    # cross-encoder용: jina-reranker-v2-base-multilingual
    # late-interaction용: jina-colbert-v2
    model: "jina-colbert-v2"
    top_n: 10
    timeout: 30
    max_documents: 20

  # Cohere - cross-encoder용
  cohere:
    model: "rerank-multilingual-v3.0"
    top_n: 10
    timeout: 30

# ========================================
# approach 선택 가이드
# ========================================
#
# 🎯 빠른 응답 필요 (실시간 채팅):
#   → approach: late-interaction, provider: jina
#   → 토큰 레벨 매칭으로 빠르면서 정확
#
# 🧠 깊은 이해 필요 (복잡한 질문):
#   → approach: llm, provider: google
#   → LLM의 언어 이해력 활용
#
# ⚖️ 균형 (일반 검색):
#   → approach: cross-encoder, provider: jina
#   → 전용 리랭커로 안정적 품질
```

**Step 3: Commit**

```bash
git add app/config/features/reranking.yaml app/config/features/reranking.yaml.legacy
git commit -m "리팩터: reranking.yaml 3단계 구조로 마이그레이션"
```

---

## Phase 3: DI 컨테이너 업데이트

### Task 4: DI 컨테이너에서 RerankerFactoryV2 사용

**Files:**
- Modify: `app/core/di_container.py:234-303`
- Create: `tests/unit/core/test_di_container_reranker_v2.py`

**Step 1: Write the failing test**

```python
"""
DI 컨테이너 RerankerFactoryV2 통합 테스트
"""
from unittest.mock import patch

import pytest


class TestDIContainerRerankerV2:
    """DI 컨테이너 Reranker v2 통합 테스트"""

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"JINA_API_KEY": "test-key"})
    async def test_create_reranker_with_new_config_structure(self):
        """새로운 설정 구조로 리랭커 생성"""
        from app.core.di_container import create_reranker_instance_v2

        config = {
            "reranking": {
                "approach": "late-interaction",
                "provider": "jina",
                "jina": {
                    "model": "jina-colbert-v2",
                },
            }
        }
        reranker = await create_reranker_instance_v2(config)
        assert reranker is not None
        assert reranker.__class__.__name__ == "JinaColBERTReranker"

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"})
    async def test_create_llm_reranker_via_di(self):
        """DI를 통한 LLM 리랭커 생성"""
        from app.core.di_container import create_reranker_instance_v2

        config = {
            "reranking": {
                "approach": "llm",
                "provider": "google",
            }
        }
        reranker = await create_reranker_instance_v2(config)
        assert reranker.__class__.__name__ == "GeminiFlashReranker"

    @pytest.mark.asyncio
    @patch.dict("os.environ", {}, clear=True)
    async def test_create_reranker_without_api_key_returns_none(self):
        """API 키 없으면 None 반환 (graceful degradation)"""
        from app.core.di_container import create_reranker_instance_v2

        config = {
            "reranking": {
                "approach": "llm",
                "provider": "google",
            }
        }
        reranker = await create_reranker_instance_v2(config)
        assert reranker is None
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/core/test_di_container_reranker_v2.py -v`
Expected: FAIL with "cannot import name 'create_reranker_instance_v2'"

**Step 3: Write minimal implementation**

`app/core/di_container.py`에 추가:

```python
async def create_reranker_instance_v2(
    config: dict, llm_factory: LLMClientFactory | None = None
) -> IReranker | None:
    """
    Reranker 인스턴스 생성 (v2 - 새로운 설정 구조)

    approach/provider/model 3단계 구조 지원.
    API 키 누락 시 None 반환 (graceful degradation).

    Args:
        config: 설정 딕셔너리
        llm_factory: LLM Factory (optional)

    Returns:
        Reranker 인스턴스 또는 None
    """
    from app.modules.core.retrieval.rerankers.factory_v2 import RerankerFactoryV2

    reranking_config = config.get("reranking", {})
    approach = reranking_config.get("approach", "cross-encoder")
    provider = reranking_config.get("provider", "jina")

    logger.info(
        "Reranker v2 초기화",
        extra={"approach": approach, "provider": provider}
    )

    try:
        reranker = RerankerFactoryV2.create(config)
        logger.info(
            f"{reranker.__class__.__name__} 초기화 성공",
            extra={"approach": approach, "provider": provider}
        )
        return reranker
    except ValueError as e:
        # API 키 누락 등 설정 오류
        logger.warning(
            "Reranker 초기화 실패",
            extra={"error": str(e), "status": "proceeding_without_reranker"}
        )
        return None
    except Exception as e:
        logger.error(
            "Reranker 초기화 중 예외 발생",
            extra={"error": str(e), "error_type": type(e).__name__}
        )
        return None
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/core/test_di_container_reranker_v2.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/core/di_container.py tests/unit/core/test_di_container_reranker_v2.py
git commit -m "기능: DI 컨테이너에 create_reranker_instance_v2 추가"
```

---

## Phase 4: 레거시 코드 제거 (최종 단계)

### Task 5: 레거시 설정 제거 및 마이그레이션 완료

**Files:**
- Remove: `app/config/schemas/reranking.py` (레거시 스키마)
- Rename: `app/config/schemas/reranking_v2.py` → `app/config/schemas/reranking.py`
- Remove: `app/modules/core/retrieval/rerankers/factory.py` (레거시 팩토리)
- Rename: `app/modules/core/retrieval/rerankers/factory_v2.py` → `app/modules/core/retrieval/rerankers/factory.py`
- Update: `app/modules/core/retrieval/rerankers/__init__.py`
- Update: `app/core/di_container.py` (레거시 함수 제거)
- Remove: `app/config/features/reranking.yaml.legacy`

**Step 1: 기존 테스트 업데이트**

기존 `test_reranker_factory.py`를 새 구조에 맞게 수정:

```python
# tests/unit/retrieval/rerankers/test_reranker_factory.py
"""
RerankerFactory 단위 테스트 (v2 구조)
"""
from unittest.mock import patch

import pytest


class TestRerankerFactory:
    """RerankerFactory 테스트"""

    def test_approach_registry_exists(self):
        """approach별 레지스트리 존재 확인"""
        from app.modules.core.retrieval.rerankers.factory import APPROACH_REGISTRY

        assert "llm" in APPROACH_REGISTRY
        assert "cross-encoder" in APPROACH_REGISTRY
        assert "late-interaction" in APPROACH_REGISTRY

    def test_get_approaches(self):
        """지원하는 approach 목록 조회"""
        from app.modules.core.retrieval.rerankers.factory import RerankerFactory

        approaches = RerankerFactory.get_approaches()
        assert "llm" in approaches
        assert "cross-encoder" in approaches
        assert "late-interaction" in approaches

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"})
    def test_create_llm_google_reranker(self):
        """LLM approach + Google provider 리랭커 생성"""
        from app.modules.core.retrieval.rerankers.factory import RerankerFactory

        config = {
            "reranking": {
                "approach": "llm",
                "provider": "google",
            }
        }
        reranker = RerankerFactory.create(config)
        assert reranker.__class__.__name__ == "GeminiFlashReranker"

    @patch.dict("os.environ", {"JINA_API_KEY": "test-key"})
    def test_create_cross_encoder_jina_reranker(self):
        """Cross-encoder approach + Jina provider 리랭커 생성"""
        from app.modules.core.retrieval.rerankers.factory import RerankerFactory

        config = {
            "reranking": {
                "approach": "cross-encoder",
                "provider": "jina",
            }
        }
        reranker = RerankerFactory.create(config)
        assert reranker.__class__.__name__ == "JinaReranker"

    @patch.dict("os.environ", {"JINA_API_KEY": "test-key"})
    def test_create_late_interaction_reranker(self):
        """Late-interaction approach 리랭커 생성"""
        from app.modules.core.retrieval.rerankers.factory import RerankerFactory

        config = {
            "reranking": {
                "approach": "late-interaction",
                "provider": "jina",
            }
        }
        reranker = RerankerFactory.create(config)
        assert reranker.__class__.__name__ == "JinaColBERTReranker"

    def test_invalid_approach_raises_error(self):
        """유효하지 않은 approach 에러"""
        from app.modules.core.retrieval.rerankers.factory import RerankerFactory

        config = {
            "reranking": {
                "approach": "invalid",
                "provider": "jina",
            }
        }
        with pytest.raises(ValueError, match="지원하지 않는 approach"):
            RerankerFactory.create(config)
```

**Step 2: 파일 이동/제거**

```bash
# 백업 (안전을 위해)
mkdir -p app/config/schemas/_legacy
mv app/config/schemas/reranking.py app/config/schemas/_legacy/reranking_v1.py

mkdir -p app/modules/core/retrieval/rerankers/_legacy
mv app/modules/core/retrieval/rerankers/factory.py app/modules/core/retrieval/rerankers/_legacy/factory_v1.py

# 새 파일로 교체
mv app/config/schemas/reranking_v2.py app/config/schemas/reranking.py
mv app/modules/core/retrieval/rerankers/factory_v2.py app/modules/core/retrieval/rerankers/factory.py

# 레거시 YAML 백업 제거
rm app/config/features/reranking.yaml.legacy
```

**Step 3: __init__.py 업데이트**

`app/modules/core/retrieval/rerankers/__init__.py`:

```python
"""
Reranker Module - 검색 결과 리랭킹 모듈

approach별 리랭커:
- LLM: GeminiFlashReranker, OpenAILLMReranker
- Cross-Encoder: JinaReranker
- Late-Interaction: JinaColBERTReranker

RerankerFactory를 통해 approach/provider/model 설정으로 생성합니다.
"""

from ..interfaces import IReranker
from .colbert_reranker import ColBERTRerankerConfig, JinaColBERTReranker
from .factory import APPROACH_REGISTRY, PROVIDER_REGISTRY, RerankerFactory
from .gemini_reranker import GeminiFlashReranker
from .jina_reranker import JinaReranker
from .openai_llm_reranker import OpenAILLMReranker
from .reranker_chain import RerankerChain, RerankerChainConfig

__all__ = [
    "IReranker",
    "JinaReranker",
    "JinaColBERTReranker",
    "ColBERTRerankerConfig",
    "OpenAILLMReranker",
    "GeminiFlashReranker",
    "RerankerChain",
    "RerankerChainConfig",
    "RerankerFactory",
    "APPROACH_REGISTRY",
    "PROVIDER_REGISTRY",
]
```

**Step 4: 전체 테스트 실행**

Run: `uv run pytest tests/ -v --tb=short`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add -A
git commit -m "리팩터: Reranker 설정 구조 v2로 마이그레이션 완료

- approach/provider/model 3단계 계층 구조 적용
- 레거시 default_provider, providers 섹션 제거
- RerankerFactory를 RerankerFactoryV2로 교체
- DI 컨테이너 create_reranker_instance_v2 적용
- 백업 파일은 _legacy 디렉토리에 보관"
```

---

## Phase 5: 문서화 및 정리

### Task 6: CLAUDE.md 및 기술부채 문서 업데이트

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/TECHNICAL_DEBT_ANALYSIS.md`

**Step 1: CLAUDE.md 업데이트**

Reranking 섹션 추가/수정:

```markdown
### Reranking 설정 구조 (v2.0)

3단계 계층 구조로 리랭커를 설정합니다:

```yaml
reranking:
  approach: "late-interaction"  # 기술 방식
  provider: "jina"              # 서비스 제공자
  jina:                         # provider별 상세 설정
    model: "jina-colbert-v2"
```

**approach 종류:**
| approach | 설명 | 유효 provider |
|----------|------|--------------|
| `llm` | 범용 LLM 리랭킹 | google, openai, openrouter |
| `cross-encoder` | 전용 리랭커 API | jina, cohere |
| `late-interaction` | ColBERT 방식 | jina |
```

**Step 2: 기술부채 문서 업데이트**

`docs/TECHNICAL_DEBT_ANALYSIS.md`에서 Reranker 항목 완료 처리:

```markdown
### ✅ 완료: Reranker 설정 구조 리팩토링 (v1.2.0)

- **이전**: 혼란스러운 provider 네이밍 (모델명, 회사명, 기술명 혼재)
- **이후**: approach/provider/model 3단계 계층 구조
- **커밋**: 2026-01-19
```

**Step 3: Commit**

```bash
git add CLAUDE.md docs/TECHNICAL_DEBT_ANALYSIS.md
git commit -m "문서: Reranker v2 설정 구조 문서화"
```

---

## 검증 체크리스트

- [ ] `uv run pytest tests/unit/config/schemas/test_reranking_schema_v2.py -v` PASS
- [ ] `uv run pytest tests/unit/retrieval/rerankers/test_reranker_factory_v2.py -v` PASS
- [ ] `uv run pytest tests/unit/core/test_di_container_reranker_v2.py -v` PASS
- [ ] `uv run pytest tests/ -v --tb=short` 전체 PASS
- [ ] `uv run mypy app/config/schemas/reranking.py` 타입 체크 PASS
- [ ] `uv run ruff check app/modules/core/retrieval/rerankers/factory.py` 린트 PASS

---

**Plan complete and saved to `docs/plans/2026-01-19-reranker-config-refactoring.md`. Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
