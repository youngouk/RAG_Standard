"""
Pydantic 기본 설정 클래스

모든 설정 스키마의 부모 클래스입니다.
공통 validators와 설정을 정의합니다.
"""

import os
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class BaseConfig(BaseModel):
    """
    모든 설정 스키마의 기본 클래스

    기능:
    - YAML alias 매핑 (snake_case ↔ kebab-case)
    - 환경 변수 자동 치환 (${ENV_VAR} 형식)
    - 추가 필드 허용 (하위 호환성)
    - 불변성 보장 (frozen=True는 사용하지 않음, 유연성 위해)
    """

    model_config = ConfigDict(
        # 추가 필드 허용 (기존 YAML과의 호환성)
        extra="allow",
        # 타입 강제 변환 (문자열 → 숫자 등)
        coerce_numbers_to_str=False,
        # 환경 변수 자동 로드 (Pydantic Settings 사용 시)
        validate_assignment=True,
        # YAML alias 매핑
        populate_by_name=True,
    )

    @field_validator("*", mode="before")
    @classmethod
    def substitute_env_vars(cls, value: Any) -> Any:
        """
        환경 변수 치환 validator

        YAML에서 ${ENV_VAR} 또는 ${ENV_VAR:-default} 형식을 지원합니다.

        Examples:
            api_key: "${GOOGLE_API_KEY}"
            port: "${PORT:-8000}"

        Args:
            value: 원본 설정값

        Returns:
            환경 변수로 치환된 값
        """
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            # ${ENV_VAR} or ${ENV_VAR:-default} 파싱
            env_expr = value[2:-1]  # ${ } 제거

            if ":-" in env_expr:
                # 기본값 있음
                env_name, default_value = env_expr.split(":-", 1)
                return os.getenv(env_name, default_value)
            else:
                # 기본값 없음
                env_name = env_expr
                return os.getenv(env_name, "")

        return value

    def to_dict(self) -> dict[str, Any]:
        """
        Pydantic 모델을 dict로 변환 (하위 호환성)

        기존 코드에서 config['key'] 형식으로 접근하는 경우를 위해 제공합니다.

        Returns:
            설정 딕셔너리
        """
        return self.model_dump(by_alias=True, exclude_none=True)
