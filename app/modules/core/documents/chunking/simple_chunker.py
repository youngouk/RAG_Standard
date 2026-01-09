"""
Simple Chunker - 1:1 매핑 청킹 전략 (FAQ용)
"""

from app.lib.logger import get_logger

from ..models import Chunk, Document
from .base import BaseChunker

logger = get_logger(__name__)


class SimpleChunker(BaseChunker):
    """
    가장 단순한 청킹 전략: 1개 항목 = 1개 청크

    FAQ와 같이 이미 구조화된 Q&A 데이터에 적합합니다.
    각 항목을 개별 청크로 변환하며, 추가 분할을 수행하지 않습니다.

    Attributes:
        content_template: 청크 내용 생성 템플릿 (기본: "{question}\n{answer}")

    사용 예시:
        >>> chunker = SimpleChunker()
        >>> document = Document(
        ...     source='faq.xlsx',
        ...     doc_type='FAQ',
        ...     data=[{'질문': '...', '답변': '...'}]
        ... )
        >>> chunks = chunker.chunk(document)
        >>> len(chunks)
        175
    """

    def __init__(self, content_template: str = "{question}\n{answer}"):
        """
        SimpleChunker 초기화

        Args:
            content_template: 청크 내용 생성 템플릿
                - {question}: 질문 필드
                - {answer}: 답변 필드
                - 예: "Q: {question}\nA: {answer}"
        """
        self.content_template = content_template
        logger.debug(f"SimpleChunker initialized with template: {content_template}")

    def chunk(self, document: Document) -> list[Chunk]:
        """
        문서를 1:1 매핑으로 청크 분할

        Args:
            document: 분할할 문서 (FAQ 형식)

        Returns:
            Chunk 객체 리스트

        Raises:
            ValueError: 잘못된 문서 형식
        """
        self.validate_document(document)

        # FAQ 데이터는 리스트 형태여야 함
        if not isinstance(document.data, list):
            raise ValueError(f"SimpleChunker requires list data, got {type(document.data)}")

        logger.info(f"Chunking {len(document.data)} items with SimpleChunker")

        chunks = []
        for idx, item in enumerate(document.data):
            try:
                chunk = self._create_chunk_from_item(item, idx, document)
                chunks.append(chunk)
            except Exception as e:
                logger.warning(f"Failed to create chunk from item {idx}: {e}")
                continue

        chunks = self.post_process_chunks(chunks)

        logger.info(f"Created {len(chunks)} chunks from {len(document.data)} items")
        return chunks

    def _create_chunk_from_item(self, item: dict, index: int, document: Document) -> Chunk:
        """
        개별 항목에서 청크 생성

        Args:
            item: FAQ 항목 (딕셔너리)
            index: 항목 인덱스
            document: 원본 문서

        Returns:
            Chunk 객체

        Raises:
            KeyError: 필수 필드 누락
        """
        # 필드명 유연성 (여러 형태 지원)
        question_keys = ["질문", "question", "Question", "Q", "query"]
        answer_keys = ["답변", "answer", "Answer", "A", "response"]

        question = None
        answer = None

        # 질문 필드 찾기
        for key in question_keys:
            if key in item:
                question = item[key]
                break

        # 답변 필드 찾기
        for key in answer_keys:
            if key in item:
                answer = item[key]
                break

        if question is None or answer is None:
            raise KeyError(
                f"Required fields not found in item. " f"Available keys: {list(item.keys())}"
            )

        # 내용 생성
        content = self._format_content(question, answer)

        # 메타데이터 생성
        metadata = {
            "doc_type": document.doc_type,
            "source": str(document.source),
            "original_index": index,
            "question": question,
        }

        # 원본 메타데이터 병합 (섹션, 카테고리 등)
        if "section" in item or "섹션명" in item:
            metadata["section"] = item.get("section", item.get("섹션명"))

        if "category" in item or "카테고리" in item:
            metadata["category"] = item.get("category", item.get("카테고리"))

        # 문서 메타데이터도 포함
        metadata.update(document.metadata)

        return Chunk(content=content, metadata=metadata, chunk_index=index)

    def _format_content(self, question: str, answer: str) -> str:
        """
        질문과 답변을 템플릿에 맞춰 포맷팅

        Args:
            question: 질문 텍스트
            answer: 답변 텍스트

        Returns:
            포맷팅된 내용
        """
        # 기본 템플릿 적용
        if "{question}" in self.content_template and "{answer}" in self.content_template:
            return self.content_template.format(question=question.strip(), answer=answer.strip())

        # 템플릿이 없으면 기본 형식
        return f"질문: {question.strip()}\n답변: {answer.strip()}"

    def validate_document(self, document: Document) -> None:
        """
        문서 검증 (FAQ 형식 체크)

        Args:
            document: 검증할 문서

        Raises:
            ValueError: 잘못된 문서 형식
        """
        super().validate_document(document)

        if not isinstance(document.data, list):
            raise ValueError("FAQ document must have list data")

        if len(document.data) == 0:
            raise ValueError("FAQ document cannot be empty")

        # 첫 번째 항목으로 필드 검증
        first_item = document.data[0]
        if not isinstance(first_item, dict):
            raise ValueError("FAQ items must be dictionaries")
