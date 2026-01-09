"""HTML Document Loader"""

from pathlib import Path

from bs4 import BeautifulSoup
from langchain_core.documents import Document

from .....lib.logger import get_logger
from .base import DocumentLoaderStrategy

logger = get_logger(__name__)


class HTMLLoader(DocumentLoaderStrategy):
    """HTML 파일 로더"""

    @property
    def supported_extensions(self) -> list[str]:
        return [".html", ".HTML", ".htm", ".HTM"]

    async def load(self, file_path: Path) -> list[Document]:
        """HTML 파일 로드"""
        try:
            with open(file_path, encoding="utf-8") as file:
                html_content = file.read()
            soup = BeautifulSoup(html_content, "html.parser")
            text = soup.get_text(separator="\n", strip=True)
            if not text.strip():
                logger.warning(f"Empty HTML file: {file_path.name}")
                return []
            documents = [Document(page_content=text, metadata={})]
            logger.info(f"HTML loaded from {file_path.name}")
            return documents
        except Exception as e:
            logger.error(f"HTML loading failed: {e}")
            raise ValueError(f"Failed to load HTML file: {e}") from e
