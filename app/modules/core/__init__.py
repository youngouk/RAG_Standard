"""Core RAG pipeline modules.

이 패키지는 RAG 시스템의 핵심 파이프라인을 구성하는 모듈들을 포함합니다:
- 문서 처리 (Document Processing)
- 검색 및 재랭킹 (Retrieval & Reranking)
- 답변 생성 (Generation)
- 세션 관리 (Session Management)
- 쿼리 처리 (Query Processing)
"""

from .documents import DocumentProcessor
from .embedding import GeminiEmbedder, GeminiEmbeddings  # 하위 호환성 유지
from .generation import GenerationModule, GenerationResult, PromptManager
from .retrieval import QueryComplexity, RetrievalOrchestrator, SearchIntent
from .retrieval.interfaces import SearchResult
from .retrieval.query_expansion import ExpandedQuery, GPT5QueryExpansionEngine
from .routing import (
    ComplexityCalculator,
    ComplexityResult,
    LLMQueryRouter,
    QueryProfile,
    RoutingDecision,
    RuleBasedRouter,
    RuleMatch,
)
from .self_rag import SelfRAGOrchestrator, SelfRAGResult
from .session import EnhancedSessionModule  # Phase 1.5: session 폴더로 이동

__all__ = [
    # Document Processing
    "DocumentProcessor",
    "GeminiEmbeddings",  # 하위 호환성
    "GeminiEmbedder",  # 새로운 이름
    # Retrieval & Reranking
    "SearchResult",
    "QueryExpansionEngine",
    "GPT5QueryExpansionEngine",
    "ExpandedQuery",
    "QueryComplexity",
    "SearchIntent",
    "RetrievalOrchestrator",
    # Query Processing
    "LLMQueryRouter",
    "QueryProfile",
    "RoutingDecision",
    "ComplexityCalculator",
    "ComplexityResult",
    # Self-RAG
    "SelfRAGOrchestrator",
    "SelfRAGResult",
    # Generation
    "GenerationModule",
    "GenerationResult",
    "PromptManager",
    # Session Management
    "EnhancedSessionModule",
    # Query Routing
    "RuleBasedRouter",
    "RuleMatch",
]
