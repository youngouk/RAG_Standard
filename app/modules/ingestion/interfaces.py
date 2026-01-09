"""
Ingestion Interfaces

데이터 소스에 관계없이 일관된 방식으로 데이터를 추출하기 위한 규격.
"""
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StandardDocument:
    """모든 커넥터가 반환해야 하는 표준 문서 규격"""
    content: str
    source_url: str
    metadata: dict[str, Any] = field(default_factory=dict)
    raw_hash: str | None = None

class IIngestionConnector(ABC):
    """지식 수집 커넥터 인터페이스"""

    @abstractmethod
    async def fetch_documents(self) -> AsyncGenerator[StandardDocument, None]:
        """소스로부터 문서를 하나씩 비동기적으로 가져옴"""
        yield StandardDocument(content="", source_url="")
