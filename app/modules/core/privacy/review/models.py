"""
PII Review System 데이터 모델

PII 탐지, 정책 결정, 감사 로그를 위한 데이터 클래스 정의.
모든 모델은 불변(immutable) 설계로 타입 안전성 보장.

구현일: 2025-12-01
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class PIIType(Enum):
    """
    PII(개인식별정보) 유형 정의

    정형 패턴 (Regex 탐지):
        - PHONE: 전화번호
        - EMAIL: 이메일
        - SSN: 주민등록번호
        - ACCOUNT: 계좌번호
        - CARD: 카드번호

    NER 기반 (spaCy 탐지):
        - PERSON_NAME: 인명
        - ADDRESS: 주소
        - ORGANIZATION: 기관명
    """

    # 정형 패턴 (Regex)
    PHONE = "phone"
    EMAIL = "email"
    SSN = "ssn"
    ACCOUNT = "account"
    CARD = "card"

    # NER 기반
    PERSON_NAME = "person_name"
    ADDRESS = "address"
    ORGANIZATION = "organization"

    # 분류 불가
    UNKNOWN = "unknown"


class PolicyAction(Enum):
    """
    PII 정책 처리 액션

    REVIEW_ONLY: 로그만 기록, 원본 유지
    MASK_AND_PROCEED: 마스킹 후 진행
    BLOCK_ON_VIOLATION: 처리 중단 (민감 정보)
    QUARANTINE: 격리 (수동 검토 대기)
    """

    REVIEW_ONLY = "review_only"
    MASK_AND_PROCEED = "mask"
    BLOCK_ON_VIOLATION = "block"
    QUARANTINE = "quarantine"


class DetectionMethod(Enum):
    """PII 탐지 방법"""

    REGEX = "regex"
    NER = "ner"
    HYBRID = "hybrid"


@dataclass(frozen=True)
class PIIEntity:
    """
    탐지된 PII 엔티티

    불변(frozen) 설계로 해시 가능하며 Set/Dict 키로 사용 가능.

    Attributes:
        entity_type: PII 유형 (PHONE, EMAIL, PERSON_NAME 등)
        value: 탐지된 원본 값
        start_pos: 텍스트 내 시작 위치
        end_pos: 텍스트 내 끝 위치
        confidence: 탐지 신뢰도 (0.0 ~ 1.0)
        detection_method: 탐지 방법 (regex, ner, hybrid)
        context: 주변 문맥 (감사용, 선택적)
    """

    entity_type: PIIType
    value: str
    start_pos: int
    end_pos: int
    confidence: float
    detection_method: DetectionMethod
    context: str | None = None

    def __post_init__(self) -> None:
        """유효성 검증"""
        # frozen=True이므로 object.__setattr__ 사용 불가
        # 대신 생성 시점에서만 검증
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {self.confidence}")
        if self.start_pos < 0:
            raise ValueError(f"start_pos must be non-negative, got {self.start_pos}")
        if self.end_pos < self.start_pos:
            raise ValueError(f"end_pos ({self.end_pos}) must be >= start_pos ({self.start_pos})")

    @property
    def length(self) -> int:
        """엔티티 길이"""
        return self.end_pos - self.start_pos

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리 변환 (직렬화용)"""
        return {
            "entity_type": self.entity_type.value,
            "value": self.value,
            "start_pos": self.start_pos,
            "end_pos": self.end_pos,
            "confidence": self.confidence,
            "detection_method": self.detection_method.value,
            "context": self.context,
        }


@dataclass(frozen=True)
class PolicyDecision:
    """
    정책 엔진의 처리 결정

    Attributes:
        action: 결정된 처리 액션
        entities_to_mask: 마스킹 대상 엔티티 목록
        reason: 결정 사유 (로깅용)
        requires_human_review: 수동 검토 필요 여부
    """

    action: PolicyAction
    entities_to_mask: tuple[PIIEntity, ...]  # frozen이므로 tuple 사용
    reason: str
    requires_human_review: bool

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리 변환"""
        return {
            "action": self.action.value,
            "entities_to_mask_count": len(self.entities_to_mask),
            "reason": self.reason,
            "requires_human_review": self.requires_human_review,
        }


@dataclass
class ProcessResult:
    """
    PII 검토 처리 결과

    Attributes:
        document_id: 처리된 문서 ID
        original_content: 원본 텍스트
        processed_content: 처리된 텍스트 (마스킹 적용 또는 None)
        action_taken: 적용된 정책 액션
        entities_detected: 탐지된 PII 개수
        entities_masked: 마스킹된 PII 개수
        audit_id: 감사 로그 ID
        requires_review: 수동 검토 필요 여부
        processing_time_ms: 처리 소요 시간 (밀리초)
    """

    document_id: str
    original_content: str
    processed_content: str | None
    action_taken: PolicyAction
    entities_detected: int
    entities_masked: int
    audit_id: str
    requires_review: bool
    processing_time_ms: float = 0.0

    @property
    def is_blocked(self) -> bool:
        """처리가 차단되었는지 여부"""
        return self.action_taken == PolicyAction.BLOCK_ON_VIOLATION

    @property
    def is_quarantined(self) -> bool:
        """격리 상태인지 여부"""
        return self.action_taken == PolicyAction.QUARANTINE

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리 변환"""
        return {
            "document_id": self.document_id,
            "action_taken": self.action_taken.value,
            "entities_detected": self.entities_detected,
            "entities_masked": self.entities_masked,
            "audit_id": self.audit_id,
            "requires_review": self.requires_review,
            "processing_time_ms": self.processing_time_ms,
            "is_blocked": self.is_blocked,
            "is_quarantined": self.is_quarantined,
        }


@dataclass
class AuditRecord:
    """
    PII 처리 감사 기록

    컴플라이언스 및 추적을 위한 상세 감사 로그.

    Attributes:
        id: 감사 레코드 고유 ID
        timestamp: 기록 시점 (UTC)
        document_id: 처리된 문서 ID
        source_file: 원본 파일명/소스

        detected_entities: 탐지된 엔티티 목록 (값은 해시 처리)
        total_pii_count: 총 PII 개수

        policy_applied: 적용된 정책명
        action_taken: 실행된 액션
        entities_masked: 마스킹된 개수

        processor_version: 프로세서 버전
        processing_time_ms: 처리 소요 시간
    """

    id: str
    timestamp: datetime
    document_id: str
    source_file: str

    # 탐지 결과 (값은 보안을 위해 해시 또는 요약)
    detected_entity_types: list[str]
    total_pii_count: int

    # 처리 결과
    policy_applied: str
    action_taken: PolicyAction
    entities_masked: int

    # 메타데이터
    processor_version: str
    processing_time_ms: float

    # 추가 컨텍스트
    entities: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """MongoDB 저장용 딕셔너리 변환"""
        return {
            "_id": self.id,
            "timestamp": self.timestamp,
            "document_id": self.document_id,
            "source_file": self.source_file,
            "detected_entity_types": self.detected_entity_types,
            "total_pii_count": self.total_pii_count,
            "policy_applied": self.policy_applied,
            "action_taken": self.action_taken.value,
            "entities_masked": self.entities_masked,
            "processor_version": self.processor_version,
            "processing_time_ms": self.processing_time_ms,
            "entities": self.entities,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuditRecord":
        """딕셔너리에서 생성"""
        return cls(
            id=data["_id"],
            timestamp=data["timestamp"],
            document_id=data["document_id"],
            source_file=data["source_file"],
            detected_entity_types=data["detected_entity_types"],
            total_pii_count=data["total_pii_count"],
            policy_applied=data["policy_applied"],
            action_taken=PolicyAction(data["action_taken"]),
            entities_masked=data["entities_masked"],
            processor_version=data["processor_version"],
            processing_time_ms=data["processing_time_ms"],
            entities=data.get("entities", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class PIIPolicy:
    """
    문서 유형별 PII 정책 설정

    Attributes:
        name: 정책 이름
        entity_actions: 엔티티별 처리 방식
        quarantine_threshold: 격리 임계값 (PII 개수)
        min_confidence: 최소 신뢰도 (이하는 무시)
        whitelist_patterns: 오탐 방지 화이트리스트
    """

    name: str
    entity_actions: dict[PIIType, PolicyAction]
    quarantine_threshold: int = 20
    min_confidence: float = 0.7
    whitelist_patterns: list[str] = field(default_factory=list)

    @classmethod
    def default(cls) -> "PIIPolicy":
        """기본 정책 생성"""
        return cls(
            name="default",
            entity_actions={
                PIIType.PHONE: PolicyAction.MASK_AND_PROCEED,
                PIIType.EMAIL: PolicyAction.MASK_AND_PROCEED,
                PIIType.SSN: PolicyAction.BLOCK_ON_VIOLATION,
                PIIType.ACCOUNT: PolicyAction.MASK_AND_PROCEED,
                PIIType.CARD: PolicyAction.BLOCK_ON_VIOLATION,
                PIIType.PERSON_NAME: PolicyAction.REVIEW_ONLY,
                PIIType.ADDRESS: PolicyAction.MASK_AND_PROCEED,
                PIIType.ORGANIZATION: PolicyAction.REVIEW_ONLY,
                PIIType.UNKNOWN: PolicyAction.REVIEW_ONLY,
            },
            quarantine_threshold=20,
            min_confidence=0.7,
            whitelist_patterns=[
                "담당",
                "관리자",
                "직원",
                "고객",
                "가족",
                "친구",
                "팀장",
                "매니저",
                "대표",
                "안내",
                "문의",
                "확인",
                "지원",
            ],
        )
