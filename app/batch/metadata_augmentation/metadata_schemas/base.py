"""
메타데이터 스키마 베이스 클래스

모든 카테고리 스키마가 상속하는 공통 기능 정의:
- 금액 문자열 → 정수 변환
- 날짜 문자열 파싱
- null 값 처리
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, model_validator


class BaseMetadataSchema(BaseModel):
    """메타데이터 스키마 베이스 클래스"""

    model_config = ConfigDict(
        # 추가 필드 허용 (LLM이 예상 외 필드 생성 시)
        extra="ignore",
        # 필드명 유효성 검사 강화
        validate_default=True,
        # JSON 직렬화 시 별칭 사용
        populate_by_name=True,
    )

    # 서브클래스에서 오버라이드할 필수 필드 목록
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    @staticmethod
    def parse_currency(value: Any) -> int | None:
        """
        금액 문자열을 정수로 변환합니다.

        지원 형식:
        - "50,000원" → 50000
        - "5만원" → 50000
        - "5만 5천원" → 55000
        - "55000" → 55000
        - 55000 → 55000

        Args:
            value: 금액 문자열 또는 숫자

        Returns:
            정수 금액 또는 None
        """
        if value is None:
            return None

        if isinstance(value, int):
            return value

        if isinstance(value, float):
            return int(value)

        if not isinstance(value, str):
            return None

        # 빈 문자열 처리
        value = value.strip()
        if not value or value.lower() in ("null", "none", "n/a", "-", "없음"):
            return None

        # 숫자만 있는 경우
        if value.isdigit():
            return int(value)

        # 쉼표와 원 기호 제거
        cleaned = value.replace(",", "").replace("원", "").replace(" ", "")

        # 만/천 단위 변환
        result = 0
        man_match = re.search(r"(\d+)만", cleaned)
        cheon_match = re.search(r"(\d+)천", cleaned)

        if man_match:
            result += int(man_match.group(1)) * 10000
        if cheon_match:
            result += int(cheon_match.group(1)) * 1000

        # 만/천 단위가 없으면 숫자만 추출
        if not man_match and not cheon_match:
            numbers = re.findall(r"\d+", cleaned)
            if numbers:
                result = int("".join(numbers))

        return result if result > 0 else None

    @staticmethod
    def parse_date(value: Any) -> str | None:
        """
        날짜 문자열을 YYYY-MM-DD 형식으로 변환합니다.

        지원 형식:
        - "2025-01-01"
        - "25년 1월 1일"
        - "2025.01.01"

        Args:
            value: 날짜 문자열

        Returns:
            YYYY-MM-DD 형식 문자열 또는 None
        """
        if value is None:
            return None

        if isinstance(value, date):
            return value.isoformat()

        if not isinstance(value, str):
            return None

        value = value.strip()
        if not value or value.lower() in ("null", "none", "n/a", "-"):
            return None

        # YYYY-MM-DD 형식
        if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
            return value

        # 한글 형식: 25년 1월 1일 또는 2025년 1월 1일
        korean_match = re.search(r"(\d{2,4})년\s*(\d{1,2})월\s*(\d{1,2})일", value)
        if korean_match:
            year = korean_match.group(1)
            if len(year) == 2:
                year = f"20{year}"
            month = korean_match.group(2).zfill(2)
            day = korean_match.group(3).zfill(2)
            return f"{year}-{month}-{day}"

        # 점 형식: 2025.01.01
        dot_match = re.search(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", value)
        if dot_match:
            year = dot_match.group(1)
            month = dot_match.group(2).zfill(2)
            day = dot_match.group(3).zfill(2)
            return f"{year}-{month}-{day}"

        return value  # 파싱 실패 시 원본 반환

    @staticmethod
    def parse_boolean(value: Any) -> bool | None:
        """
        불리언 값을 파싱합니다.

        지원 형식:
        - true/false
        - "가능"/"불가", "있음"/"없음"
        - "O"/"X"

        Args:
            value: 불리언 값 또는 문자열

        Returns:
            불리언 값 또는 None
        """
        if value is None:
            return None

        if isinstance(value, bool):
            return value

        if not isinstance(value, str):
            return None

        value = value.strip().lower()

        if value in ("true", "가능", "있음", "o", "예", "yes", "포함"):
            return True
        if value in ("false", "불가", "없음", "x", "아니오", "no", "미포함"):
            return False

        return None

    @model_validator(mode="after")
    def validate_required_fields(self) -> BaseMetadataSchema:
        """필수 필드가 비어있지 않은지 검증합니다."""
        for field_name in self.REQUIRED_FIELDS:
            value = getattr(self, field_name, None)
            if value is None or (isinstance(value, str) and not value.strip()):
                raise ValueError(f"필수 필드 '{field_name}'이(가) 비어있습니다.")
        return self

    def to_display_dict(self, field_aliases: dict[str, str]) -> dict[str, Any]:
        """
        한글 별칭을 키로 사용하는 딕셔너리를 반환합니다.

        Args:
            field_aliases: 필드명 → 한글 별칭 매핑

        Returns:
            한글 키를 사용하는 딕셔너리
        """
        result = {}
        for field_name, value in self.model_dump().items():
            if value is not None:
                alias = field_aliases.get(field_name, field_name)
                result[alias] = value
        return result

    def get_filled_field_count(self) -> tuple[int, int]:
        """
        채워진 필드 수와 전체 필드 수를 반환합니다.

        Returns:
            (채워진 필드 수, 전체 필드 수)
        """
        data = self.model_dump()
        total = len(data)
        filled = sum(1 for v in data.values() if v is not None)
        return filled, total

    def get_extraction_rate(self) -> float:
        """
        추출율(%)을 반환합니다.

        Returns:
            추출율 (0.0 ~ 100.0)
        """
        filled, total = self.get_filled_field_count()
        return (filled / total * 100) if total > 0 else 0.0
