"""
Base Metadata Extractor - 메타데이터 추출 전략 추상 베이스 클래스
"""

from abc import ABC, abstractmethod
from typing import Any

from ..models import Chunk


class BaseMetadataExtractor(ABC):
    """
    메타데이터 추출 전략의 추상 베이스 클래스

    모든 메타데이터 추출 전략은 이 클래스를 상속하여 구현합니다.
    Strategy 패턴을 통해 런타임에 추출 전략을 교체할 수 있습니다.

    사용 예시:
        >>> class MyExtractor(BaseMetadataExtractor):
        ...     def extract(self, chunk):
        ...         # 커스텀 추출 로직
        ...         return {'key': 'value'}
        >>> extractor = MyExtractor()
        >>> metadata = extractor.extract(chunk)
    """

    @abstractmethod
    def extract(self, chunk: Chunk) -> dict[str, Any]:
        """
        청크에서 메타데이터 추출

        Args:
            chunk: 메타데이터를 추출할 청크

        Returns:
            추출된 메타데이터 딕셔너리

        Raises:
            ValueError: 잘못된 청크
        """
        pass

    def validate_chunk(self, chunk: Chunk) -> None:
        """
        청크 검증 (선택적으로 오버라이드 가능)

        Args:
            chunk: 검증할 청크

        Raises:
            ValueError: 잘못된 청크
        """
        if not chunk.content or not chunk.content.strip():
            raise ValueError("Chunk content cannot be empty")

    def merge_metadata(self, existing: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
        """
        기존 메타데이터와 새 메타데이터 병합

        Args:
            existing: 기존 메타데이터
            new: 새로 추출한 메타데이터

        Returns:
            병합된 메타데이터
        """
        # 깊은 복사로 원본 보호
        merged = existing.copy()
        merged.update(new)
        return merged
