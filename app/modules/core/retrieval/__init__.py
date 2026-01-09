"""
Retrieval Module - 검색 및 리랭킹 모듈

이 패키지는 MongoDB 기반 하이브리드 검색을 제공합니다.

주요 구성:
- interfaces: 인터페이스 정의 (IRetriever, IReranker, ICacheManager)
- retrievers: 벡터 검색 구현 (MongoDB 하이브리드 검색 - Production)
- rerankers: 리랭킹 구현 (Gemini Flash, Jina, GPT-5 Nano)
- cache: 캐싱 구현 (MemoryCacheManager, RedisCacheManager)
- orchestrator: Facade 패턴으로 전체 조율

프로덕션 권장사항:
- ✅ MongoDBRetriever 사용 (Dense + Sparse BM25 하이브리드 검색)
- ✅ GeminiFlashReranker 사용 (빠르고 정확한 리랭킹)

사용 예시:
    from app.modules.core.retrieval import RetrievalOrchestrator
    from app.modules.core.retrieval.retrievers import MongoDBRetriever
    from app.modules.core.retrieval.rerankers import GeminiFlashReranker
    from app.modules.core.retrieval.cache import MemoryCacheManager

    retriever = MongoDBRetriever(embedder, collection_name="documents")
    reranker = GeminiFlashReranker(api_key=api_key)
    cache = MemoryCacheManager()

    orchestrator = RetrievalOrchestrator(
        retriever, reranker, cache, config
    )

    results = await orchestrator.search_and_rerank("query", top_k=10)
"""

# 인터페이스 및 데이터 모델 (항상 import 가능)
# 캐시 매니저 (완료)
from .cache.memory_cache import MemoryCacheManager
from .interfaces import (
    BaseCacheManager,
    BaseReranker,
    BaseRetriever,
    ICacheManager,
    IReranker,
    IRetriever,
    SearchResult,
)

# Orchestrator (Phase 2.4 완료)
from .orchestrator import RetrievalOrchestrator

# Query Expansion 인터페이스 및 데이터 모델
from .query_expansion.interface import (
    ExpandedQuery,
    IQueryExpansionEngine,
    QueryComplexity,
    SearchIntent,
)
from .rerankers.gemini_reranker import GeminiFlashReranker

# Reranker 구현체 (Phase 2.3 완료)
from .rerankers.jina_reranker import JinaReranker
from .rerankers.openai_llm_reranker import GPT5NanoReranker, OpenAILLMReranker

# Retriever 구현체 (Phase 2.2 완료)
# MongoDB Retriever (프로덕션 기본값)
# Dense Vector + Sparse BM25 하이브리드 검색
from .retrievers.mongodb_retriever import MongoDBRetriever

__all__ = [
    # 인터페이스
    "IRetriever",
    "IReranker",
    "ICacheManager",
    "BaseRetriever",
    "BaseReranker",
    "BaseCacheManager",
    # 데이터 모델
    "SearchResult",
    # 캐시 매니저
    "MemoryCacheManager",
    # Retriever 구현체
    "MongoDBRetriever",  # MongoDB 하이브리드 검색 (프로덕션)
    # Reranker 구현체
    "JinaReranker",
    "OpenAILLMReranker",
    "GPT5NanoReranker",  # deprecated - OpenAILLMReranker 사용 권장
    "GeminiFlashReranker",
    # Orchestrator (Facade)
    "RetrievalOrchestrator",
]
