"""JSON Document Loader"""

import json
from pathlib import Path

from langchain_core.documents import Document

from .....lib.logger import get_logger
from .base import DocumentLoaderStrategy

logger = get_logger(__name__)


class JSONLoader(DocumentLoaderStrategy):
    """JSON 파일 로더"""

    @property
    def supported_extensions(self) -> list[str]:
        return [".json", ".JSON"]

    async def load(self, file_path: Path) -> list[Document]:
        """JSON 파일 로드"""
        try:
            with open(file_path, encoding="utf-8") as file:
                json_data = json.load(file)
            content = json.dumps(json_data, ensure_ascii=False, indent=2)
            if not content.strip():
                logger.warning(f"Empty JSON file: {file_path.name}")
                return []
            documents = [Document(page_content=content, metadata={})]
            logger.info(f"JSON loaded from {file_path.name}")
            return documents
        except Exception as e:
            logger.error(f"JSON loading failed: {e}")
            raise ValueError(f"Failed to load JSON file: {e}") from e
