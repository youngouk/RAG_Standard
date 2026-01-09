"""
Chunk Model - 분할된 문서 청크 데이터 모델
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class Chunk:
    """
    분할된 문서 조각을 표현하는 데이터 모델

    청킹 단계에서 생성되며, 검색 및 임베딩의 기본 단위입니다.

    Attributes:
        content: 청크 내용 (텍스트)
        metadata: 청크 메타데이터
        embedding: 임베딩 벡터 (선택적)
        chunk_index: 전체 문서에서의 인덱스
        created_at: 생성 시각 (UTC)

    사용 예시:
        >>> chunk = Chunk(
        ...     content='질문: 서비스 이용 시간은? 답변: 09:00~18:00',
        ...     metadata={'section': '이용안내', 'doc_type': 'FAQ'}
        ... )
        >>> print(chunk.char_count)
        28
        >>> chunk.set_embedding([0.1, 0.2, ...])
    """

    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None
    chunk_index: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """초기화 후 검증 및 자동 메타데이터 생성"""
        # content 검증
        if not self.content or not self.content.strip():
            raise ValueError("Chunk content cannot be empty")

        # 자동 메타데이터 추가
        if "char_count" not in self.metadata:
            self.metadata["char_count"] = len(self.content)

        if "word_count" not in self.metadata:
            # 한글/영어 단어 수 대략 계산
            self.metadata["word_count"] = len(self.content.split())

    @property
    def char_count(self) -> int:
        """문자 수"""
        return len(self.content)

    @property
    def word_count(self) -> int:
        """단어 수"""
        return len(self.content.split())

    @property
    def has_embedding(self) -> bool:
        """임베딩 존재 여부"""
        return self.embedding is not None and len(self.embedding) > 0

    def set_embedding(self, embedding: list[float]) -> None:
        """
        임베딩 벡터 설정

        Args:
            embedding: 임베딩 벡터 (float 리스트)

        Raises:
            ValueError: 빈 임베딩 벡터인 경우
        """
        if not embedding or len(embedding) == 0:
            raise ValueError("Embedding vector cannot be empty")

        self.embedding = embedding
        self.metadata["embedding_dim"] = len(embedding)

    def to_dict(self, include_embedding: bool = False) -> dict[str, Any]:
        """
        딕셔너리로 변환

        Args:
            include_embedding: 임베딩 벡터 포함 여부 (기본: False, 크기가 크므로)

        Returns:
            딕셔너리 표현
        """
        result = {
            "content": self.content,
            "metadata": self.metadata,
            "chunk_index": self.chunk_index,
            "created_at": self.created_at.isoformat(),
            "char_count": self.char_count,
            "word_count": self.word_count,
            "has_embedding": self.has_embedding,
        }

        if include_embedding and self.embedding:
            result["embedding"] = self.embedding

        return result

    def to_langchain_document(self) -> Any:
        """
        LangChain Document 형식으로 변환 (기존 시스템과 호환성)

        Returns:
            langchain.schema.Document 객체
        """
        from langchain_core.documents import Document as LangChainDocument

        return LangChainDocument(page_content=self.content, metadata=self.metadata)

    @classmethod
    def from_langchain_document(cls, doc: Any, chunk_index: int = 0) -> "Chunk":
        """
        LangChain Document에서 Chunk 생성

        Args:
            doc: langchain.schema.Document 객체
            chunk_index: 청크 인덱스

        Returns:
            Chunk 객체
        """
        return cls(
            content=doc.page_content,
            metadata=doc.metadata.copy() if hasattr(doc, "metadata") else {},
            chunk_index=chunk_index,
        )

    def __repr__(self) -> str:
        """문자열 표현"""
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return (
            f"Chunk(index={self.chunk_index}, "
            f"chars={self.char_count}, "
            f"content='{content_preview}')"
        )

    def __len__(self) -> int:
        """길이 연산자 (문자 수)"""
        return self.char_count
