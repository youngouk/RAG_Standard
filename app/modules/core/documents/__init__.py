"""
Documents Module - 문서 처리 모듈

문서 로딩, 분할, 임베딩을 담당하는 모듈:
- DocumentProcessor: 기존 문서 로딩 및 처리 (Low-level)
- BaseDocumentProcessor: 문서 유형별 처리 전략 (High-level, MVP Phase)
- DocumentProcessorFactory: 문서 프로세서 팩토리

사용 예시:
    # 기존 방식 (Low-level)
    from app.modules.core.documents import DocumentProcessor
    processor = DocumentProcessor(config)
    docs = await processor.process_files(file_paths)

    # 새로운 방식 (High-level, MVP Phase)
    from app.modules.core.documents import DocumentProcessorFactory
    processor = DocumentProcessorFactory.create('faq')
    chunks = processor.process('data/faq.xlsx')

    # 검색은 retrieval 모듈 사용
    from app.modules.core.retrieval import RetrievalOrchestrator
    # 쿼리 확장은 retrieval 모듈 사용
    from app.modules.core.retrieval.query_expansion import GPT5QueryExpansionEngine

v3.3.0 리팩토링:
- retrieval 모듈 re-export 제거 (계층 분리 강화)
- SearchResult, ExpandedQuery, GPT5QueryExpansionEngine → retrieval에서 직접 import
"""

# MVP Phase: 문서 유형별 처리 전략 (Strategy 패턴)
from .base import BaseDocumentProcessor

# Chunking Strategies
from .chunking import BaseChunker, SimpleChunker
from .document_processing import DocumentProcessor
from .factory import DocumentProcessorFactory

# Metadata Extraction
from .metadata import BaseMetadataExtractor, RuleBasedExtractor

# Models
from .models import Chunk, Document

# Processors
from .processors import FAQProcessor

__all__ = [
    # Document Processing
    "DocumentProcessor",
    # MVP Phase: 문서 유형별 처리 전략
    "BaseDocumentProcessor",
    "DocumentProcessorFactory",
    # Models
    "Document",
    "Chunk",
    # Chunking
    "BaseChunker",
    "SimpleChunker",
    # Metadata
    "BaseMetadataExtractor",
    "RuleBasedExtractor",
    # Processors
    "FAQProcessor",
]
