"""
Storage Interfaces

시스템의 데이터 저장소 추상화 인터페이스 정의.
이 인터페이스를 통해 비즈니스 로직은 구체적인 DB 구현체(Postgres, Weaviate 등)로부터 분리됩니다.
"""
from abc import ABC, abstractmethod
from typing import Any


class IMetadataStore(ABC):
    """
    메타데이터 저장소 인터페이스 (RDB/NoSQL 공용)
    CRUD 작업을 추상화합니다.
    """
    @abstractmethod
    async def save(self, collection: str, data: dict[str, Any], key_field: str = "id") -> bool:
        """데이터 저장 또는 갱신 (Upsert)"""
        pass

    @abstractmethod
    async def get(self, collection: str, filters: dict[str, Any]) -> list[dict[str, Any]]:
        """조건에 맞는 데이터 조회"""
        pass

    @abstractmethod
    async def delete(self, collection: str, filters: dict[str, Any]) -> int:
        """조건에 맞는 데이터 삭제"""
        pass

class IVectorStore(ABC):
    """
    벡터 저장소 인터페이스
    임베딩 벡터 저장 및 검색을 추상화합니다.
    """
    @abstractmethod
    async def add_documents(self, collection: str, documents: list[dict[str, Any]]) -> int:
        """문서(벡터 포함) 저장"""
        pass

    @abstractmethod
    async def search(self, collection: str, query_vector: list[float], top_k: int, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """벡터 유사도 검색"""
        pass

    @abstractmethod
    async def delete(self, collection: str, filters: dict[str, Any]) -> int:
        """조건에 맞는 벡터 삭제"""
        pass
