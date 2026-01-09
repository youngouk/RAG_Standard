"""
Cache Module - 검색 결과 캐싱 모듈

구현체:
- MemoryCacheManager: In-memory LRU 캐시 (완료)
- InMemorySemanticCache: 쿼리 임베딩 유사도 기반 시맨틱 캐시
- RedisCacheManager: Redis 분산 캐시 (향후 확장)

팩토리:
- CacheFactory: 설정 기반 캐시 자동 선택 팩토리
"""

from .factory import SUPPORTED_CACHES, CacheFactory
from .memory_cache import MemoryCacheManager
from .semantic_cache import InMemorySemanticCache, SemanticCacheConfig

__all__ = [
    # 팩토리
    "CacheFactory",
    "SUPPORTED_CACHES",
    # 구현체
    "MemoryCacheManager",
    "InMemorySemanticCache",
    "SemanticCacheConfig",
    # "RedisCacheManager",  # Phase 3 확장 대비
]
