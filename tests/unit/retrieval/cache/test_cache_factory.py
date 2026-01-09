"""
CacheFactory 단위 테스트
설정 기반 캐시 생성 검증

TDD 방식으로 작성됨:
- RED: 이 테스트가 먼저 실패해야 함
- GREEN: factory.py 구현 후 통과
- REFACTOR: 필요 시 리팩토링
"""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.core.retrieval.cache.factory import (
    SUPPORTED_CACHES,
    CacheFactory,
)


class TestSupportedCachesRegistry:
    """SUPPORTED_CACHES 레지스트리 테스트"""

    def test_supported_caches_registry_exists(self):
        """지원 캐시 레지스트리가 존재하는지 확인"""
        assert isinstance(SUPPORTED_CACHES, dict)
        assert len(SUPPORTED_CACHES) > 0

    def test_supported_caches_contains_expected_types(self):
        """레지스트리에 memory, redis, semantic이 포함되어 있는지 확인"""
        assert "memory" in SUPPORTED_CACHES
        assert "redis" in SUPPORTED_CACHES
        assert "semantic" in SUPPORTED_CACHES

    def test_each_cache_has_required_fields(self):
        """각 캐시 정보에 필수 필드가 포함되어 있는지 확인"""
        required_fields = {"type", "class", "description", "default_config"}

        for cache_name, cache_info in SUPPORTED_CACHES.items():
            for field in required_fields:
                assert field in cache_info, f"{cache_name}에 {field} 필드 없음"


class TestCacheFactoryStaticMethods:
    """CacheFactory 정적 메서드 테스트"""

    def test_get_supported_caches(self):
        """지원 캐시 목록 조회"""
        caches = CacheFactory.get_supported_caches()
        assert "memory" in caches
        assert "redis" in caches
        assert "semantic" in caches

    def test_list_caches_by_type_local(self):
        """타입별 캐시 목록 조회 - local"""
        local_caches = CacheFactory.list_caches_by_type("local")
        assert "memory" in local_caches

    def test_list_caches_by_type_distributed(self):
        """타입별 캐시 목록 조회 - distributed"""
        distributed_caches = CacheFactory.list_caches_by_type("distributed")
        assert "redis" in distributed_caches

    def test_list_caches_by_type_semantic(self):
        """타입별 캐시 목록 조회 - semantic"""
        semantic_caches = CacheFactory.list_caches_by_type("semantic")
        assert "semantic" in semantic_caches

    def test_get_cache_info_existing(self):
        """존재하는 캐시 정보 조회"""
        info = CacheFactory.get_cache_info("memory")
        assert info is not None
        assert info["class"] == "MemoryCacheManager"

    def test_get_cache_info_non_existing(self):
        """존재하지 않는 캐시 정보 조회 시 None 반환"""
        info = CacheFactory.get_cache_info("non-existing-cache")
        assert info is None


class TestCacheFactoryCreate:
    """CacheFactory.create() 메서드 테스트"""

    def test_create_memory_cache(self):
        """Memory 캐시 생성 테스트"""
        config = {
            "cache": {
                "provider": "memory",
                "memory": {
                    "maxsize": 500,
                    "ttl": 1800,
                },
            }
        }
        cache = CacheFactory.create(config)
        assert cache is not None
        assert cache.__class__.__name__ == "MemoryCacheManager"

    def test_create_memory_cache_with_defaults(self):
        """기본값으로 Memory 캐시 생성"""
        config = {
            "cache": {
                "provider": "memory",
            }
        }
        cache = CacheFactory.create(config)
        assert cache is not None
        assert cache.__class__.__name__ == "MemoryCacheManager"

    def test_create_semantic_cache(self):
        """Semantic 캐시 생성 테스트"""
        # Mock embedder 생성 - embed_query 메서드가 있어야 함
        mock_embedder = MagicMock()
        mock_embedder.return_value = [0.1] * 3072

        config = {
            "cache": {
                "provider": "semantic",
                "semantic": {
                    "similarity_threshold": 0.92,
                    "max_entries": 1000,
                    "ttl": 3600,
                },
            }
        }
        cache = CacheFactory.create(config, embedder=mock_embedder)
        assert cache is not None
        assert cache.__class__.__name__ == "InMemorySemanticCache"

    def test_create_with_invalid_provider_raises_error(self):
        """유효하지 않은 프로바이더로 생성 시 에러"""
        config = {
            "cache": {
                "provider": "invalid-provider",
            }
        }
        with pytest.raises(ValueError, match="지원하지 않는 캐시"):
            CacheFactory.create(config)

    def test_semantic_cache_requires_embedder(self):
        """Semantic 캐시는 embedder 필수"""
        config = {
            "cache": {
                "provider": "semantic",
            }
        }
        with pytest.raises(ValueError, match="embedder.*필수"):
            CacheFactory.create(config)

    def test_create_default_provider_is_memory(self):
        """provider 미지정 시 기본값은 memory"""
        config = {"cache": {}}
        cache = CacheFactory.create(config)
        assert cache.__class__.__name__ == "MemoryCacheManager"

    def test_create_with_empty_config_uses_memory(self):
        """빈 설정으로 생성 시 memory 캐시 사용"""
        config = {}
        cache = CacheFactory.create(config)
        assert cache.__class__.__name__ == "MemoryCacheManager"


class TestRedisCacheFallback:
    """Redis 캐시 폴백 테스트"""

    def test_redis_without_url_fallbacks_to_memory(self):
        """REDIS_URL 없으면 MemoryCacheManager로 폴백"""
        config = {
            "cache": {
                "provider": "redis",
                "redis": {
                    "ttl": 3600,
                    "prefix": "test:",
                },
            }
        }

        # REDIS_URL 환경변수가 없는 상태 확인
        with patch.dict("os.environ", {}, clear=True):
            cache = CacheFactory.create(config)
            assert cache.__class__.__name__ == "MemoryCacheManager"

    @patch.dict("os.environ", {"REDIS_URL": "redis://localhost:6379"})
    def test_redis_with_url_but_not_implemented_fallbacks_to_memory(self):
        """REDIS_URL 있어도 RedisCacheManager 미완성 시 MemoryCacheManager로 폴백"""
        config = {
            "cache": {
                "provider": "redis",
            }
        }
        # 현재는 RedisCacheManager를 직접 생성하지 않고 폴백
        cache = CacheFactory.create(config)
        assert cache.__class__.__name__ == "MemoryCacheManager"


class TestSemanticCacheConfig:
    """Semantic 캐시 설정 테스트"""

    def test_semantic_cache_uses_custom_threshold(self):
        """Semantic 캐시가 커스텀 similarity_threshold를 사용하는지 확인"""
        mock_embedder = MagicMock()
        mock_embedder.return_value = [0.1] * 768

        config = {
            "cache": {
                "provider": "semantic",
                "semantic": {
                    "similarity_threshold": 0.85,  # 커스텀 값
                    "max_entries": 500,
                    "ttl": 7200,
                },
            }
        }
        cache = CacheFactory.create(config, embedder=mock_embedder)

        # InMemorySemanticCache의 config에서 값 확인
        assert cache.config.similarity_threshold == 0.85
        assert cache.config.max_entries == 500
        assert cache.config.ttl_seconds == 7200

    def test_semantic_cache_uses_defaults_when_not_specified(self):
        """Semantic 캐시가 미지정 시 기본값 사용하는지 확인"""
        mock_embedder = MagicMock()
        mock_embedder.return_value = [0.1] * 768

        config = {
            "cache": {
                "provider": "semantic",
            }
        }
        cache = CacheFactory.create(config, embedder=mock_embedder)

        # 기본값 확인 (SUPPORTED_CACHES의 default_config)
        defaults = SUPPORTED_CACHES["semantic"]["default_config"]
        assert cache.config.similarity_threshold == defaults["similarity_threshold"]
        assert cache.config.max_entries == defaults["max_entries"]
        assert cache.config.ttl_seconds == defaults["ttl"]
