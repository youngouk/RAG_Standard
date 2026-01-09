"""
Base Document Processor - 문서 처리 전략 추상 베이스 클래스
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from app.lib.logger import get_logger

from .chunking import BaseChunker
from .metadata import BaseMetadataExtractor
from .models import Chunk, Document

logger = get_logger(__name__)


class BaseDocumentProcessor(ABC):
    """
    문서 처리 전략의 추상 베이스 클래스

    모든 문서 유형별 프로세서는 이 클래스를 상속하여 구현합니다.
    Strategy 패턴을 통해 문서 유형에 따라 다른 처리 전략을 사용할 수 있습니다.

    처리 파이프라인:
    1. load() - 문서 로드 (파일, DB 등)
    2. validate() - 문서 검증 (선택적)
    3. chunk() - 문서 청킹
    4. extract_metadata() - 메타데이터 추출
    5. process() - 전체 파이프라인 실행

    Attributes:
        chunker: 청킹 전략
        metadata_extractor: 메타데이터 추출 전략
        validator: 검증 전략 (선택적)

    사용 예시:
        >>> class MyProcessor(BaseDocumentProcessor):
        ...     def load(self, source):
        ...         # 커스텀 로딩 로직
        ...         return Document(...)
        >>> processor = MyProcessor(chunker, extractor)
        >>> chunks = processor.process('data/file.xlsx')
    """

    def __init__(
        self,
        chunker: BaseChunker,
        metadata_extractor: BaseMetadataExtractor,
        validator: Any | None = None,
    ):
        """
        BaseDocumentProcessor 초기화

        Args:
            chunker: 청킹 전략 객체
            metadata_extractor: 메타데이터 추출 전략 객체
            validator: 검증 전략 객체 (선택적)
        """
        self.chunker = chunker
        self.metadata_extractor = metadata_extractor
        self.validator = validator

        logger.debug(
            f"{self.__class__.__name__} initialized with "
            f"chunker={chunker.__class__.__name__}, "
            f"extractor={metadata_extractor.__class__.__name__}"
        )

    @abstractmethod
    def load(self, source: str | Path | Any) -> Document:
        """
        문서 로드 (추상 메서드 - 반드시 구현 필요)

        각 프로세서는 자신의 문서 유형에 맞는 로딩 로직을 구현해야 합니다.

        Args:
            source: 문서 출처 (파일 경로, URL, DB 쿼리 등)

        Returns:
            Document 객체

        Raises:
            FileNotFoundError: 파일을 찾을 수 없음
            ValueError: 잘못된 파일 형식
        """
        pass

    def validate(self, document: Document) -> Document:
        """
        문서 검증 (선택적으로 오버라이드 가능)

        Args:
            document: 검증할 문서

        Returns:
            검증된 문서 (또는 수정된 문서)

        Raises:
            ValueError: 검증 실패
        """
        if self.validator:
            return self.validator.validate(document)  # type: ignore[no-any-return]

        # 기본 검증: 데이터 존재 확인
        if not document.data:
            raise ValueError("Document data cannot be empty")

        logger.debug(f"Document validated: {document}")
        return document

    def chunk(self, document: Document) -> list[Chunk]:
        """
        문서 청킹

        Args:
            document: 청킹할 문서

        Returns:
            Chunk 객체 리스트
        """
        logger.info(f"Chunking document: {document}")
        chunks = self.chunker.chunk(document)
        logger.info(f"Created {len(chunks)} chunks")
        return chunks

    def extract_metadata(self, chunks: list[Chunk]) -> list[Chunk]:
        """
        청크별 메타데이터 추출

        Args:
            chunks: 메타데이터를 추출할 청크 리스트

        Returns:
            메타데이터가 추가된 청크 리스트
        """
        logger.info(f"Extracting metadata for {len(chunks)} chunks")

        for i, chunk in enumerate(chunks):
            try:
                extracted = self.metadata_extractor.extract(chunk)

                # 기존 메타데이터와 병합
                chunk.metadata = self.metadata_extractor.merge_metadata(chunk.metadata, extracted)

                logger.debug(f"Metadata extracted for chunk {i}: {list(extracted.keys())}")

            except Exception as e:
                logger.warning(f"Failed to extract metadata for chunk {i}: {e}")
                continue

        logger.info(f"Metadata extraction completed for {len(chunks)} chunks")
        return chunks

    def process(self, source: str | Path | Any) -> list[Chunk]:
        """
        전체 문서 처리 파이프라인 실행

        Args:
            source: 문서 출처

        Returns:
            처리된 청크 리스트 (메타데이터 포함)

        Raises:
            Exception: 처리 중 오류 발생
        """
        logger.info(f"Starting document processing pipeline for: {source}")

        try:
            # 1. 문서 로드
            document = self.load(source)
            logger.info(f"Document loaded: {document.total_items} items")

            # 2. 문서 검증
            document = self.validate(document)
            logger.info("Document validated")

            # 3. 청킹
            chunks = self.chunk(document)
            logger.info(f"Document chunked into {len(chunks)} chunks")

            # 4. 메타데이터 추출
            chunks = self.extract_metadata(chunks)
            logger.info(f"Metadata extracted for {len(chunks)} chunks")

            logger.info(f"Document processing completed: {len(chunks)} chunks created")
            return chunks

        except Exception as e:
            logger.error(f"Document processing failed for {source}: {e}")
            raise

    def get_stats(self) -> dict[str, Any]:
        """
        프로세서 통계 반환

        Returns:
            통계 딕셔너리
        """
        return {
            "processor": self.__class__.__name__,
            "chunker": self.chunker.__class__.__name__,
            "metadata_extractor": self.metadata_extractor.__class__.__name__,
            "validator": self.validator.__class__.__name__ if self.validator else None,
        }

    def __repr__(self) -> str:
        """문자열 표현"""
        return (
            f"{self.__class__.__name__}("
            f"chunker={self.chunker.__class__.__name__}, "
            f"extractor={self.metadata_extractor.__class__.__name__})"
        )
