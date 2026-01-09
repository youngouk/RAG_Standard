"""
Documents Models - 문서 처리 데이터 모델

문서와 청크의 데이터 구조를 정의하는 모듈:
- Document: 원본 문서 표현
- Chunk: 분할된 문서 조각

사용 예시:
    from app.modules.core.documents.models import Document, Chunk

    # 문서 생성
    doc = Document(
        source='data/faq.xlsx',
        doc_type='FAQ',
        data=[...]
    )

    # 청크 생성
    chunk = Chunk(
        content='질문: ... 답변: ...',
        metadata={'section': '서비스'}
    )
"""

from .chunk import Chunk
from .document import Document

__all__ = [
    "Document",
    "Chunk",
]
