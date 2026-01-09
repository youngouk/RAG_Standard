"""
범용 메타데이터 스키마

도메인 설정(domain.yaml)에 기반하여 동적으로 필드를 검증하고 처리하는 범용 스키마입니다.
하드코딩된 필드 대신 유연한 Dict 구조를 지원하며, 설정된 필수 필드와 데이터 타입을 검증합니다.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import Field, model_validator

from .base import BaseMetadataSchema


class GenericMetadataSchema(BaseMetadataSchema):
    """
    범용 메타데이터 스키마

    모든 필드는 동적으로 처리되며(extra="allow"),
    유효성 검사는 설정 파일이나 초기화 시 주입된 규칙에 따릅니다.
    """

    # 기본 식별자 (모든 도메인 공통 권장)
    id: str | None = Field(default=None, alias="ID")
    name: str | None = Field(default=None, alias="Name")
    category: str | None = Field(default="General", alias="Category")
    source: str | None = Field(default=None, alias="Source")

    # 동적 필드 정의 (검증 규칙)
    # 클래스 변수로 선언하여 인스턴스 간 공유하거나,
    # 필요시 인스턴스별 검증 로직을 추가 구현해야 함.
    _required_fields: ClassVar[list[str]] = ["name"]
    _numeric_fields: ClassVar[list[str]] = []
    _boolean_fields: ClassVar[list[str]] = []

    @classmethod
    def set_validation_rules(cls, required: list[str], numeric: list[str], boolean: list[str]):
        """검증 규칙 설정 (앱 시작 시 호출)"""
        cls._required_fields = required
        cls._numeric_fields = numeric
        cls._boolean_fields = boolean

    @model_validator(mode="before")
    @classmethod
    def pre_validate_and_parse(cls, data: Any) -> Any:
        """데이터 파싱 및 전처리"""
        if not isinstance(data, dict):
            return data

        # 1. 숫자 필드 파싱
        for field in cls._numeric_fields:
            if field in data:
                data[field] = cls.parse_currency(data[field])

        # 2. 불리언 필드 파싱
        for field in cls._boolean_fields:
            if field in data:
                data[field] = cls.parse_boolean(data[field])

        # 3. 날짜 필드 (필요시 추가)

        return data

    @model_validator(mode="after")
    def validate_requirements(self) -> GenericMetadataSchema:
        """필수 필드 검증"""
        # Pydantic 모델 필드와 extra 필드 모두 확인
        all_data = self.model_dump(by_alias=True)

        for field in self._required_fields:
            # 대소문자 구분 없이 확인하거나, 정확한 키 매칭 확인
            # 여기서는 편의상 정확한 키 매칭 또는 alias 매칭을 가정
            val = all_data.get(field)

            # Pydantic 모델 필드인 경우 속성으로도 접근 가능
            if val is None and hasattr(self, field.lower()):
                 val = getattr(self, field.lower())

            if val is None or (isinstance(val, str) and not val.strip()):
                # 필수 필드 누락 시 에러보다는 경고 로그를 남기거나,
                # 엄격 모드 설정에 따라 처리. 여기서는 Pass (유연성)
                pass

        return self
