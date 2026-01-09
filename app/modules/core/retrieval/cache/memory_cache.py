"""
Memory Cache Manager
In-memory LRU 캐시 기반 검색 결과 캐싱

기존 retrieval_rerank.py의 LRUCache 로직을 분리한 모듈입니다.
"""

import hashlib
import time
from typing import Any

from cachetools import LRUCache

from .....lib.logger import get_logger
from ..interfaces import SearchResult

logger = get_logger(__name__)


class MemoryCacheManager:
    """
    In-memory LRU 캐시 매니저

    특징:
    - LRUCache를 사용한 메모리 기반 캐싱
    - 캐시 히트/미스 통계 추적
    - TTL 지원 (선택적)
    - 쿼리 해시 기반 키 생성
    """

    def __init__(
        self,
        maxsize: int = 1000,
        default_ttl: int | None = 3600,
        enable_stats: bool = True,
    ):
        """
        Args:
            maxsize: 캐시 최대 항목 수 (LRU 정책으로 오래된 항목 자동 제거)
            default_ttl: 기본 TTL (초 단위, None이면 무제한)
            enable_stats: 통계 수집 활성화 여부
        """
        self.cache: LRUCache[str, list[SearchResult]] = LRUCache(maxsize=maxsize)
        self.default_ttl = default_ttl
        self.enable_stats = enable_stats

        # TTL 추적용 딕셔너리 (키 -> 만료 시간)
        self._expiry_times: dict[str, float] = {}

        # 통계
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "invalidations": 0,
            "clears": 0,
            "saved_time_ms": 0,  # 캐시로 절약한 시간 (밀리초)
        }

        logger.info(f"MemoryCacheManager 초기화: maxsize={maxsize}, TTL={default_ttl}s")

    async def get(self, key: str) -> list[SearchResult] | None:
        """
        캐시에서 검색 결과 조회

        Args:
            key: 캐시 키 (일반적으로 쿼리 해시)

        Returns:
            캐시된 결과 (없거나 만료되면 None)
        """
        # TTL 체크
        if self._is_expired(key):
            await self.invalidate(key)
            if self.enable_stats:
                self.stats["misses"] += 1
            return None

        # 캐시 조회
        result = self.cache.get(key)
        if result is not None:
            if self.enable_stats:
                self.stats["hits"] += 1
            logger.debug(f"캐시 히트: {key[:16]}...")
            return result
        else:
            if self.enable_stats:
                self.stats["misses"] += 1
            return None

    async def set(
        self,
        key: str,
        value: list[SearchResult],
        ttl: int | None = None,
    ) -> None:
        """
        검색 결과를 캐시에 저장

        Args:
            key: 캐시 키
            value: 저장할 검색 결과
            ttl: Time-To-Live (초 단위, None이면 default_ttl 사용)
        """
        self.cache[key] = value

        # TTL 설정
        effective_ttl = ttl if ttl is not None else self.default_ttl
        if effective_ttl is not None:
            self._expiry_times[key] = time.time() + effective_ttl

        if self.enable_stats:
            self.stats["sets"] += 1

        logger.debug(f"캐시 저장: {key[:16]}... (TTL={effective_ttl}s, 결과 수={len(value)})")

    async def invalidate(self, key: str) -> None:
        """
        특정 키의 캐시 무효화

        Args:
            key: 무효화할 캐시 키
        """
        if key in self.cache:
            del self.cache[key]

        if key in self._expiry_times:
            del self._expiry_times[key]

        if self.enable_stats:
            self.stats["invalidations"] += 1

        logger.debug(f"캐시 무효화: {key[:16]}...")

    async def clear(self) -> None:
        """
        모든 캐시 클리어
        """
        self.cache.clear()
        self._expiry_times.clear()

        if self.enable_stats:
            self.stats["clears"] += 1

        logger.info("전체 캐시 클리어 완료")

    def get_stats(self) -> dict[str, Any]:
        """
        캐시 통계 반환

        Returns:
            히트율, 미스율, 저장 횟수 등
        """
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = self.stats["hits"] / total_requests if total_requests > 0 else 0.0
        miss_rate = self.stats["misses"] / total_requests if total_requests > 0 else 0.0

        return {
            "total_requests": total_requests,
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "hit_rate": round(hit_rate, 4),
            "miss_rate": round(miss_rate, 4),
            "sets": self.stats["sets"],
            "invalidations": self.stats["invalidations"],
            "clears": self.stats["clears"],
            "current_size": len(self.cache),
            "max_size": self.cache.maxsize,
            "saved_time_ms": self.stats["saved_time_ms"],
        }

    def _is_expired(self, key: str) -> bool:
        """
        키의 TTL 만료 여부 확인

        Args:
            key: 확인할 캐시 키

        Returns:
            만료 여부 (True/False)
        """
        if key not in self._expiry_times:
            return False

        expiry_time = self._expiry_times[key]
        if time.time() > expiry_time:
            logger.debug(f"캐시 만료: {key[:16]}...")
            return True

        return False

    # ========================================
    # 유틸리티 메서드 (기존 코드 호환성)
    # ========================================

    @staticmethod
    def generate_cache_key(query: str, top_k: int, filters: dict | None = None) -> str:
        """
        캐시 키 생성 (쿼리 해시)

        Args:
            query: 검색 쿼리
            top_k: 반환할 결과 수
            filters: 추가 필터 (메타데이터 등)

        Returns:
            SHA256 해시 캐시 키
        """
        # 쿼리 + top_k + filters를 결합하여 유니크 키 생성
        key_components = [query, str(top_k)]
        if filters:
            # 딕셔너리를 정렬된 문자열로 변환
            filters_str = str(sorted(filters.items()))
            key_components.append(filters_str)

        combined = "|".join(key_components)
        return hashlib.sha256(combined.encode()).hexdigest()

    def record_saved_time(self, duration_ms: float) -> None:
        """
        캐시로 절약한 시간 기록

        Args:
            duration_ms: 절약한 시간 (밀리초)
        """
        if self.enable_stats:
            self.stats["saved_time_ms"] += int(duration_ms)
