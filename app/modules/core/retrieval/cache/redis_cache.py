"""
Redis Cache Manager
Redis 기반 분산 캐시 매니저 (멀티 인스턴스 환경 지원)

주요 개선사항:
- 프로세스 간 캐시 공유 (멀티 워커 환경 지원)
- 자동 직렬화/역직렬화 (JSON 기반)
- Connection Pool로 성능 최적화
- Graceful Fallback (Redis 장애 시 로컬 캐시로 전환)
- 캐시 통계 추적
"""

import asyncio
import hashlib
import json
import time
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import ConnectionError, RedisError, TimeoutError

from .....lib.logger import get_logger
from ..interfaces import SearchResult

logger = get_logger(__name__)


class RedisCacheManager:
    """
    Redis 기반 분산 캐시 매니저

    특징:
    - 멀티 프로세스/인스턴스 간 캐시 공유
    - 자동 직렬화/역직렬화 (SearchResult → JSON)
    - Connection Pool로 성능 최적화
    - TTL 기반 자동 만료
    - Graceful Degradation (Redis 장애 시 로컬 캐시 폴백)
    - 캐시 히트/미스 통계

    멀티 인스턴스 환경에서의 동작:
    ```
    User Request → Load Balancer
      ├─ Worker 1 (Cache Miss) → Redis → DB Query → Redis Set
      ├─ Worker 2 (Cache Hit)  → Redis → ✅ Cached Data
      └─ Worker 3 (Cache Hit)  → Redis → ✅ Cached Data
    ```
    """

    def __init__(
        self,
        redis_client: Redis,
        key_prefix: str = "rag:cache:",
        default_ttl: int = 3600,
        enable_stats: bool = True,
        enable_fallback: bool = True,
        operation_timeout: float = 2.0,  # Redis 작업 타임아웃 (초)
    ):
        """
        Args:
            redis_client: Redis 비동기 클라이언트 인스턴스
            key_prefix: Redis 키 접두사 (네임스페이스 분리)
            default_ttl: 기본 TTL (초 단위)
            enable_stats: 통계 수집 활성화 여부
            enable_fallback: Redis 장애 시 로컬 캐시 폴백 활성화
            operation_timeout: Redis 작업당 최대 대기 시간
        """
        self.redis = redis_client
        self.key_prefix = key_prefix
        self.default_ttl = default_ttl
        self.enable_stats = enable_stats
        self.enable_fallback = enable_fallback
        self.operation_timeout = operation_timeout

        # 통계 (로컬 프로세스 단위)
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "invalidations": 0,
            "clears": 0,
            "errors": 0,
            "fallback_hits": 0,  # 폴백 캐시 히트 수
            "saved_time_ms": 0,
        }

        # Graceful Fallback: 로컬 인메모리 캐시 (Redis 장애 시 사용)
        self._fallback_cache: dict[str, tuple[list[SearchResult], float]] = {}
        self._fallback_active = False  # Redis 장애 감지 플래그

        logger.info(
            f"RedisCacheManager 초기화: prefix={key_prefix}, TTL={default_ttl}s, "
            f"fallback={enable_fallback}, timeout={operation_timeout}s"
        )

    async def get(self, key: str) -> list[SearchResult] | None:
        """
        캐시에서 검색 결과 조회 (Redis 우선, 실패 시 로컬 폴백)

        Args:
            key: 캐시 키 (쿼리 해시)

        Returns:
            캐시된 검색 결과 (없으면 None)
        """
        redis_key = self._build_redis_key(key)

        # [Step 1] Redis에서 조회 시도
        try:
            raw_data = await asyncio.wait_for(
                self.redis.get(redis_key), timeout=self.operation_timeout
            )

            if raw_data:
                # 직렬화된 데이터 역직렬화
                results = self._deserialize(raw_data)
                if self.enable_stats:
                    self.stats["hits"] += 1

                self._fallback_active = False  # Redis 정상 동작 확인
                logger.debug(
                    "Redis 캐시 히트",
                    extra={
                        "key_prefix": key[:16],
                        "result_count": len(results)
                    }
                )
                return results

        except (ConnectionError, TimeoutError, RedisError) as e:
            logger.warning(
                "Redis 캐시 조회 실패",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            self._fallback_active = True
            if self.enable_stats:
                self.stats["errors"] += 1

            # [Step 2] 로컬 폴백 캐시 시도
            if self.enable_fallback:
                fallback_result = self._get_from_fallback(key)
                if fallback_result:
                    if self.enable_stats:
                        self.stats["fallback_hits"] += 1
                    logger.debug(
                        "폴백 캐시 히트",
                        extra={"key_prefix": key[:16]}
                    )
                    return fallback_result

        # [Step 3] 캐시 미스
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
        검색 결과를 Redis 캐시에 저장 (직렬화 후 저장)

        Args:
            key: 캐시 키
            value: 저장할 검색 결과
            ttl: Time-To-Live (초 단위, None이면 default_ttl 사용)
        """
        redis_key = self._build_redis_key(key)
        effective_ttl = ttl if ttl is not None else self.default_ttl

        # [Step 1] Redis에 저장 시도
        try:
            # SearchResult 리스트 → JSON 직렬화
            serialized_data = self._serialize(value)

            await asyncio.wait_for(
                self.redis.setex(redis_key, effective_ttl, serialized_data),
                timeout=self.operation_timeout,
            )

            if self.enable_stats:
                self.stats["sets"] += 1

            self._fallback_active = False  # Redis 정상 동작 확인
            logger.debug(
                "Redis 캐시 저장",
                extra={
                    "key_prefix": key[:16],
                    "ttl_seconds": effective_ttl,
                    "result_count": len(value)
                }
            )

        except (ConnectionError, TimeoutError, RedisError) as e:
            logger.warning(
                "Redis 캐시 저장 실패",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            self._fallback_active = True
            if self.enable_stats:
                self.stats["errors"] += 1

            # [Step 2] 로컬 폴백 캐시에 저장
            if self.enable_fallback:
                self._set_to_fallback(key, value, effective_ttl)
                logger.debug(
                    "폴백 캐시 저장",
                    extra={"key_prefix": key[:16]}
                )

    async def invalidate(self, key: str) -> None:
        """
        특정 키의 캐시 무효화 (Redis + 로컬 폴백 모두 삭제)

        Args:
            key: 무효화할 캐시 키
        """
        redis_key = self._build_redis_key(key)

        try:
            await asyncio.wait_for(self.redis.delete(redis_key), timeout=self.operation_timeout)

            if self.enable_stats:
                self.stats["invalidations"] += 1

            logger.debug(
                "Redis 캐시 무효화",
                extra={"key_prefix": key[:16]}
            )

        except (ConnectionError, TimeoutError, RedisError) as e:
            logger.warning(
                "Redis 캐시 무효화 실패",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            if self.enable_stats:
                self.stats["errors"] += 1

        # 로컬 폴백 캐시에서도 삭제
        if key in self._fallback_cache:
            del self._fallback_cache[key]

    async def clear(self) -> None:
        """
        모든 캐시 클리어 (Redis 네임스페이스 전체 + 로컬 폴백)

        주의: 같은 key_prefix를 사용하는 모든 캐시가 삭제됨
        """
        try:
            # Redis SCAN으로 key_prefix로 시작하는 모든 키 찾기
            keys_to_delete = []
            async for key in self.redis.scan_iter(match=f"{self.key_prefix}*"):
                keys_to_delete.append(key)

            if keys_to_delete:
                await asyncio.wait_for(
                    self.redis.delete(*keys_to_delete),
                    timeout=self.operation_timeout * 2,  # 대량 삭제는 타임아웃 2배
                )

            if self.enable_stats:
                self.stats["clears"] += 1

            logger.info(
                "Redis 캐시 클리어 완료",
                extra={"deleted_keys": len(keys_to_delete)}
            )

        except (ConnectionError, TimeoutError, RedisError) as e:
            logger.warning(
                "Redis 캐시 클리어 실패",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            if self.enable_stats:
                self.stats["errors"] += 1

        # 로컬 폴백 캐시도 클리어
        self._fallback_cache.clear()
        logger.debug("폴백 캐시 클리어 완료")

    def get_stats(self) -> dict[str, Any]:
        """
        캐시 통계 반환 (로컬 프로세스 단위 통계)

        Returns:
            히트율, 미스율, 에러율, 폴백 사용률 등
        """
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = self.stats["hits"] / total_requests if total_requests > 0 else 0.0
        miss_rate = self.stats["misses"] / total_requests if total_requests > 0 else 0.0
        error_rate = (
            self.stats["errors"] / (total_requests + self.stats["errors"])
            if total_requests > 0
            else 0.0
        )
        fallback_rate = self.stats["fallback_hits"] / total_requests if total_requests > 0 else 0.0

        return {
            "total_requests": total_requests,
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "hit_rate": round(hit_rate, 4),
            "miss_rate": round(miss_rate, 4),
            "sets": self.stats["sets"],
            "invalidations": self.stats["invalidations"],
            "clears": self.stats["clears"],
            "errors": self.stats["errors"],
            "error_rate": round(error_rate, 4),
            "fallback_hits": self.stats["fallback_hits"],
            "fallback_rate": round(fallback_rate, 4),
            "fallback_active": self._fallback_active,
            "fallback_cache_size": len(self._fallback_cache),
            "saved_time_ms": self.stats["saved_time_ms"],
        }

    # ========================================
    # 내부 헬퍼 메서드
    # ========================================

    def _build_redis_key(self, key: str) -> str:
        """Redis 키 생성 (네임스페이스 접두사 추가)"""
        return f"{self.key_prefix}{key}"

    def _serialize(self, results: list[SearchResult]) -> str:
        """SearchResult 리스트를 JSON 문자열로 직렬화"""
        data = [
            {
                "id": r.id,
                "content": r.content,
                "score": r.score,
                "metadata": r.metadata,
            }
            for r in results
        ]
        return json.dumps(data, ensure_ascii=False)

    def _deserialize(self, raw_data: bytes) -> list[SearchResult]:
        """JSON 문자열을 SearchResult 리스트로 역직렬화"""
        data = json.loads(raw_data.decode("utf-8"))
        return [
            SearchResult(
                id=item["id"],
                content=item["content"],
                score=item["score"],
                metadata=item["metadata"],
            )
            for item in data
        ]

    def _get_from_fallback(self, key: str) -> list[SearchResult] | None:
        """로컬 폴백 캐시에서 조회 (TTL 체크 포함)"""
        if key not in self._fallback_cache:
            return None

        results, expiry_time = self._fallback_cache[key]

        # TTL 만료 확인
        if time.time() > expiry_time:
            del self._fallback_cache[key]
            logger.debug(f"폴백 캐시 만료: {key[:16]}...")
            return None

        return results

    def _set_to_fallback(self, key: str, value: list[SearchResult], ttl: int) -> None:
        """로컬 폴백 캐시에 저장 (TTL 추적)"""
        expiry_time = time.time() + ttl
        self._fallback_cache[key] = (value, expiry_time)

    # ========================================
    # 유틸리티 메서드 (MemoryCacheManager 호환성)
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
        key_components = [query, str(top_k)]
        if filters:
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

    async def health_check(self) -> bool:
        """
        Redis 연결 상태 확인

        Returns:
            정상 연결 여부 (True/False)
        """
        try:
            await asyncio.wait_for(self.redis.ping(), timeout=1.0)
            return True
        except Exception as e:
            logger.error(
                "Redis Health Check 실패",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            return False

    async def close(self) -> None:
        """
        Redis 연결 종료 (정리 작업)
        """
        try:
            await self.redis.close()
            logger.info("Redis 연결 종료 완료")
        except Exception as e:
            logger.warning(
                "Redis 연결 종료 실패",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
