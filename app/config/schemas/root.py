"""
Root 설정 스키마

전체 애플리케이션 설정을 통합하고 검증하는 최상위 스키마입니다.
"""

from typing import Any

from pydantic import Field, ValidationError

from .base import BaseConfig
from .generation import GenerationConfig
from .reranking import RerankingConfig
from .retrieval import DocumentProcessingConfig, RAGConfig, RetrievalConfig


class RootConfig(BaseConfig):
    """
    전체 설정 통합 스키마

    핵심 모듈(retrieval, generation, reranking)은 Pydantic으로 타입 검증하고,
    나머지 설정들은 dict로 유연하게 처리하여 하위 호환성을 유지합니다.

    점진적 확장 전략:
    - Phase 1: 핵심 3개 모듈 검증 (현재)
    - Phase 2: session, embeddings, mongodb 등 추가
    - Phase 3: 전체 설정 타입 검증 완성
    """

    # ========================================
    # Phase 1: 핵심 모듈 Pydantic 검증
    # ========================================

    retrieval: RetrievalConfig | None = Field(
        default=None,
        description="검색 시스템 설정 (MongoDB 하이브리드 검색)",
    )

    document_processing: DocumentProcessingConfig | None = Field(
        default=None,
        description="문서 처리 설정 (청킹, 임베딩)",
    )

    rag: RAGConfig | None = Field(
        default=None,
        description="RAG 파이프라인 설정",
    )

    generation: GenerationConfig | None = Field(
        default=None,
        description="답변 생성 설정 (LLM 파라미터)",
    )

    reranking: RerankingConfig | None = Field(
        default=None,
        description="리랭킹 설정",
    )

    # ========================================
    # Phase 2: 추가 모듈 (향후 확장 예정)
    # ========================================

    session: dict[str, Any] | None = Field(
        default=None,
        description="세션 관리 설정 (TTL, 메모리)",
    )

    embeddings: dict[str, Any] | None = Field(
        default=None,
        description="임베딩 모델 설정",
    )

    mongodb: dict[str, Any] | None = Field(
        default=None,
        description="MongoDB 연결 설정",
    )

    query_expansion: dict[str, Any] | None = Field(
        default=None,
        description="쿼리 확장 설정 (Multi-Query RRF)",
    )

    routing: dict[str, Any] | None = Field(
        default=None,
        description="쿼리 라우팅 설정",
    )

    self_rag: dict[str, Any] | None = Field(
        default=None,
        description="Self-RAG 품질 검증 설정",
    )

    llm: dict[str, Any] | None = Field(
        default=None,
        description="LLM 제공자 설정 (DEPRECATED)",
    )

    # ========================================
    # 기타 설정 (BaseConfig의 extra="allow"로 자동 허용)
    # ========================================
    # app, logging, monitoring 등 추가 설정 자동 허용


def validate_config(config_dict: dict[str, Any]) -> tuple[RootConfig | None, list[str]]:
    """
    설정 딕셔너리를 Pydantic 모델로 검증

    Args:
        config_dict: YAML에서 로드한 설정 딕셔너리

    Returns:
        tuple[RootConfig | None, list[str]]:
            - RootConfig: 검증된 설정 객체 (실패 시 None)
            - list[str]: 검증 오류 메시지 목록 (성공 시 빈 리스트)

    Examples:
        >>> config_dict = {"retrieval": {"max_sources": 15}}
        >>> validated_config, errors = validate_config(config_dict)
        >>> if errors:
        ...     print("설정 검증 실패:", errors)
        >>> else:
        ...     print("설정 검증 성공:", validated_config.retrieval.max_sources)
    """
    try:
        validated_config = RootConfig(**config_dict)
        return validated_config, []

    except ValidationError as e:
        # Pydantic v2 에러 형식 파싱
        error_messages = []
        for error in e.errors():
            loc = " → ".join(str(x) for x in error["loc"])
            msg = error["msg"]
            error_type = error["type"]
            error_messages.append(f"[{loc}] {msg} (type: {error_type})")

        return None, error_messages

    except Exception as e:
        # 예상치 못한 에러
        return None, [f"Unexpected validation error: {str(e)}"]


def validate_config_safe(
    config_dict: dict[str, Any],
    *,
    raise_on_error: bool = False,
    log_errors: bool = True,
) -> RootConfig | dict[str, Any]:
    """
    안전한 설정 검증 (Graceful Degradation 지원)

    검증 실패 시 원본 딕셔너리를 반환하여 시스템 동작을 유지합니다.
    Feature Flag와 함께 사용하여 점진적으로 Pydantic 검증을 활성화할 수 있습니다.

    Args:
        config_dict: YAML에서 로드한 설정 딕셔너리
        raise_on_error: True이면 검증 실패 시 예외 발생 (기본값: False)
        log_errors: True이면 검증 오류를 로깅 (기본값: True)

    Returns:
        RootConfig | dict[str, Any]:
            - 검증 성공: RootConfig 객체
            - 검증 실패: 원본 dict (시스템 계속 동작)

    Examples:
        >>> # 프로덕션 환경: 검증 실패해도 시스템 동작
        >>> config = validate_config_safe(config_dict, raise_on_error=False)
        >>>
        >>> # 개발 환경: 검증 실패 시 명확한 에러
        >>> config = validate_config_safe(config_dict, raise_on_error=True)
    """
    validated_config, errors = validate_config(config_dict)

    if errors:
        if log_errors:
            # 로깅 (향후 structlog로 교체)
            print("⚠️  설정 검증 실패 - 원본 딕셔너리 사용 (Graceful Degradation)")
            for error in errors:
                print(f"  - {error}")

        if raise_on_error:
            error_msg = "\n".join(errors)
            raise ValueError(f"Configuration validation failed:\n{error_msg}")

        # Graceful Degradation: 원본 딕셔너리 반환
        return config_dict

    # 검증 성공
    if log_errors:  # log_errors=True이면 성공도 로깅
        print("✅ 설정 검증 성공 - Pydantic 모델 사용")

    return validated_config


__all__ = [
    "RootConfig",
    "validate_config",
    "validate_config_safe",
]
