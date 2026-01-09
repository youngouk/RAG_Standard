"""
Base Chunker - 청킹 전략 추상 베이스 클래스
"""

from abc import ABC, abstractmethod

from ..models import Chunk, Document


class BaseChunker(ABC):
    """
    문서 청킹 전략의 추상 베이스 클래스

    모든 청킹 전략은 이 클래스를 상속하여 구현합니다.
    Strategy 패턴을 통해 런타임에 청킹 전략을 교체할 수 있습니다.

    사용 예시:
        >>> class MyChunker(BaseChunker):
        ...     def chunk(self, document):
        ...         # 커스텀 청킹 로직
        ...         return [Chunk(...), Chunk(...)]
        >>> chunker = MyChunker()
        >>> chunks = chunker.chunk(document)
    """

    @abstractmethod
    def chunk(self, document: Document) -> list[Chunk]:
        """
        문서를 청크로 분할

        Args:
            document: 분할할 문서

        Returns:
            Chunk 객체 리스트

        Raises:
            ValueError: 잘못된 문서 형식
        """
        pass

    def validate_document(self, document: Document) -> None:
        """
        문서 검증 (선택적으로 오버라이드 가능)

        Args:
            document: 검증할 문서

        Raises:
            ValueError: 잘못된 문서
        """
        if not document.data:
            raise ValueError("Document data cannot be empty")

    def post_process_chunks(self, chunks: list[Chunk]) -> list[Chunk]:
        """
        청킹 후처리 (선택적으로 오버라이드 가능)

        Args:
            chunks: 후처리할 청크 리스트

        Returns:
            후처리된 청크 리스트
        """
        # 기본 구현: chunk_index 자동 설정
        for i, chunk in enumerate(chunks):
            chunk.chunk_index = i
            chunk.metadata["total_chunks"] = len(chunks)

        return chunks
