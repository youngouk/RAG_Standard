"""PII 감사 로그 보호 테스트"""
import hashlib

import pytest

from app.modules.core.privacy.review.audit import PIIAuditLogger
from app.modules.core.privacy.review.models import (
    DetectionMethod,
    PIIEntity,
    PIIType,
    PolicyAction,
    PolicyDecision,
)


class TestAuditPIIProtection:
    """감사 로그 PII 보호 테스트"""

    @pytest.mark.asyncio
    async def test_audit_log_hashes_original_values(self):
        """원본 값은 해시 처리되어야 함"""
        # Given: PII 엔티티
        entities = [
            PIIEntity(
                entity_type=PIIType.PHONE,
                value="010-1234-5678",
                start_pos=10,
                end_pos=23,
                confidence=0.95,
                detection_method=DetectionMethod.REGEX,
            ),
        ]

        decision = PolicyDecision(
            action=PolicyAction.MASK_AND_PROCEED,
            reason="전화번호 마스킹 정책",
            entities_to_mask=tuple(entities),
            requires_human_review=False,
        )

        # Mock collection
        collection = MockCollection()
        logger = PIIAuditLogger(collection=collection)

        # When: 감사 로그 기록
        await logger.log_detection(
            document_id="doc-123",
            entities=entities,
            decision=decision,
        )

        # Then: MongoDB에 저장된 값 검증
        saved_doc = collection.inserted_docs[0]

        # 원본 값이 그대로 저장되면 안 됨
        assert "010-1234-5678" not in str(saved_doc)

        # 해시값이 저장되어야 함
        expected_hash = hashlib.sha256(b"010-1234-5678").hexdigest()

        # entities 필드에서 해시 확인
        saved_entities = saved_doc["entities"]
        assert len(saved_entities) == 1
        assert saved_entities[0]["value_hash"] == expected_hash
        assert "value" not in saved_entities[0]  # 원본 값 필드 없음

    @pytest.mark.asyncio
    async def test_audit_log_metadata_no_pii(self):
        """메타데이터에도 PII 없어야 함"""
        entities = [
            PIIEntity(
                entity_type=PIIType.PHONE,
                value="010-9999-8888",
                start_pos=0,
                end_pos=13,
                confidence=1.0,
                detection_method=DetectionMethod.REGEX,
            ),
        ]

        decision = PolicyDecision(
            action=PolicyAction.MASK_AND_PROCEED,
            reason="테스트",
            entities_to_mask=tuple(entities),
            requires_human_review=False,
        )

        collection = MockCollection()
        logger = PIIAuditLogger(collection=collection)

        await logger.log_detection(
            document_id="doc-456",
            entities=entities,
            decision=decision,
            metadata={"context": "연락처: 010-9999-8888"},  # PII 포함
        )

        saved_doc = collection.inserted_docs[0]

        # metadata에도 원본 PII 없어야 함
        assert "010-9999-8888" not in str(saved_doc["metadata"])


class MockCollection:
    """테스트용 Mock MongoDB Collection"""

    def __init__(self):
        self.inserted_docs = []

    async def insert_one(self, doc):
        self.inserted_docs.append(doc)
