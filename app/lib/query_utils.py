"""
Query Utilities
쿼리 정규화, 캐싱, 전처리 유틸리티
"""

import re
from hashlib import md5
from threading import Lock
from typing import Any

from cachetools import TTLCache

from .logger import get_logger

logger = get_logger(__name__)


class QueryNormalizer:
    """
    쿼리 정규화 유틸리티
    - 공백 제거, 소문자 변환, 조사 제거로 캐시 적중률 향상
    """

    # 한국어 조사 패턴
    JOSA_PATTERN = re.compile(r"[을를이가은는에서와과도만의로으로부터까지](?=\s|$)")

    # 공백 정규화 패턴
    WHITESPACE_PATTERN = re.compile(r"\s+")

    @staticmethod
    def normalize(query: str) -> str:
        """
        쿼리 정규화

        Args:
            query: 원본 쿼리

        Returns:
            정규화된 쿼리 문자열
        """
        if not query:
            return ""

        # 1. 소문자 변환
        normalized = query.lower().strip()

        # 2. 공백 제거
        normalized = QueryNormalizer.WHITESPACE_PATTERN.sub("", normalized)

        # 3. 조사 제거
        normalized = QueryNormalizer.JOSA_PATTERN.sub("", normalized)

        return normalized

    @staticmethod
    def get_cache_key(query: str) -> str:
        """
        캐시 키 생성 (MD5 해시)

        Args:
            query: 쿼리 문자열

        Returns:
            MD5 해시 문자열
        """
        normalized = QueryNormalizer.normalize(query)
        return md5(normalized.encode("utf-8")).hexdigest()


class QueryCache:
    """
    Thread-safe 쿼리 결과 캐시 (TTL + LRU)
    """

    def __init__(self, maxsize: int = 1000, ttl: int = 300):
        """
        Args:
            maxsize: 최대 캐시 항목 수
            ttl: TTL (초) - 기본 5분
        """
        self.cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)
        self._lock = Lock()
        self.normalizer = QueryNormalizer()

        # 통계
        self.stats = {
            "hits": 0,
            "misses": 0,
            "total_requests": 0,
        }

        logger.info(f"QueryCache 초기화: maxsize={maxsize}, ttl={ttl}초")

    def get(self, query: str) -> Any | None:
        """
        캐시에서 결과 조회

        Args:
            query: 쿼리 문자열

        Returns:
            캐시된 결과 또는 None
        """
        with self._lock:
            self.stats["total_requests"] += 1

            cache_key = self.normalizer.get_cache_key(query)
            result = self.cache.get(cache_key)

            if result is not None:
                self.stats["hits"] += 1
                logger.debug(f"캐시 HIT: {query[:30]}")
            else:
                self.stats["misses"] += 1
                logger.debug(f"캐시 MISS: {query[:30]}")

            return result

    def set(self, query: str, value: Any) -> None:
        """
        캐시에 결과 저장

        Args:
            query: 쿼리 문자열
            value: 저장할 값
        """
        with self._lock:
            cache_key = self.normalizer.get_cache_key(query)
            self.cache[cache_key] = value
            logger.debug(f"캐시 저장: {query[:30]}")

    def clear(self) -> None:
        """캐시 전체 삭제"""
        with self._lock:
            self.cache.clear()
            logger.info("캐시 초기화 완료")

    def get_stats(self) -> dict:
        """캐시 통계 반환"""
        with self._lock:
            total = self.stats["total_requests"]
            hit_rate = (self.stats["hits"] / total * 100) if total > 0 else 0

            return {
                **self.stats,
                "hit_rate": round(hit_rate, 2),
                "size": len(self.cache),
                "maxsize": self.cache.maxsize,
            }
