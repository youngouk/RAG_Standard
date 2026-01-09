"""
GeoJS 기반 IP 지역 분석 모듈
완전 무료, 무제한 API 사용
"""

import asyncio
import hashlib
import ipaddress
from datetime import datetime, timedelta
from typing import Any, cast

import httpx

from .logger import get_logger

logger = get_logger(__name__)


class IPGeolocationModule:
    """GeoJS API를 사용한 IP 지역 분석"""

    def __init__(self, config: dict):
        self.config = config
        self.api_url = "https://get.geojs.io/v1/ip/geo/{ip}.json"
        self.timeout = 3  # 3초 타임아웃

        # 인메모리 캐시 (24시간 TTL)
        self.cache: dict[str, dict] = {}
        self.cache_ttl = config.get("ip_geolocation", {}).get("cache_ttl", 86400)  # 기본 24시간

        # 통계
        self.stats = {"total_requests": 0, "cache_hits": 0, "api_calls": 0, "errors": 0}

    async def initialize(self) -> None:
        """모듈 초기화"""
        logger.info("✅ IP Geolocation module initialized (GeoJS)")

    def hash_ip(self, ip: str) -> str:
        """
        IP 주소를 SHA256 해시로 변환

        Args:
            ip: IP 주소 문자열

        Returns:
            SHA256 해시 문자열 (64자)
        """
        return hashlib.sha256(ip.encode("utf-8")).hexdigest()

    def _is_private_ip(self, ip: str) -> bool:
        """
        사설 IP 및 내부 네트워크 IP 확인 (Railway 내부 IP 포함)

        Args:
            ip: IP 주소 문자열

        Returns:
            True if private IP or internal network IP
        """
        try:
            # Railway 내부 IP 대역 (100.64.0.0/10) 명시적 체크
            if ip.startswith("100.64."):
                logger.debug(f"Detected Railway internal IP: {ip}")
                return True

            # 일반 사설 IP 체크
            ip_obj = ipaddress.ip_address(ip)
            return ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local
        except ValueError:
            # IP 주소 파싱 실패 시 False 반환
            return False

    async def get_location(self, ip: str) -> dict:
        """
        IP 주소의 지역 정보 조회

        Args:
            ip: IP 주소 문자열

        Returns:
            {
                "ip": "8.8.8.8",
                "ip_hash": "sha256_hash",
                "country": "United States",
                "country_code": "US",
                "city": "Mountain View",
                "region": "California",
                "latitude": 37.3860,
                "longitude": -122.0838,
                "timezone": "America/Los_Angeles",
                "is_private": False,
                "cached": False
            }
        """
        self.stats["total_requests"] += 1

        # IP 유효성 검사
        if not ip:
            return self._get_fallback_result("unknown")

        # 사설 IP 체크
        if self._is_private_ip(ip):
            return {
                "ip": ip,
                "ip_hash": self.hash_ip(ip),
                "country": "Local Network",
                "country_code": "XX",
                "city": None,
                "region": None,
                "latitude": None,
                "longitude": None,
                "timezone": None,
                "is_private": True,
                "cached": False,
            }

        # 캐시 확인
        cache_key = self.hash_ip(ip)
        cached = self.cache.get(cache_key)

        if cached:
            # 캐시 만료 확인
            if datetime.now() < cached["expires_at"]:
                self.stats["cache_hits"] += 1
                result = cached["data"].copy()
                result["cached"] = True
                logger.debug(f"📦 Cache hit for IP hash: {cache_key[:8]}...")
                return cast(dict[Any, Any], result)
            else:
                # 만료된 캐시 삭제
                del self.cache[cache_key]

        # GeoJS API 호출
        try:
            self.stats["api_calls"] += 1
            url = self.api_url.format(ip=ip)

            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()

            # 안전한 float 변환 함수 (nil 문자열 처리)
            def safe_float(value: Any) -> float | None:
                """'nil' 문자열이나 None을 안전하게 처리"""
                if value in ["nil", None, ""]:
                    return None
                try:
                    return float(value)
                except (ValueError, TypeError):
                    logger.debug(f"Cannot convert to float: {value}")
                    return None

            # 결과 포맷팅
            result = {
                "ip": ip,
                "ip_hash": self.hash_ip(ip),
                "country": data.get("country"),
                "country_code": data.get("country_code"),
                "city": data.get("city"),
                "region": data.get("region"),
                "latitude": safe_float(data.get("latitude")),
                "longitude": safe_float(data.get("longitude")),
                "timezone": data.get("timezone"),
                "is_private": False,
                "cached": False,
            }

            # 캐시 저장
            self.cache[cache_key] = {
                "data": result.copy(),
                "expires_at": datetime.now() + timedelta(seconds=self.cache_ttl),
            }

            logger.info(
                f"📍 IP location resolved: {result['country']} ({result['country_code']}) - {result['city']}"
            )
            return result

        except httpx.TimeoutException:
            self.stats["errors"] += 1
            logger.warning(f"⏱️ GeoJS API timeout for IP: {ip}")
            return self._get_fallback_result(ip)

        except httpx.HTTPStatusError as e:
            self.stats["errors"] += 1
            logger.error(f"❌ GeoJS API HTTP error: {e.response.status_code}")
            return self._get_fallback_result(ip)

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"❌ GeoJS API error: {e}")
            return self._get_fallback_result(ip)

    def _get_fallback_result(self, ip: str) -> dict:
        """API 실패 시 폴백 결과"""
        return {
            "ip": ip,
            "ip_hash": self.hash_ip(ip),
            "country": "Unknown",
            "country_code": "XX",
            "city": None,
            "region": None,
            "latitude": None,
            "longitude": None,
            "timezone": None,
            "is_private": False,
            "cached": False,
        }

    async def get_location_batch(self, ips: list[str]) -> dict[str, dict]:
        """
        여러 IP 일괄 조회 (병렬 처리)

        Args:
            ips: IP 주소 리스트

        Returns:
            {ip_hash: location_data}
        """
        tasks = [self.get_location(ip) for ip in ips]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {result["ip_hash"]: result for result in results if isinstance(result, dict)}

    def get_stats(self) -> dict:
        """통계 조회"""
        cache_hit_rate = (
            self.stats["cache_hits"] / self.stats["total_requests"] * 100
            if self.stats["total_requests"] > 0
            else 0
        )

        return {
            **self.stats,
            "cache_hit_rate": round(cache_hit_rate, 2),
            "cache_size": len(self.cache),
        }

    async def destroy(self) -> None:
        """모듈 정리"""
        self.cache.clear()
        logger.info("IP Geolocation module destroyed")
