"""
Metadata Extraction - 메타데이터 추출 전략 모듈

청크에서 메타데이터를 추출하는 다양한 전략을 제공:
- BaseMetadataExtractor: 추상 베이스 클래스
- RuleBasedExtractor: 규칙 기반 추출 (MVP)
- LLMBasedExtractor: LLM 기반 추출 (Phase 2)

사용 예시:
    from app.modules.core.documents.metadata import RuleBasedExtractor

    extractor = RuleBasedExtractor()
    metadata = extractor.extract(chunk)
"""

from .base import BaseMetadataExtractor
from .rule_based import RuleBasedExtractor

__all__ = [
    "BaseMetadataExtractor",
    "RuleBasedExtractor",
]
