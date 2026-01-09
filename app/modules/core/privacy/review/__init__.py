"""
PII Review System - 개인정보 검토 시스템

문서 전처리 파이프라인에서 PII(개인식별정보)를 탐지하고 처리하는 시스템.

주요 컴포넌트:
- HybridPIIDetector: Regex + spaCy NER 하이브리드 탐지기
- PIIPolicyEngine: 정책 기반 처리 결정 엔진
- PIIAuditLogger: MongoDB 감사 로그 기록
- PIIReviewProcessor: 통합 처리 프로세서

사용 예시:
    from app.modules.core.privacy.review import (
        HybridPIIDetector,
        PIIPolicyEngine,
        PIIAuditLogger,
        PIIReviewProcessor,
    )

    # 컴포넌트 초기화
    detector = HybridPIIDetector()
    policy_engine = PIIPolicyEngine()
    audit_logger = PIIAuditLogger(mongo_collection)

    # 프로세서 생성
    processor = PIIReviewProcessor(detector, policy_engine, audit_logger)

    # 문서 처리
    result = await processor.process_text("연락처: 010-1234-5678")
    print(result.processed_content)  # "연락처: [전화번호]"

구현일: 2025-12-01
"""

from .audit import PIIAuditLogger
from .detector import HybridPIIDetector, PIIDetectorProtocol
from .models import (
    AuditRecord,
    DetectionMethod,
    PIIEntity,
    PIIPolicy,
    PIIType,
    PolicyAction,
    PolicyDecision,
    ProcessResult,
)
from .policy import PIIPolicyEngine
from .processor import (
    Document,
    PIIReviewDecorator,
    PIIReviewError,
    PIIReviewProcessor,
    PIIViolationError,
)

__all__ = [
    # 탐지기
    "HybridPIIDetector",
    "PIIDetectorProtocol",
    # 정책 엔진
    "PIIPolicyEngine",
    # 감사 로거
    "PIIAuditLogger",
    # 프로세서
    "PIIReviewProcessor",
    "PIIReviewDecorator",
    # 모델
    "PIIEntity",
    "PIIType",
    "PIIPolicy",
    "PolicyAction",
    "PolicyDecision",
    "ProcessResult",
    "AuditRecord",
    "DetectionMethod",
    "Document",
    # 예외
    "PIIReviewError",
    "PIIViolationError",
]
