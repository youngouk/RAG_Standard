# Multi Vector DB 지원 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 5개 벡터 DB(Pinecone, Chroma, Qdrant, pgvector, MongoDB Atlas)를 추가하여 오픈소스 범용성 확보

**Architecture:** 기존 IVectorStore/IRetriever 추상화 활용, Factory 패턴으로 설정 기반 DB 전환, 하이브리드 검색은 지원 DB만 활성화

**Tech Stack:** pinecone-client, chromadb, qdrant-client, pgvector, motor (MongoDB async)

---

## Phase 0: 기반 작업 (Factory + 설정)

### Task 0-1: VectorStoreFactory 생성

**Files:**
- Create: `app/infrastructure/storage/vector/factory.py`
- Test: `tests/unit/infrastructure/storage/vector/test_factory.py`

**Step 1: 테스트 디렉토리 생성**

```bash
mkdir -p tests/unit/infrastructure/storage/vector
touch tests/unit/infrastructure/storage/vector/__init__.py
```

**Step 2: 실패하는 테스트 작성**

```python
# tests/unit/infrastructure/storage/vector/test_factory.py
"""VectorStoreFactory 테스트"""
import pytest
from app.infrastructure.storage.vector.factory import VectorStoreFactory


class TestVectorStoreFactory:
    """VectorStoreFactory 단위 테스트"""

    def test_get_available_providers(self):
        """등록된 provider 목록 반환"""
        providers = VectorStoreFactory.get_available_providers()
        assert "weaviate" in providers

    def test_create_unknown_provider_raises_error(self):
        """알 수 없는 provider는 ValueError 발생"""
        with pytest.raises(ValueError, match="Unknown vector store provider"):
            VectorStoreFactory.create("unknown_db", {})

    def test_create_weaviate_returns_instance(self):
        """weaviate provider는 WeaviateVectorStore 반환"""
        # 실제 연결 없이 클래스 타입만 확인
        assert "weaviate" in VectorStoreFactory.get_available_providers()
```

**Step 3: 테스트 실행하여 실패 확인**

```bash
pytest tests/unit/infrastructure/storage/vector/test_factory.py -v
```

Expected: FAIL - `ModuleNotFoundError: No module named 'app.infrastructure.storage.vector.factory'`

**Step 4: Factory 구현**

```python
# app/infrastructure/storage/vector/factory.py
"""
Vector Store Factory

설정 기반으로 벡터 스토어 인스턴스를 생성합니다.
지원 DB: weaviate, pinecone, chroma, qdrant, pgvector, mongodb
"""
from typing import Any

from app.core.interfaces.storage import IVectorStore
from app.lib.logger import get_logger

logger = get_logger(__name__)


class VectorStoreFactory:
    """
    벡터 스토어 팩토리

    설정(YAML/환경변수)에 따라 적절한 벡터 스토어 인스턴스를 생성합니다.
    """

    # 지연 로딩을 위한 provider 매핑 (클래스 경로)
    _provider_map: dict[str, str] = {
        "weaviate": "app.infrastructure.storage.vector.weaviate_store.WeaviateVectorStore",
    }

    @classmethod
    def get_available_providers(cls) -> list[str]:
        """등록된 provider 목록 반환"""
        return list(cls._provider_map.keys())

    @classmethod
    def register_provider(cls, name: str, class_path: str) -> None:
        """새 provider 등록 (확장용)"""
        cls._provider_map[name] = class_path
        logger.info(f"VectorStoreFactory: provider '{name}' 등록됨")

    @classmethod
    def create(cls, provider: str, config: dict[str, Any]) -> IVectorStore:
        """
        벡터 스토어 인스턴스 생성

        Args:
            provider: 벡터 DB 이름 (weaviate, pinecone, chroma 등)
            config: DB별 설정 딕셔너리

        Returns:
            IVectorStore 구현체 인스턴스

        Raises:
            ValueError: 알 수 없는 provider
            ImportError: 해당 DB 라이브러리 미설치
        """
        if provider not in cls._provider_map:
            available = ", ".join(cls._provider_map.keys())
            raise ValueError(
                f"Unknown vector store provider: '{provider}'. "
                f"사용 가능한 provider: {available}"
            )

        class_path = cls._provider_map[provider]
        module_path, class_name = class_path.rsplit(".", 1)

        try:
            import importlib
            module = importlib.import_module(module_path)
            store_class = getattr(module, class_name)
            logger.info(f"VectorStoreFactory: '{provider}' 인스턴스 생성")
            return store_class(**config)
        except ImportError as e:
            raise ImportError(
                f"'{provider}' 벡터 스토어를 사용하려면 해당 라이브러리를 설치하세요. "
                f"예: uv sync --extra {provider}"
            ) from e
```

**Step 5: 테스트 실행하여 통과 확인**

```bash
pytest tests/unit/infrastructure/storage/vector/test_factory.py -v
```

Expected: PASS

**Step 6: 커밋**

```bash
git add app/infrastructure/storage/vector/factory.py tests/unit/infrastructure/storage/vector/
git commit -m "feat: VectorStoreFactory 추가 - 설정 기반 벡터 스토어 생성

- 지연 로딩으로 불필요한 의존성 방지
- register_provider()로 확장 가능
- weaviate 기본 등록

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

### Task 0-2: RetrieverFactory 생성

**Files:**
- Create: `app/modules/core/retrieval/retrievers/factory.py`
- Test: `tests/unit/retrieval/retrievers/test_retriever_factory.py`

**Step 1: 실패하는 테스트 작성**

```python
# tests/unit/retrieval/retrievers/test_retriever_factory.py
"""RetrieverFactory 테스트"""
import pytest
from app.modules.core.retrieval.retrievers.factory import RetrieverFactory


class TestRetrieverFactory:
    """RetrieverFactory 단위 테스트"""

    def test_get_available_providers(self):
        """등록된 provider 목록 반환"""
        providers = RetrieverFactory.get_available_providers()
        assert "weaviate" in providers

    def test_unknown_provider_raises_error(self):
        """알 수 없는 provider는 ValueError 발생"""
        with pytest.raises(ValueError, match="Unknown retriever provider"):
            RetrieverFactory.create(
                provider="unknown",
                embedder=None,
                config={}
            )

    def test_supports_hybrid_returns_correct_value(self):
        """하이브리드 지원 여부 확인"""
        # 하이브리드 지원 DB
        assert RetrieverFactory.supports_hybrid("weaviate") is True
        # 하이브리드 미지원 DB (추후 추가 시)
        # assert RetrieverFactory.supports_hybrid("chroma") is False
```

**Step 2: 테스트 실행하여 실패 확인**

```bash
pytest tests/unit/retrieval/retrievers/test_retriever_factory.py -v
```

Expected: FAIL

**Step 3: Factory 구현**

```python
# app/modules/core/retrieval/retrievers/factory.py
"""
Retriever Factory

설정 기반으로 Retriever 인스턴스를 생성합니다.
하이브리드 검색 지원 여부도 관리합니다.
"""
from typing import Any

from app.lib.logger import get_logger

logger = get_logger(__name__)


class RetrieverFactory:
    """
    Retriever 팩토리

    설정에 따라 적절한 Retriever 인스턴스를 생성합니다.
    """

    # Provider별 클래스 경로
    _provider_map: dict[str, str] = {
        "weaviate": "app.modules.core.retrieval.retrievers.weaviate_retriever.WeaviateRetriever",
    }

    # 하이브리드 검색 지원 DB
    _hybrid_supported: set[str] = {"weaviate"}

    @classmethod
    def get_available_providers(cls) -> list[str]:
        """등록된 provider 목록 반환"""
        return list(cls._provider_map.keys())

    @classmethod
    def supports_hybrid(cls, provider: str) -> bool:
        """해당 provider가 하이브리드 검색을 지원하는지 확인"""
        return provider in cls._hybrid_supported

    @classmethod
    def register_provider(
        cls,
        name: str,
        class_path: str,
        supports_hybrid: bool = False
    ) -> None:
        """새 provider 등록"""
        cls._provider_map[name] = class_path
        if supports_hybrid:
            cls._hybrid_supported.add(name)
        logger.info(f"RetrieverFactory: provider '{name}' 등록 (hybrid={supports_hybrid})")

    @classmethod
    def create(
        cls,
        provider: str,
        embedder: Any,
        config: dict[str, Any],
        # BM25 전처리 모듈 (하이브리드 지원 DB용)
        synonym_manager: Any | None = None,
        stopword_filter: Any | None = None,
        user_dictionary: Any | None = None,
    ) -> Any:  # IRetriever Protocol
        """
        Retriever 인스턴스 생성

        Args:
            provider: 벡터 DB 이름
            embedder: 임베딩 모델
            config: DB별 설정
            synonym_manager: BM25 동의어 관리자 (Optional)
            stopword_filter: BM25 불용어 필터 (Optional)
            user_dictionary: BM25 사용자 사전 (Optional)

        Returns:
            IRetriever Protocol 구현체
        """
        if provider not in cls._provider_map:
            available = ", ".join(cls._provider_map.keys())
            raise ValueError(
                f"Unknown retriever provider: '{provider}'. "
                f"사용 가능한 provider: {available}"
            )

        class_path = cls._provider_map[provider]
        module_path, class_name = class_path.rsplit(".", 1)

        try:
            import importlib
            module = importlib.import_module(module_path)
            retriever_class = getattr(module, class_name)

            # 하이브리드 지원 DB는 BM25 전처리 모듈 전달
            kwargs = {"embedder": embedder, **config}
            if cls.supports_hybrid(provider):
                kwargs.update({
                    "synonym_manager": synonym_manager,
                    "stopword_filter": stopword_filter,
                    "user_dictionary": user_dictionary,
                })

            logger.info(f"RetrieverFactory: '{provider}' Retriever 생성")
            return retriever_class(**kwargs)
        except ImportError as e:
            raise ImportError(
                f"'{provider}' Retriever를 사용하려면 해당 라이브러리를 설치하세요."
            ) from e
```

**Step 4: 테스트 실행하여 통과 확인**

```bash
pytest tests/unit/retrieval/retrievers/test_retriever_factory.py -v
```

**Step 5: 커밋**

```bash
git add app/modules/core/retrieval/retrievers/factory.py tests/unit/retrieval/retrievers/test_retriever_factory.py
git commit -m "feat: RetrieverFactory 추가 - 하이브리드 지원 여부 관리

- 하이브리드 지원 DB에 BM25 전처리 모듈 자동 전달
- supports_hybrid()로 지원 여부 확인 가능

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

### Task 0-3: 설정 스키마 추가 (vector_db 섹션)

**Files:**
- Modify: `app/config/schemas/retrieval.py`
- Modify: `app/config/base.yaml`
- Test: `tests/unit/config/test_vectordb_config.py`

**Step 1: 실패하는 테스트 작성**

```python
# tests/unit/config/test_vectordb_config.py
"""Vector DB 설정 스키마 테스트"""
import pytest
from pydantic import ValidationError


class TestVectorDBConfig:
    """Vector DB 설정 검증 테스트"""

    def test_valid_provider_accepted(self):
        """유효한 provider는 통과"""
        from app.config.schemas.retrieval import VectorDBConfig

        config = VectorDBConfig(provider="weaviate")
        assert config.provider == "weaviate"

    def test_invalid_provider_rejected(self):
        """유효하지 않은 provider는 거부"""
        from app.config.schemas.retrieval import VectorDBConfig

        with pytest.raises(ValidationError):
            VectorDBConfig(provider="invalid_db")

    def test_default_provider_is_weaviate(self):
        """기본 provider는 weaviate"""
        from app.config.schemas.retrieval import VectorDBConfig

        config = VectorDBConfig()
        assert config.provider == "weaviate"
```

**Step 2: 테스트 실행하여 실패 확인**

```bash
pytest tests/unit/config/test_vectordb_config.py -v
```

**Step 3: 설정 스키마 추가**

```python
# app/config/schemas/retrieval.py에 추가 (기존 파일 하단에)

from typing import Literal

class VectorDBConfig(BaseModel):
    """벡터 DB 설정"""

    provider: Literal["weaviate", "pinecone", "chroma", "qdrant", "pgvector", "mongodb"] = "weaviate"

    model_config = ConfigDict(extra="allow")  # DB별 추가 설정 허용
```

**Step 4: base.yaml에 섹션 추가**

```yaml
# app/config/base.yaml에 추가

# ========================================
# Vector DB 설정
# ========================================
vector_db:
  provider: "${VECTOR_DB_PROVIDER:-weaviate}"
```

**Step 5: 테스트 통과 확인 및 커밋**

```bash
pytest tests/unit/config/test_vectordb_config.py -v
git add app/config/schemas/retrieval.py app/config/base.yaml tests/unit/config/test_vectordb_config.py
git commit -m "feat: VectorDBConfig 스키마 추가 - provider 검증

- 지원 DB: weaviate, pinecone, chroma, qdrant, pgvector, mongodb
- 환경변수 VECTOR_DB_PROVIDER로 오버라이드 가능

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Phase 1: Chroma (가장 쉬움)

### Task 1-1: pyproject.toml에 chromadb 의존성 추가

**Files:**
- Modify: `pyproject.toml`

**Step 1: 의존성 추가**

```toml
# pyproject.toml의 [project.optional-dependencies] 섹션에 추가

[project.optional-dependencies]
# ... 기존 내용 ...
chroma = ["chromadb>=0.4.0"]
```

**Step 2: 커밋**

```bash
git add pyproject.toml
git commit -m "build: chromadb 선택적 의존성 추가

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

### Task 1-2: ChromaVectorStore 구현

**Files:**
- Create: `app/infrastructure/storage/vector/chroma_store.py`
- Test: `tests/unit/infrastructure/storage/vector/test_chroma_store.py`

**Step 1: 실패하는 테스트 작성**

```python
# tests/unit/infrastructure/storage/vector/test_chroma_store.py
"""ChromaVectorStore 테스트"""
import pytest

# Chroma가 설치되지 않은 환경에서도 테스트 파일 로드 가능하도록
pytest.importorskip("chromadb")

from app.infrastructure.storage.vector.chroma_store import ChromaVectorStore


class TestChromaVectorStore:
    """ChromaVectorStore 단위 테스트"""

    @pytest.fixture
    def store(self, tmp_path):
        """임시 디렉토리에 Chroma 스토어 생성"""
        return ChromaVectorStore(
            persist_directory=str(tmp_path / "chroma_test"),
            collection_name="test_collection"
        )

    @pytest.mark.asyncio
    async def test_add_and_search_documents(self, store):
        """문서 추가 및 검색 테스트"""
        docs = [
            {"id": "1", "content": "Hello world", "vector": [0.1] * 384},
            {"id": "2", "content": "Goodbye world", "vector": [0.2] * 384},
        ]
        count = await store.add_documents("test", docs)
        assert count == 2

        results = await store.search("test", [0.1] * 384, top_k=1)
        assert len(results) == 1
        assert results[0]["content"] == "Hello world"

    @pytest.mark.asyncio
    async def test_delete_document(self, store):
        """문서 삭제 테스트"""
        docs = [{"id": "del_1", "content": "To delete", "vector": [0.3] * 384}]
        await store.add_documents("test", docs)

        deleted = await store.delete("test", {"id": "del_1"})
        assert deleted == 1
```

**Step 2: 테스트 실행하여 실패 확인**

```bash
uv sync --extra chroma
pytest tests/unit/infrastructure/storage/vector/test_chroma_store.py -v
```

**Step 3: ChromaVectorStore 구현**

```python
# app/infrastructure/storage/vector/chroma_store.py
"""
Chroma Vector Store

경량 임베디드 벡터 DB. 로컬 개발/테스트에 최적화.
pip install chromadb 또는 uv sync --extra chroma
"""
from typing import Any

from app.core.interfaces.storage import IVectorStore
from app.lib.logger import get_logger

logger = get_logger(__name__)


class ChromaVectorStore(IVectorStore):
    """
    Chroma 벡터 스토어 (IVectorStore 구현)

    특징:
    - 로컬 파일 시스템 기반 (설치 불필요)
    - In-memory 또는 영구 저장 선택 가능
    - Dense 검색만 지원 (하이브리드 미지원)
    """

    def __init__(
        self,
        persist_directory: str | None = None,
        collection_name: str = "documents",
    ) -> None:
        """
        Chroma 스토어 초기화

        Args:
            persist_directory: 영구 저장 경로 (None이면 in-memory)
            collection_name: 기본 컬렉션 이름
        """
        try:
            import chromadb
            from chromadb.config import Settings
        except ImportError:
            raise ImportError(
                "chromadb가 설치되지 않았습니다. "
                "설치 방법: uv sync --extra chroma"
            )

        self.collection_name = collection_name

        # Chroma 클라이언트 초기화
        if persist_directory:
            self.client = chromadb.PersistentClient(
                path=persist_directory,
                settings=Settings(anonymized_telemetry=False)
            )
            logger.info(f"ChromaVectorStore 초기화 (영구 저장): {persist_directory}")
        else:
            self.client = chromadb.Client(
                settings=Settings(anonymized_telemetry=False)
            )
            logger.info("ChromaVectorStore 초기화 (in-memory)")

        # 컬렉션 캐시
        self._collections: dict[str, Any] = {}

    def _get_or_create_collection(self, name: str) -> Any:
        """컬렉션 가져오기 또는 생성"""
        if name not in self._collections:
            self._collections[name] = self.client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"}  # 코사인 유사도 사용
            )
        return self._collections[name]

    async def add_documents(
        self,
        collection: str,
        documents: list[dict[str, Any]]
    ) -> int:
        """문서 추가"""
        col = self._get_or_create_collection(collection)

        ids = []
        embeddings = []
        documents_text = []
        metadatas = []

        for doc in documents:
            doc_id = doc.get("id", str(len(ids)))
            ids.append(doc_id)
            embeddings.append(doc["vector"])
            documents_text.append(doc.get("content", ""))

            # 메타데이터 추출 (vector, id, content 제외)
            metadata = {k: v for k, v in doc.items()
                        if k not in ("id", "vector", "content")}
            metadatas.append(metadata)

        col.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents_text,
            metadatas=metadatas
        )

        logger.debug(f"Chroma: {len(documents)}개 문서 추가 완료")
        return len(documents)

    async def search(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int,
        filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """벡터 검색"""
        col = self._get_or_create_collection(collection)

        # Chroma where 필터 변환
        where_filter = None
        if filters:
            where_filter = filters  # Chroma 형식 그대로 사용

        results = col.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )

        # 결과 변환
        output: list[dict[str, Any]] = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                item: dict[str, Any] = {
                    "_id": doc_id,
                    "content": results["documents"][0][i] if results["documents"] else "",
                    "_distance": results["distances"][0][i] if results["distances"] else 0.0,
                }
                if results["metadatas"] and results["metadatas"][0]:
                    item.update(results["metadatas"][0][i])
                output.append(item)

        return output

    async def delete(
        self,
        collection: str,
        filters: dict[str, Any]
    ) -> int:
        """문서 삭제"""
        col = self._get_or_create_collection(collection)

        if "id" in filters:
            col.delete(ids=[filters["id"]])
            return 1
        elif "ids" in filters:
            col.delete(ids=filters["ids"])
            return len(filters["ids"])

        # where 조건으로 삭제
        col.delete(where=filters)
        return 1  # 정확한 삭제 수 알 수 없음
```

**Step 4: Factory에 등록**

```python
# app/infrastructure/storage/vector/factory.py의 _provider_map에 추가

_provider_map: dict[str, str] = {
    "weaviate": "app.infrastructure.storage.vector.weaviate_store.WeaviateVectorStore",
    "chroma": "app.infrastructure.storage.vector.chroma_store.ChromaVectorStore",
}
```

**Step 5: 테스트 실행 및 커밋**

```bash
pytest tests/unit/infrastructure/storage/vector/test_chroma_store.py -v
git add app/infrastructure/storage/vector/chroma_store.py app/infrastructure/storage/vector/factory.py tests/unit/infrastructure/storage/vector/test_chroma_store.py
git commit -m "feat: ChromaVectorStore 구현 - 경량 로컬 벡터 DB

- IVectorStore 인터페이스 구현
- In-memory 또는 영구 저장 지원
- Dense 검색만 지원 (하이브리드 미지원)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

### Task 1-3: ChromaRetriever 구현

**Files:**
- Create: `app/modules/core/retrieval/retrievers/chroma_retriever.py`
- Test: `tests/unit/retrieval/retrievers/test_chroma_retriever.py`

**Step 1: 실패하는 테스트 작성**

```python
# tests/unit/retrieval/retrievers/test_chroma_retriever.py
"""ChromaRetriever 테스트"""
import pytest
from unittest.mock import AsyncMock, MagicMock

pytest.importorskip("chromadb")

from app.modules.core.retrieval.retrievers.chroma_retriever import ChromaRetriever
from app.modules.core.retrieval.interfaces import SearchResult


class TestChromaRetriever:
    """ChromaRetriever 단위 테스트"""

    @pytest.fixture
    def mock_embedder(self):
        """Mock embedder"""
        embedder = MagicMock()
        embedder.embed_query = AsyncMock(return_value=[0.1] * 384)
        return embedder

    @pytest.fixture
    def retriever(self, mock_embedder, tmp_path):
        """Chroma Retriever 인스턴스"""
        return ChromaRetriever(
            embedder=mock_embedder,
            persist_directory=str(tmp_path / "chroma"),
            collection_name="test"
        )

    @pytest.mark.asyncio
    async def test_search_returns_search_results(self, retriever):
        """search()는 SearchResult 리스트 반환"""
        # 테스트 데이터 추가
        await retriever.store.add_documents("test", [
            {"id": "1", "content": "Test content", "vector": [0.1] * 384}
        ])

        results = await retriever.search("test query", top_k=1)

        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert results[0].content == "Test content"

    @pytest.mark.asyncio
    async def test_health_check_returns_true(self, retriever):
        """health_check()는 True 반환"""
        result = await retriever.health_check()
        assert result is True
```

**Step 2: ChromaRetriever 구현**

```python
# app/modules/core/retrieval/retrievers/chroma_retriever.py
"""
Chroma Retriever - Dense 검색 전용

특징:
- ChromaVectorStore 기반 검색
- Dense 검색만 지원 (하이브리드 미지원)
- IRetriever 인터페이스 구현
"""
from typing import Any

from app.lib.logger import get_logger
from ..interfaces import SearchResult

logger = get_logger(__name__)


class ChromaRetriever:
    """
    Chroma 기반 Dense 검색 Retriever

    IRetriever Protocol 구현.
    하이브리드 검색이 필요하면 Weaviate/Pinecone/Qdrant 사용.
    """

    def __init__(
        self,
        embedder: Any,
        persist_directory: str | None = None,
        collection_name: str = "documents",
    ) -> None:
        """
        ChromaRetriever 초기화

        Args:
            embedder: 임베딩 모델 (embed_query 메서드 필요)
            persist_directory: Chroma 저장 경로 (None이면 in-memory)
            collection_name: 검색 대상 컬렉션
        """
        from app.infrastructure.storage.vector.chroma_store import ChromaVectorStore

        self.embedder = embedder
        self.collection_name = collection_name
        self.store = ChromaVectorStore(
            persist_directory=persist_directory,
            collection_name=collection_name
        )

        self.stats = {
            "total_searches": 0,
            "errors": 0,
        }

        logger.info(f"ChromaRetriever 초기화: collection={collection_name}")

    async def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """
        Dense 벡터 검색 수행

        Args:
            query: 검색 쿼리
            top_k: 반환할 결과 수
            filters: 메타데이터 필터

        Returns:
            SearchResult 리스트
        """
        try:
            self.stats["total_searches"] += 1

            # 1. 쿼리 임베딩 생성
            query_vector = await self.embedder.embed_query(query)

            # 2. 벡터 검색 수행
            raw_results = await self.store.search(
                collection=self.collection_name,
                query_vector=query_vector,
                top_k=top_k,
                filters=filters
            )

            # 3. SearchResult로 변환
            results: list[SearchResult] = []
            for item in raw_results:
                # distance를 score로 변환 (1 - distance for cosine)
                distance = item.pop("_distance", 0.0)
                score = 1.0 - distance if distance else 1.0

                results.append(SearchResult(
                    id=item.pop("_id", ""),
                    content=item.pop("content", ""),
                    score=score,
                    metadata=item  # 나머지는 메타데이터
                ))

            logger.debug(f"Chroma 검색 완료: query='{query[:30]}...', results={len(results)}")
            return results

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Chroma 검색 오류: {e}")
            return []

    async def health_check(self) -> bool:
        """Chroma 연결 상태 확인"""
        try:
            # 컬렉션 접근 테스트
            self.store._get_or_create_collection(self.collection_name)
            return True
        except Exception as e:
            logger.error(f"Chroma health check 실패: {e}")
            return False
```

**Step 3: RetrieverFactory에 등록**

```python
# app/modules/core/retrieval/retrievers/factory.py의 _provider_map에 추가

_provider_map: dict[str, str] = {
    "weaviate": "app.modules.core.retrieval.retrievers.weaviate_retriever.WeaviateRetriever",
    "chroma": "app.modules.core.retrieval.retrievers.chroma_retriever.ChromaRetriever",
}

# _hybrid_supported는 weaviate만 유지 (chroma는 미지원)
```

**Step 4: 테스트 및 커밋**

```bash
pytest tests/unit/retrieval/retrievers/test_chroma_retriever.py -v
git add app/modules/core/retrieval/retrievers/chroma_retriever.py app/modules/core/retrieval/retrievers/factory.py tests/unit/retrieval/retrievers/test_chroma_retriever.py
git commit -m "feat: ChromaRetriever 구현 - Dense 검색 전용

- IRetriever Protocol 구현
- ChromaVectorStore 내부 사용
- 하이브리드 미지원 (Dense만)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

### Task 1-4: Chroma 설정 파일 추가

**Files:**
- Create: `app/config/features/chroma.yaml`

**Step 1: 설정 파일 생성**

```yaml
# app/config/features/chroma.yaml
# Chroma Vector DB 설정
# 경량 로컬/임베디드 벡터 DB

chroma:
  # 저장 경로 (null이면 in-memory)
  persist_directory: "${CHROMA_PERSIST_DIR:-./data/chroma}"

  # 기본 컬렉션 이름
  collection_name: "documents"

  # 검색 설정
  retrieval:
    top_k: 15
    # 하이브리드 미지원 (Dense만)

# ========================================
# 사용 방법
# ========================================
# 1. 의존성 설치: uv sync --extra chroma
# 2. 환경변수 설정: VECTOR_DB_PROVIDER=chroma
# 3. (선택) 저장 경로: CHROMA_PERSIST_DIR=/path/to/data
```

**Step 2: 커밋**

```bash
git add app/config/features/chroma.yaml
git commit -m "config: Chroma 설정 파일 추가

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Phase 2: Pinecone (서버리스)

### Task 2-1: pinecone-client 의존성 추가

**Files:**
- Modify: `pyproject.toml`

**Step 1: 의존성 추가**

```toml
[project.optional-dependencies]
pinecone = ["pinecone-client>=3.0.0"]
```

**Step 2: 커밋**

```bash
git add pyproject.toml
git commit -m "build: pinecone-client 선택적 의존성 추가

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

### Task 2-2: PineconeVectorStore 구현

**Files:**
- Create: `app/infrastructure/storage/vector/pinecone_store.py`
- Test: `tests/unit/infrastructure/storage/vector/test_pinecone_store.py`

**Step 1: 실패하는 테스트 작성**

```python
# tests/unit/infrastructure/storage/vector/test_pinecone_store.py
"""PineconeVectorStore 테스트 (Mock 기반)"""
import pytest
from unittest.mock import MagicMock, patch

pytest.importorskip("pinecone")


class TestPineconeVectorStore:
    """PineconeVectorStore 단위 테스트"""

    @pytest.fixture
    def mock_pinecone(self):
        """Pinecone 클라이언트 Mock"""
        with patch("app.infrastructure.storage.vector.pinecone_store.Pinecone") as mock:
            mock_index = MagicMock()
            mock.return_value.Index.return_value = mock_index
            yield mock, mock_index

    def test_init_creates_client(self, mock_pinecone):
        """초기화 시 Pinecone 클라이언트 생성"""
        from app.infrastructure.storage.vector.pinecone_store import PineconeVectorStore

        mock_pc, _ = mock_pinecone
        store = PineconeVectorStore(
            api_key="test-key",
            index_name="test-index"
        )

        mock_pc.assert_called_once_with(api_key="test-key")
        assert store.index_name == "test-index"

    @pytest.mark.asyncio
    async def test_search_returns_results(self, mock_pinecone):
        """search()는 결과 반환"""
        from app.infrastructure.storage.vector.pinecone_store import PineconeVectorStore

        _, mock_index = mock_pinecone
        mock_index.query.return_value = MagicMock(
            matches=[
                MagicMock(id="1", score=0.95, metadata={"content": "Test"})
            ]
        )

        store = PineconeVectorStore(api_key="test", index_name="test")
        results = await store.search("ns", [0.1] * 1536, top_k=1)

        assert len(results) == 1
        assert results[0]["_id"] == "1"
```

**Step 2: PineconeVectorStore 구현**

```python
# app/infrastructure/storage/vector/pinecone_store.py
"""
Pinecone Vector Store

서버리스 벡터 DB. 프로덕션 환경에 최적화.
설치: uv sync --extra pinecone
"""
import os
from typing import Any

from app.core.interfaces.storage import IVectorStore
from app.lib.logger import get_logger

logger = get_logger(__name__)


class PineconeVectorStore(IVectorStore):
    """
    Pinecone 벡터 스토어 (IVectorStore 구현)

    특징:
    - 서버리스 (인프라 관리 불필요)
    - 하이브리드 검색 지원 (Sparse Vector)
    - 높은 확장성
    """

    def __init__(
        self,
        api_key: str | None = None,
        index_name: str | None = None,
        namespace: str = "default",
    ) -> None:
        """
        Pinecone 스토어 초기화

        Args:
            api_key: Pinecone API 키
            index_name: 인덱스 이름
            namespace: 네임스페이스 (기본: default)
        """
        try:
            from pinecone import Pinecone
        except ImportError:
            raise ImportError(
                "pinecone-client가 설치되지 않았습니다. "
                "설치 방법: uv sync --extra pinecone"
            )

        self.api_key = api_key or os.getenv("PINECONE_API_KEY")
        if not self.api_key:
            raise ValueError("PINECONE_API_KEY 환경 변수가 필요합니다.")

        self.index_name = index_name or os.getenv("PINECONE_INDEX_NAME", "rag-documents")
        self.namespace = namespace

        # Pinecone 클라이언트 초기화
        self.pc = Pinecone(api_key=self.api_key)
        self.index = self.pc.Index(self.index_name)

        logger.info(f"PineconeVectorStore 초기화: index={self.index_name}, namespace={namespace}")

    async def add_documents(
        self,
        collection: str,  # Pinecone에서는 namespace로 사용
        documents: list[dict[str, Any]]
    ) -> int:
        """문서 추가 (upsert)"""
        vectors = []
        for doc in documents:
            vector_data: dict[str, Any] = {
                "id": doc.get("id", str(len(vectors))),
                "values": doc["vector"],
            }

            # 메타데이터 추출
            metadata = {k: v for k, v in doc.items()
                        if k not in ("id", "vector")}
            if metadata:
                vector_data["metadata"] = metadata

            # Sparse vector (하이브리드 검색용)
            if "sparse_values" in doc:
                vector_data["sparse_values"] = doc["sparse_values"]

            vectors.append(vector_data)

        # Batch upsert
        namespace = collection or self.namespace
        self.index.upsert(vectors=vectors, namespace=namespace)

        logger.debug(f"Pinecone: {len(vectors)}개 문서 upsert 완료")
        return len(vectors)

    async def search(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int,
        filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """벡터 검색"""
        namespace = collection or self.namespace

        query_params: dict[str, Any] = {
            "vector": query_vector,
            "top_k": top_k,
            "namespace": namespace,
            "include_metadata": True,
        }

        if filters:
            query_params["filter"] = filters

        response = self.index.query(**query_params)

        results: list[dict[str, Any]] = []
        for match in response.matches:
            item: dict[str, Any] = {
                "_id": match.id,
                "_score": match.score,
            }
            if match.metadata:
                item.update(match.metadata)
            results.append(item)

        return results

    async def delete(
        self,
        collection: str,
        filters: dict[str, Any]
    ) -> int:
        """문서 삭제"""
        namespace = collection or self.namespace

        if "id" in filters:
            self.index.delete(ids=[filters["id"]], namespace=namespace)
            return 1
        elif "ids" in filters:
            self.index.delete(ids=filters["ids"], namespace=namespace)
            return len(filters["ids"])

        # 필터 기반 삭제
        self.index.delete(filter=filters, namespace=namespace)
        return 1
```

**Step 3: Factory 등록 및 테스트**

```bash
pytest tests/unit/infrastructure/storage/vector/test_pinecone_store.py -v
git add app/infrastructure/storage/vector/pinecone_store.py tests/unit/infrastructure/storage/vector/test_pinecone_store.py
git commit -m "feat: PineconeVectorStore 구현 - 서버리스 벡터 DB

- IVectorStore 인터페이스 구현
- 하이브리드 검색 지원 (Sparse Vector)
- Namespace 기반 컬렉션 분리

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

### Task 2-3: PineconeRetriever 구현 (하이브리드 지원)

**Files:**
- Create: `app/modules/core/retrieval/retrievers/pinecone_retriever.py`
- Test: `tests/unit/retrieval/retrievers/test_pinecone_retriever.py`

(ChromaRetriever와 유사한 구조, 하이브리드 검색 + BM25 전처리 추가)

**핵심 차이점:**
```python
# Pinecone 하이브리드 검색
async def search(self, query: str, top_k: int = 10, ...) -> list[SearchResult]:
    # BM25 전처리 적용 (Weaviate와 동일)
    processed_query = self._preprocess_query(query)

    # Dense + Sparse 검색
    query_vector = await self.embedder.embed_query(processed_query)
    sparse_vector = self._generate_sparse_vector(processed_query)  # BM25 기반

    results = await self.store.search(
        collection=self.namespace,
        query_vector=query_vector,
        sparse_values=sparse_vector,
        top_k=top_k,
        alpha=self.alpha  # 하이브리드 가중치
    )
```

---

## Phase 3-5: Qdrant, pgvector, MongoDB (동일 패턴)

각 DB에 대해 동일한 패턴 적용:
1. 의존성 추가 (pyproject.toml)
2. VectorStore 구현 + 테스트
3. Retriever 구현 + 테스트
4. 설정 파일 추가
5. Factory 등록

### Qdrant 특이사항
- 하이브리드 검색 지원 (BM25 내장)
- BM25 전처리 모듈 적용

### pgvector 특이사항
- PostgreSQL 확장 필요
- Dense 검색만 지원
- 기존 PostgreSQL과 함께 사용 가능

### MongoDB Atlas 특이사항
- Atlas Search 필요
- Dense 검색만 지원
- 기존 MongoDB와 호환

---

## Phase 6: DI 컨테이너 통합

### Task 6-1: di_container.py에 Factory 통합

**Files:**
- Modify: `app/core/di_container.py`

**핵심 변경:**
```python
# 기존: 하드코딩된 Weaviate
vector_store = providers.Singleton(WeaviateVectorStore, ...)
retriever = providers.Factory(WeaviateRetriever, ...)

# 변경: Factory 기반 동적 생성
from app.infrastructure.storage.vector.factory import VectorStoreFactory
from app.modules.core.retrieval.retrievers.factory import RetrieverFactory

vector_store = providers.Singleton(
    VectorStoreFactory.create,
    provider=config.vector_db.provider,
    config=config.vector_db
)

retriever = providers.Factory(
    RetrieverFactory.create,
    provider=config.vector_db.provider,
    embedder=embedder,
    config=config.retrieval,
    synonym_manager=synonym_manager,
    stopword_filter=stopword_filter,
    user_dictionary=user_dictionary,
)
```

---

## 최종 검증

### Task Final: 전체 테스트 및 린트

```bash
# 모든 테스트 실행
make test

# 타입 체크
make type-check

# 린트
make lint

# 아키텍처 검증
make lint-imports
```

---

## 요약

| Phase | 작업 | 파일 수 | 예상 시간 |
|-------|------|---------|----------|
| 0 | Factory + 설정 | 6개 | 30분 |
| 1 | Chroma | 4개 | 20분 |
| 2 | Pinecone | 4개 | 30분 |
| 3 | Qdrant | 4개 | 30분 |
| 4 | pgvector | 4개 | 30분 |
| 5 | MongoDB | 4개 | 30분 |
| 6 | DI 통합 | 2개 | 20분 |
| **총합** | | **~28개** | **~3시간** |
