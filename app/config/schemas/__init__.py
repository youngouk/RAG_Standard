"""
Pydantic 기반 설정 스키마 모듈

이 모듈은 YAML 설정 파일의 타입 안정성과 검증을 제공합니다.

주요 기능:
- 설정값 타입 검증 (시작 시 자동 검증)
- 환경 변수 자동 바인딩
- 범위 및 제약 조건 검증
- IDE 자동 완성 지원

사용법:
    from app.config.schemas import validate_config

    # YAML 로드 후 검증
    config_dict = load_yaml("config.yaml")
    validated_config = validate_config(config_dict)

v3.3.0 리팩토링:
- 레거시 동적 import 제거 (importlib.util 해킹 코드 제거)
- 헬퍼 함수를 이 모듈에 직접 정의
- BM25Config, PrivacyConfig 직접 정의
"""

import re
from typing import Any

from pydantic import BaseModel

from .base import BaseConfig
from .generation import GenerationConfig
from .reranking import RerankingConfig
from .retrieval import RetrievalConfig
from .root import RootConfig, validate_config

# ========================================
# 헬퍼 함수 (기존 schemas.py에서 이동)
# ========================================


def detect_duplicate_keys_in_yaml(yaml_path: str) -> list[str]:
    """
    YAML 파일에서 중복된 최상위 키 탐지

    Args:
        yaml_path: YAML 파일 경로

    Returns:
        중복된 키 목록 (예: ["app (첫 번째: 1줄, 중복: 5줄)"])
    """
    with open(yaml_path, encoding="utf-8") as f:
        lines = f.readlines()

    # 최상위 키만 추출 (들여쓰기 없는 키)
    top_level_pattern = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*):\s*")
    keys_seen: dict[str, int] = {}
    duplicates = []

    for i, line in enumerate(lines, start=1):
        match = top_level_pattern.match(line)
        if match:
            key = match.group(1)
            if key in keys_seen:
                duplicates.append(f"{key} (첫 번째: {keys_seen[key]}줄, 중복: {i}줄)")
            else:
                keys_seen[key] = i

    return duplicates


def validate_config_dict(config_dict: dict[str, Any]) -> RootConfig:
    """
    딕셔너리를 Pydantic 모델로 검증

    Args:
        config_dict: YAML에서 로드한 설정 딕셔너리

    Returns:
        검증된 RootConfig 객체

    Raises:
        ValidationError: 설정 검증 실패 시
    """
    return RootConfig.model_validate(config_dict)


# ========================================
# BM25 및 Privacy 설정 클래스
# ========================================


class BM25Config(BaseModel):
    """BM25 검색 설정"""

    enabled: bool = True
    k1: float = 1.2
    b: float = 0.75


class PrivacyConfig(BaseModel):
    """개인정보 보호 설정"""

    enabled: bool = True
    pii_detection: bool = True
    anonymization: bool = False


__all__ = [
    # Pydantic 스키마 클래스
    "BaseConfig",
    "RetrievalConfig",
    "GenerationConfig",
    "RerankingConfig",
    "RootConfig",
    # 검증 함수
    "validate_config",
    "validate_config_dict",
    # 헬퍼 함수
    "detect_duplicate_keys_in_yaml",
    # 추가 설정 클래스
    "BM25Config",
    "PrivacyConfig",
]
