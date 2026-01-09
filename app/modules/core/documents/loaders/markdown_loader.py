"""Markdown Document Loader"""

from pathlib import Path

import markdown  # type: ignore[import-untyped]
from bs4 import BeautifulSoup
from langchain_core.documents import Document

from .....lib.logger import get_logger
from .base import DocumentLoaderStrategy

logger = get_logger(__name__)


class MarkdownLoader(DocumentLoaderStrategy):
    """Markdown 파일 로더"""

    @property
    def supported_extensions(self) -> list[str]:
        return [".md", ".MD", ".markdown", ".MARKDOWN"]

    async def load(self, file_path: Path) -> list[Document]:
        """Markdown 파일 로드"""
        try:
            with open(file_path, encoding="utf-8") as file:
                md_content = file.read()
            html = markdown.markdown(md_content)
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text(separator="\n", strip=True)
            if not text.strip():
                logger.warning(f"Empty Markdown file: {file_path.name}")
                return []
            documents = [Document(page_content=text, metadata={})]
            logger.info(f"Markdown loaded from {file_path.name}")
            return documents
        except Exception as e:
            logger.error(f"Markdown loading failed: {e}")
            raise ValueError(f"Failed to load Markdown file: {e}") from e
