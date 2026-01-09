"""
Null Enricher

보강 기능이 비활성화되었을 때 사용하는 Null Object 패턴 구현체입니다.
아무 작업도 하지 않고 None을 반환하여 원본 문서를 그대로 사용합니다.

Null Object 패턴의 장점:
- 조건문(if enabled) 없이 항상 enricher.enrich() 호출 가능
- 코드 간결성 향상
- 에러 처리 불필요
"""

from typing import Any

from app.lib.logger import get_logger

from ..interfaces.enricher_interface import EnricherInterface
from ..schemas.enrichment_schema import EnrichmentResult

logger = get_logger(__name__)


class NullEnricher(EnricherInterface):
    """
    Null Object 패턴 구현 - 보강 기능 비활성화

    모든 메서드가 None을 반환하여 원본 문서를 그대로 사용합니다.

    사용 예시:
        >>> enricher = NullEnricher()
        >>> result = await enricher.enrich({"content": "..."})
        >>> print(result)  # None (보강 안 함)
    """

    def __init__(self):
        """NullEnricher 초기화"""
        logger.info("NullEnricher initialized (enrichment disabled)")

    async def enrich(self, document: dict[str, Any]) -> EnrichmentResult | None:
        """
        보강하지 않음 (항상 None 반환)

        Args:
            document: 문서 (무시됨)

        Returns:
            None: 보강하지 않음
        """
        logger.debug("Enrichment skipped (NullEnricher)")
        return None

    async def enrich_batch(self, documents: list[dict[str, Any]]) -> list[EnrichmentResult | None]:
        """
        배치 보강하지 않음 (항상 None 리스트 반환)

        Args:
            documents: 문서 리스트 (무시됨)

        Returns:
            list[None]: 모두 None
        """
        logger.debug(f"Batch enrichment skipped for {len(documents)} documents (NullEnricher)")
        return [None] * len(documents)

    async def validate_enrichment(self, enrichment: EnrichmentResult) -> bool:
        """
        검증하지 않음 (항상 True 반환)

        Args:
            enrichment: 보강 결과 (무시됨)

        Returns:
            True: 항상 통과
        """
        return True

    async def initialize(self) -> None:
        """초기화 불필요"""
        pass

    async def cleanup(self) -> None:
        """정리 불필요"""
        pass
