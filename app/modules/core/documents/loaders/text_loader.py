"""
Text Document Loader
일반 텍스트 파일 로딩 전략 구현
"""

from pathlib import Path

from langchain_core.documents import Document

from .....lib.logger import get_logger
from .base import DocumentLoaderStrategy

logger = get_logger(__name__)


class TextLoader(DocumentLoaderStrategy):
    """텍스트 파일 로더"""

    @property
    def supported_extensions(self) -> list[str]:
        return [".txt", ".TXT", ".text"]

    async def load(self, file_path: Path) -> list[Document]:
        """텍스트 파일 로드"""
        try:
            with open(file_path, encoding="utf-8") as file:
                content = file.read()
            if not content.strip():
                logger.warning(f"Empty text file: {file_path.name}")
                return []
            documents = [Document(page_content=content, metadata={})]
            logger.info(f"Text file loaded: {len(content)} characters from {file_path.name}")
            return documents
        except UnicodeDecodeError:
            try:
                with open(file_path, encoding="cp949") as file:
                    content = file.read()
                documents = [Document(page_content=content, metadata={})]
                logger.info(f"Text file loaded (cp949): {file_path.name}")
                return documents
            except Exception as e:
                logger.error(f"Text loading failed with multiple encodings: {e}")
                raise ValueError(f"Failed to load text file: {e}") from e
        except Exception as e:
            logger.error(f"Text loading failed for {file_path}: {e}")
            raise ValueError(f"Failed to load text file: {e}") from e
