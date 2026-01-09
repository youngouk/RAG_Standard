"""
PDF Document Loader
PDF 파일 로딩 전략 구현
"""

from pathlib import Path

from langchain_core.documents import Document
from pypdf import PdfReader

from .....lib.logger import get_logger
from .base import DocumentLoaderStrategy

logger = get_logger(__name__)


class PDFLoader(DocumentLoaderStrategy):
    """PDF 파일 로더"""

    @property
    def supported_extensions(self) -> list[str]:
        return [".pdf", ".PDF"]

    async def load(self, file_path: Path) -> list[Document]:
        """PDF 파일 로드"""
        documents = []
        try:
            with open(file_path, "rb") as file:
                reader = PdfReader(file)
                for page_num, page in enumerate(reader.pages):
                    try:
                        text = page.extract_text()
                        if text.strip():
                            documents.append(
                                Document(page_content=text, metadata={"page_number": page_num + 1})
                            )
                    except Exception as e:
                        logger.warning(f"Failed to extract text from page {page_num + 1}: {e}")
            logger.info(f"PDF loaded: {len(documents)} pages from {file_path.name}")
            return documents
        except Exception as e:
            logger.error(f"PDF loading failed for {file_path}: {e}")
            raise ValueError(f"Failed to load PDF file: {e}") from e
