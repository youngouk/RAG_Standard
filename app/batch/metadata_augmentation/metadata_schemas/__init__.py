"""
범용 메타데이터 스키마 모듈

기능:
- BaseMetadataSchema: 모든 스키마의 기반 클래스
- GenericMetadataSchema: 범용 필드 지원 스키마
"""

from .base import BaseMetadataSchema
from .generic import GenericMetadataSchema

__all__ = [
    "BaseMetadataSchema",
    "GenericMetadataSchema",
]
