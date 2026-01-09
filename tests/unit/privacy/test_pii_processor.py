"""
PII Review Processor 단위 테스트

PIIReviewProcessor의 통합 처리 로직 검증.

테스트 케이스:
1. 문서 처리 플로우
2. 마스킹 처리
3. Graceful Degradation
4. 비활성화 상태

구현일: 2025-12-01
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.core.privacy.review import (
    DetectionMethod,
    Document,
    HybridPIIDetector,
    PIIAuditLogger,
    PIIEntity,
    PIIPolicyEngine,
    PIIReviewProcessor,
    PIIType,
    PolicyAction,
    PolicyDecision,
)


class TestPIIReviewProcessor:
    """PIIReviewProcessor 테스트 클래스"""

    @pytest.fixture
    def mock_detector(self) -> MagicMock:
        """Mock PII Detector"""
        detector = MagicMock(spec=HybridPIIDetector)
        detector.detect.return_value = []
        return detector

    @pytest.fixture
    def mock_policy_engine(self) -> MagicMock:
        """Mock Policy Engine"""
        engine = MagicMock(spec=PIIPolicyEngine)
        engine.evaluate.return_value = PolicyDecision(
            action=PolicyAction.REVIEW_ONLY,
            entities_to_mask=(),
            reason="No PII detected",
            requires_human_review=False,
        )
        return engine

    @pytest.fixture
    def mock_audit_logger(self) -> MagicMock:
        """Mock Audit Logger"""
        logger = MagicMock(spec=PIIAuditLogger)
        logger.log_detection = AsyncMock(return_value="audit-123")
        return logger

    @pytest.fixture
    def processor(
        self,
        mock_detector: MagicMock,
        mock_policy_engine: MagicMock,
        mock_audit_logger: MagicMock,
    ) -> PIIReviewProcessor:
        """테스트용 프로세서"""
        return PIIReviewProcessor(
            detector=mock_detector,
            policy_engine=mock_policy_engine,
            audit_logger=mock_audit_logger,
            enabled=True,
        )

    @pytest.fixture
    def sample_document(self) -> Document:
        """테스트용 문서"""
        return Document(
            id="doc-123",
            content="연락처: 010-1234-5678",
            metadata={"source": "test"},
        )

    def _create_phone_entity(self, value: str = "010-1234-5678") -> PIIEntity:
        """전화번호 엔티티 생성 헬퍼"""
        return PIIEntity(
            entity_type=PIIType.PHONE,
            value=value,
            start_pos=5,  # "연락처: " 다음
            end_pos=5 + len(value),
            confidence=0.95,
            detection_method=DetectionMethod.REGEX,
            context="연락처: 010-1234-5678",
        )

    # ========================================
    # 기본 처리 플로우 테스트
    # ========================================

    @pytest.mark.asyncio
    async def test_process_document_no_pii(
        self,
        processor: PIIReviewProcessor,
        sample_document: Document,
        mock_detector: MagicMock,
    ) -> None:
        """PII가 없는 문서 처리"""
        mock_detector.detect.return_value = []

        result = await processor.process(sample_document)

        assert result.document_id == "doc-123"
        assert result.entities_detected == 0
        assert result.entities_masked == 0
        assert result.action_taken == PolicyAction.REVIEW_ONLY
        assert result.processed_content == sample_document.content

    @pytest.mark.asyncio
    async def test_process_document_with_pii_mask(
        self,
        processor: PIIReviewProcessor,
        sample_document: Document,
        mock_detector: MagicMock,
        mock_policy_engine: MagicMock,
    ) -> None:
        """PII 마스킹 처리"""
        phone_entity = self._create_phone_entity()
        mock_detector.detect.return_value = [phone_entity]

        mock_policy_engine.evaluate.return_value = PolicyDecision(
            action=PolicyAction.MASK_AND_PROCEED,
            entities_to_mask=(phone_entity,),
            reason="Phone number masked",
            requires_human_review=False,
        )

        result = await processor.process(sample_document)

        assert result.entities_detected == 1
        assert result.entities_masked == 1
        assert result.action_taken == PolicyAction.MASK_AND_PROCEED
        assert "[전화번호]" in result.processed_content

    @pytest.mark.asyncio
    async def test_process_document_block(
        self,
        processor: PIIReviewProcessor,
        mock_detector: MagicMock,
        mock_policy_engine: MagicMock,
    ) -> None:
        """PII 차단 처리"""
        document = Document(
            id="doc-456",
            content="주민번호: 900101-1234567",
            metadata={},
        )

        ssn_entity = PIIEntity(
            entity_type=PIIType.SSN,
            value="900101-1234567",
            start_pos=5,
            end_pos=19,
            confidence=0.99,
            detection_method=DetectionMethod.REGEX,
            context="주민번호: 900101-1234567",
        )

        mock_detector.detect.return_value = [ssn_entity]
        mock_policy_engine.evaluate.return_value = PolicyDecision(
            action=PolicyAction.BLOCK_ON_VIOLATION,
            entities_to_mask=(),
            reason="SSN detected - blocking",
            requires_human_review=True,
        )

        result = await processor.process(document)

        assert result.action_taken == PolicyAction.BLOCK_ON_VIOLATION
        assert result.processed_content is None  # 차단 시 콘텐츠 없음
        assert result.is_blocked is True

    # ========================================
    # 마스킹 로직 테스트
    # ========================================

    @pytest.mark.asyncio
    async def test_mask_multiple_entities(
        self,
        processor: PIIReviewProcessor,
        mock_detector: MagicMock,
        mock_policy_engine: MagicMock,
    ) -> None:
        """여러 엔티티 마스킹"""
        document = Document(
            id="doc-789",
            content="전화: 010-1111-2222, 이메일: test@example.com",
            metadata={},
        )

        phone_entity = PIIEntity(
            entity_type=PIIType.PHONE,
            value="010-1111-2222",
            start_pos=4,
            end_pos=17,
            confidence=0.95,
            detection_method=DetectionMethod.REGEX,
            context="",
        )

        email_entity = PIIEntity(
            entity_type=PIIType.EMAIL,
            value="test@example.com",
            start_pos=24,
            end_pos=40,
            confidence=0.95,
            detection_method=DetectionMethod.REGEX,
            context="",
        )

        mock_detector.detect.return_value = [phone_entity, email_entity]
        mock_policy_engine.evaluate.return_value = PolicyDecision(
            action=PolicyAction.MASK_AND_PROCEED,
            entities_to_mask=(phone_entity, email_entity),
            reason="Multiple PII masked",
            requires_human_review=False,
        )

        result = await processor.process(document)

        assert result.entities_detected == 2
        assert result.entities_masked == 2
        assert "[전화번호]" in result.processed_content
        assert "[이메일]" in result.processed_content

    # ========================================
    # 비활성화 상태 테스트
    # ========================================

    @pytest.mark.asyncio
    async def test_disabled_processor(
        self,
        mock_detector: MagicMock,
        mock_policy_engine: MagicMock,
        mock_audit_logger: MagicMock,
    ) -> None:
        """비활성화된 프로세서는 원본 그대로 반환"""
        processor = PIIReviewProcessor(
            detector=mock_detector,
            policy_engine=mock_policy_engine,
            audit_logger=mock_audit_logger,
            enabled=False,  # 비활성화
        )

        document = Document(
            id="doc-disabled",
            content="민감한 정보: 010-1234-5678",
            metadata={},
        )

        result = await processor.process(document)

        # 비활성화 시 탐지/정책 평가 호출 안 함
        mock_detector.detect.assert_not_called()
        mock_policy_engine.evaluate.assert_not_called()

        # 원본 그대로 반환
        assert result.processed_content == document.content
        assert result.entities_detected == 0

    # ========================================
    # Graceful Degradation 테스트
    # ========================================

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_detector_error(
        self,
        processor: PIIReviewProcessor,
        sample_document: Document,
        mock_detector: MagicMock,
    ) -> None:
        """탐지기 오류 시 원본 반환 (Graceful Degradation)"""
        mock_detector.detect.side_effect = RuntimeError("Detector failed")

        result = await processor.process(sample_document)

        # 오류 발생해도 원본 콘텐츠 반환
        assert result.processed_content == sample_document.content
        assert result.entities_detected == 0
        assert result.action_taken == PolicyAction.REVIEW_ONLY

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_policy_error(
        self,
        processor: PIIReviewProcessor,
        sample_document: Document,
        mock_detector: MagicMock,
        mock_policy_engine: MagicMock,
    ) -> None:
        """정책 엔진 오류 시 원본 반환"""
        mock_detector.detect.return_value = [self._create_phone_entity()]
        mock_policy_engine.evaluate.side_effect = ValueError("Policy error")

        result = await processor.process(sample_document)

        assert result.processed_content == sample_document.content
        assert result.action_taken == PolicyAction.REVIEW_ONLY

    # ========================================
    # 감사 로그 테스트
    # ========================================

    @pytest.mark.asyncio
    async def test_audit_log_called(
        self,
        processor: PIIReviewProcessor,
        sample_document: Document,
        mock_detector: MagicMock,
        mock_audit_logger: MagicMock,
    ) -> None:
        """처리 후 감사 로그 기록"""
        mock_detector.detect.return_value = []

        result = await processor.process(sample_document)

        # 감사 로그 호출 확인
        mock_audit_logger.log_detection.assert_called_once()
        assert result.audit_id == "audit-123"

    # ========================================
    # process_text 편의 메서드 테스트
    # ========================================

    @pytest.mark.asyncio
    async def test_process_text_convenience(
        self,
        processor: PIIReviewProcessor,
        mock_detector: MagicMock,
    ) -> None:
        """텍스트 직접 처리"""
        mock_detector.detect.return_value = []

        result = await processor.process_text(
            text="테스트 텍스트",
            document_id="custom-id",
            source_file="test.txt",
        )

        assert result.document_id == "custom-id"
        assert result.processed_content == "테스트 텍스트"

    # ========================================
    # 처리 시간 측정 테스트
    # ========================================

    @pytest.mark.asyncio
    async def test_processing_time_recorded(
        self,
        processor: PIIReviewProcessor,
        sample_document: Document,
        mock_detector: MagicMock,
    ) -> None:
        """처리 시간이 기록됨"""
        mock_detector.detect.return_value = []

        result = await processor.process(sample_document)

        assert result.processing_time_ms >= 0


class TestDocument:
    """Document 데이터 클래스 테스트"""

    def test_from_dict(self) -> None:
        """딕셔너리에서 Document 생성"""
        data: dict[str, Any] = {
            "id": "test-id",
            "content": "테스트 콘텐츠",
            "metadata": {"key": "value"},
        }

        doc = Document.from_dict(data)

        assert doc.id == "test-id"
        assert doc.content == "테스트 콘텐츠"
        assert doc.metadata == {"key": "value"}

    def test_from_dict_missing_fields(self) -> None:
        """필드가 없는 딕셔너리 처리"""
        data: dict[str, Any] = {}

        doc = Document.from_dict(data)

        assert doc.id == ""
        assert doc.content == ""
        assert doc.metadata == {}
