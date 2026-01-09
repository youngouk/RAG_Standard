"""
Storage Interfaces Definition and Test

시스템이 특정 DB 구현체에 종속되지 않도록 하는 핵심 인터페이스 정의입니다.
TDD 사이클의 Red-Green-Refactor 단계를 따릅니다.
"""
from abc import ABC, abstractmethod
from typing import Any

import pytest

# =============================================================================
# 1. Interface Definitions (Target Architecture)
# =============================================================================

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

# =============================================================================
# 2. Tests (Interface Compliance Verification)
# =============================================================================

@pytest.mark.asyncio
async def test_metadata_store_interface_compliance():
    """
    IMetadataStore 인터페이스 준수 여부 및 Mock 구현체 동작 검증
    """
    # Given: Mock Implementation (In-Memory)
    class InMemoryMetadataStore(IMetadataStore):
        def __init__(self):
            self.store = {}

        async def save(self, collection: str, data: dict[str, Any], key_field: str = "id") -> bool:
            if collection not in self.store:
                self.store[collection] = []

            # Upsert Logic
            key_value = data.get(key_field)
            existing_idx = -1
            if key_value:
                for idx, item in enumerate(self.store[collection]):
                    if item.get(key_field) == key_value:
                        existing_idx = idx
                        break

            if existing_idx >= 0:
                self.store[collection][existing_idx] = data
            else:
                self.store[collection].append(data)
            return True

        async def get(self, collection: str, filters: dict[str, Any]) -> list[dict[str, Any]]:
            if collection not in self.store:
                return []
            results = []
            for item in self.store[collection]:
                match = True
                for k, v in filters.items():
                    if item.get(k) != v:
                        match = False
                        break
                if match:
                    results.append(item)
            return results

        async def delete(self, collection: str, filters: dict[str, Any]) -> int:
            if collection not in self.store:
                return 0
            initial_len = len(self.store[collection])
            self.store[collection] = [
                item for item in self.store[collection]
                if not all(item.get(k) == v for k, v in filters.items())
            ]
            return initial_len - len(self.store[collection])

    # When
    store = InMemoryMetadataStore()
    await store.save("products", {"id": "1", "name": "Apple", "category": "fruit"})
    await store.save("products", {"id": "2", "name": "Banana", "category": "fruit"})
    await store.save("products", {"id": "1", "name": "Green Apple", "category": "fruit"}) # Update check

    # Then
    # 1. Update check
    results = await store.get("products", {"id": "1"})
    assert len(results) == 1
    assert results[0]["name"] == "Green Apple"

    # 2. Search check
    fruits = await store.get("products", {"category": "fruit"})
    assert len(fruits) == 2

    # 3. Delete check
    deleted = await store.delete("products", {"id": "2"})
    assert deleted == 1
    remaining = await store.get("products", {"category": "fruit"})
    assert len(remaining) == 1

@pytest.mark.asyncio
async def test_vector_store_interface_compliance():
    """
    IVectorStore 인터페이스 준수 여부 검증
    """
    # Given: Mock Implementation
    class MockVectorStore(IVectorStore):
        async def add_documents(self, collection: str, documents: list[dict[str, Any]]) -> int:
            return len(documents)

        async def search(self, collection: str, query_vector: list[float], top_k: int, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
            # Mock return based on top_k
            return [{"id": f"doc_{i}", "score": 0.9 - (i * 0.1)} for i in range(top_k)]

        async def delete(self, collection: str, filters: dict[str, Any]) -> int:
            return 1

    # When
    vector_store = MockVectorStore()
    count = await vector_store.add_documents("docs", [{"content": "hello", "vector": [0.1, 0.2]}])
    results = await vector_store.search("docs", [0.1, 0.2], top_k=2)

    # Then
    assert count == 1
    assert len(results) == 2
    assert results[0]["score"] > results[1]["score"]
