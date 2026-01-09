"""
Base Document Loader Strategy
모든 로더의 공통 인터페이스 정의
"""

from abc import ABC, abstractmethod
from pathlib import Path

from langchain_core.documents import Document


class DocumentLoaderStrategy(ABC):
    """
    문서 로더 전략 인터페이스

    모든 파일 타입별 로더는 이 인터페이스를 구현해야 함.
    """

    @abstractmethod
    async def load(self, file_path: Path) -> list[Document]:
        """
        파일을 로드하여 Document 리스트로 반환

        Args:
            file_path: 로드할 파일 경로

        Returns:
            Document 객체 리스트

        Raises:
            ValueError: 파일 형식이 잘못된 경우
            FileNotFoundError: 파일이 존재하지 않는 경우
        """
        pass

    @property
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """
        이 로더가 지원하는 파일 확장자 리스트

        Returns:
            확장자 리스트 (예: ['.pdf', '.PDF'])
        """
        pass

    def can_handle(self, file_path: Path) -> bool:
        """
        이 로더가 해당 파일을 처리할 수 있는지 확인

        Args:
            file_path: 확인할 파일 경로

        Returns:
            처리 가능 여부
        """
        return file_path.suffix.lower() in [ext.lower() for ext in self.supported_extensions]
