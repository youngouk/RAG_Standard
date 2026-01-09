# Multi Vector DB 지원 설계

> 작성일: 2026-01-09
> 상태: 설계 완료, 구현 대기

## 개요

RAG_Standard 프로젝트에 다양한 벡터 DB 지원을 추가하여 오픈소스 범용성을 높입니다.

### 목적
1. **오픈소스 배포 범용성** - 사용자가 선호하는 벡터 DB 선택 가능
2. **다양한 환경 지원** - 서버리스, 경량, NoSQL+Vector, SQL+Vector

### 추가할 벡터 DB

| 카테고리 | DB | 특징 |
|---------|-----|------|
| 서버리스 (벡터 전용) | Pinecone | 설치 불필요, SDK 최고 수준 |
| 경량 (벡터 전용) | Chroma | pip install만으로 사용, 로컬 테스트 최적 |
| 셀프호스팅 (벡터 전용) | Qdrant | Docker 1줄, 무료, 하이브리드 내장 |
| NoSQL + Vector | MongoDB Atlas | 문서 DB + 벡터 검색 |
| SQL + Vector | PostgreSQL + pgvector | 관계형 DB + 벡터 확장 |

---

## 아키텍처

### 기존 추상화 활용

프로젝트에 이미 확장 가능한 구조가 존재:

```
IVectorStore (저수준)     →  원시 벡터 저장/검색
       ↓
IRetriever (고수준)       →  텍스트 쿼리 기반 검색
       ↓
DI Container             →  설정에 따라 Provider 교체
```

### 파일 구조

```
app/
├── infrastructure/storage/vector/
│   ├── weaviate_store.py      # 기존
│   ├── pinecone_store.py      # 신규
│   ├── chroma_store.py        # 신규
│   ├── qdrant_store.py        # 신규
│   ├── mongodb_store.py       # 신규
│   ├── pgvector_store.py      # 신규
│   └── factory.py             # 신규 - VectorStoreFactory
│
├── modules/core/retrieval/retrievers/
│   ├── weaviate_retriever.py  # 기존
│   ├── pinecone_retriever.py  # 신규
│   ├── chroma_retriever.py    # 신규
│   ├── qdrant_retriever.py    # 신규
│   ├── mongodb_retriever.py   # 기존 (수정)
│   ├── pgvector_retriever.py  # 신규
│   └── factory.py             # 신규 - RetrieverFactory
│
├── config/features/
│   ├── weaviate.yaml          # 기존
│   ├── pinecone.yaml          # 신규
│   ├── chroma.yaml            # 신규
│   ├── qdrant.yaml            # 신규
│   ├── mongodb_vector.yaml    # 신규
│   └── pgvector.yaml          # 신규
```

---

## 설정 방식

### 기본 설정 (YAML)

```yaml
# base.yaml에 추가
vector_db:
  provider: "weaviate"  # weaviate | pinecone | chroma | qdrant | mongodb | pgvector
```

### 환경변수 오버라이드

```bash
VECTOR_DB_PROVIDER=pinecone
```

### DB별 상세 설정 예시

```yaml
# config/features/pinecone.yaml
pinecone:
  api_key: "${PINECONE_API_KEY}"
  environment: "${PINECONE_ENVIRONMENT}"
  index_name: "rag-documents"
  namespace: "default"

  retrieval:
    top_k: 15
    hybrid_alpha: 0.6  # Dense 가중치 (Sparse = 1 - alpha)
```

---

## 기능 지원 매트릭스

| DB | Dense | Hybrid (BM25) | BM25 전처리 | 비고 |
|----|-------|---------------|------------|------|
| Weaviate | ✅ | ✅ 내장 | ✅ 적용 | 기존 구현 |
| Pinecone | ✅ | ✅ 내장 (Sparse Vector) | ✅ 적용 | |
| Qdrant | ✅ | ✅ 내장 | ✅ 적용 | |
| Chroma | ✅ | ❌ | ❌ | Dense만 |
| MongoDB Atlas | ✅ | ❌ | ❌ | Dense만 |
| pgvector | ✅ | ❌ | ❌ | Dense만 |

### BM25 전처리 모듈

하이브리드 지원 DB(Weaviate, Pinecone, Qdrant)에 기존 BM25 전처리 적용:
- `SynonymManager` - 동의어 확장
- `StopwordFilter` - 불용어 제거
- `UserDictionary` - 합성어 보호

---

## 구현 우선순위

1. **Chroma** - 가장 쉬움, 로컬 테스트용 최적
2. **Pinecone** - 서버리스, 프로덕션 인기 1위
3. **Qdrant** - 셀프호스팅, 하이브리드 지원
4. **pgvector** - SQL 친화적 사용자용
5. **MongoDB Atlas** - NoSQL 사용자용

---

## Factory 패턴

### VectorStoreFactory

```python
class VectorStoreFactory:
    """설정 기반 벡터 스토어 생성"""

    _stores = {
        "weaviate": WeaviateVectorStore,
        "pinecone": PineconeVectorStore,
        "chroma": ChromaVectorStore,
        "qdrant": QdrantVectorStore,
        "mongodb": MongoDBVectorStore,
        "pgvector": PgVectorStore,
    }

    @classmethod
    def create(cls, provider: str, config: dict) -> IVectorStore:
        store_class = cls._stores.get(provider)
        if not store_class:
            raise ValueError(f"Unknown provider: {provider}")
        return store_class(**config)
```

### RetrieverFactory

```python
class RetrieverFactory:
    """설정 기반 리트리버 생성"""

    _retrievers = {
        "weaviate": WeaviateRetriever,
        "pinecone": PineconeRetriever,
        "chroma": ChromaRetriever,
        "qdrant": QdrantRetriever,
        "mongodb": MongoDBRetriever,
        "pgvector": PgVectorRetriever,
    }

    @classmethod
    def create(cls, provider: str, embedder, store, config: dict) -> IRetriever:
        retriever_class = cls._retrievers.get(provider)
        if not retriever_class:
            raise ValueError(f"Unknown provider: {provider}")
        return retriever_class(embedder=embedder, store=store, **config)
```

---

## 사용 예시

### 사용자 관점

```python
# 설정 파일만 바꾸면 DB 자동 전환
from app.core.di_container import Container

container = Container()
retriever = container.retriever()  # 설정에 따라 자동 선택

results = await retriever.search("검색어", top_k=10)
```

### 환경변수로 전환

```bash
# 개발 환경 - Chroma (로컬)
VECTOR_DB_PROVIDER=chroma

# 프로덕션 - Pinecone (서버리스)
VECTOR_DB_PROVIDER=pinecone
PINECONE_API_KEY=xxx
```

---

## 작업량 추정

| 항목 | 수량 |
|------|------|
| 신규 Store 파일 | 5개 |
| 신규 Retriever 파일 | 5개 |
| Factory 파일 | 2개 |
| 설정 파일 (YAML) | 5개 |
| 테스트 파일 | 10개 |
| **총 신규 파일** | **약 27개** |

### 기존 코드 수정
- `di_container.py` - Factory 등록
- `base.yaml` - vector_db 섹션 추가
- `config/schemas/` - 설정 스키마 추가

---

## 의존성 추가 (pyproject.toml)

```toml
[project.optional-dependencies]
pinecone = ["pinecone-client>=3.0.0"]
chroma = ["chromadb>=0.4.0"]
qdrant = ["qdrant-client>=1.7.0"]
pgvector = ["pgvector>=0.2.0", "asyncpg>=0.29.0"]
mongodb = ["motor>=3.3.0"]  # 기존에 있을 수 있음

# 전체 설치
all-vectordb = ["pinecone-client", "chromadb", "qdrant-client", "pgvector", "asyncpg"]
```

사용자는 필요한 DB만 선택 설치:
```bash
uv sync --extra pinecone
uv sync --extra chroma
uv sync --extra all-vectordb  # 전체
```

---

## 다음 단계

1. ✅ 설계 문서 작성 (본 문서)
2. ⏳ 구현 계획 수립
3. ⏳ 우선순위별 구현
4. ⏳ 테스트 및 문서화
