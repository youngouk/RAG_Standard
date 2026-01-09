"""
PII Policy Engine 단위 테스트

PIIPolicyEngine의 정책 결정 로직 검증.

테스트 케이스:
1. REVIEW_ONLY 정책 적용
2. MASK_AND_PROCEED 정책 적용
3. BLOCK_ON_VIOLATION 정책 적용
4. QUARANTINE 임계값 검증
5. 신뢰도 필터링

구현일: 2025-12-01
"""

import pytest

from app.modules.core.privacy.review import (
    DetectionMethod,
    PIIEntity,
    PIIPolicy,
    PIIPolicyEngine,
    PIIType,
    PolicyAction,
)


class TestPIIPolicyEngine:
    """PIIPolicyEngine 테스트 클래스"""

    @pytest.fixture
    def default_engine(self) -> PIIPolicyEngine:
        """기본 정책 엔진"""
        policy = PIIPolicy(
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
            },
            quarantine_threshold=20,
            min_confidence=0.7,
        )
        return PIIPolicyEngine(policy=policy)

    @pytest.fixture
    def strict_engine(self) -> PIIPolicyEngine:
        """엄격한 정책 엔진 (모두 차단)"""
        policy = PIIPolicy(
            name="strict",
            entity_actions={
                PIIType.PHONE: PolicyAction.BLOCK_ON_VIOLATION,
                PIIType.EMAIL: PolicyAction.BLOCK_ON_VIOLATION,
                PIIType.SSN: PolicyAction.BLOCK_ON_VIOLATION,
                PIIType.ACCOUNT: PolicyAction.BLOCK_ON_VIOLATION,
                PIIType.CARD: PolicyAction.BLOCK_ON_VIOLATION,
                PIIType.PERSON_NAME: PolicyAction.BLOCK_ON_VIOLATION,
                PIIType.ADDRESS: PolicyAction.BLOCK_ON_VIOLATION,
                PIIType.ORGANIZATION: PolicyAction.BLOCK_ON_VIOLATION,
            },
            quarantine_threshold=5,
            min_confidence=0.5,
        )
        return PIIPolicyEngine(policy=policy)

    def _create_entity(
        self,
        pii_type: PIIType,
        value: str = "test",
        confidence: float = 0.9,
    ) -> PIIEntity:
        """테스트용 PIIEntity 생성 헬퍼"""
        return PIIEntity(
            entity_type=pii_type,
            value=value,
            start_pos=0,
            end_pos=len(value),
            confidence=confidence,
            detection_method=DetectionMethod.REGEX,
            context="테스트 문맥",
        )

    # ========================================
    # REVIEW_ONLY 정책 테스트
    # ========================================

    def test_review_only_for_person_name(self, default_engine: PIIPolicyEngine) -> None:
        """이름은 REVIEW_ONLY 정책 적용"""
        entities = [self._create_entity(PIIType.PERSON_NAME, "홍길동")]
        decision = default_engine.evaluate(entities)

        # person_name은 review 정책이므로 REVIEW_ONLY
        assert decision.action == PolicyAction.REVIEW_ONLY
        assert len(decision.entities_to_mask) == 0

    def test_review_only_for_organization(self, default_engine: PIIPolicyEngine) -> None:
        """기관명은 REVIEW_ONLY 정책 적용"""
        entities = [self._create_entity(PIIType.ORGANIZATION, "삼성전자")]
        decision = default_engine.evaluate(entities)

        assert decision.action == PolicyAction.REVIEW_ONLY

    # ========================================
    # MASK_AND_PROCEED 정책 테스트
    # ========================================

    def test_mask_phone_number(self, default_engine: PIIPolicyEngine) -> None:
        """전화번호는 마스킹 후 진행"""
        entities = [self._create_entity(PIIType.PHONE, "010-1234-5678")]
        decision = default_engine.evaluate(entities)

        assert decision.action == PolicyAction.MASK_AND_PROCEED
        assert len(decision.entities_to_mask) == 1
        assert decision.entities_to_mask[0].entity_type == PIIType.PHONE

    def test_mask_email(self, default_engine: PIIPolicyEngine) -> None:
        """이메일은 마스킹 후 진행"""
        entities = [self._create_entity(PIIType.EMAIL, "test@example.com")]
        decision = default_engine.evaluate(entities)

        assert decision.action == PolicyAction.MASK_AND_PROCEED
        assert len(decision.entities_to_mask) == 1

    def test_mask_account_number(self, default_engine: PIIPolicyEngine) -> None:
        """계좌번호는 마스킹 후 진행"""
        entities = [self._create_entity(PIIType.ACCOUNT, "123-456-789012")]
        decision = default_engine.evaluate(entities)

        assert decision.action == PolicyAction.MASK_AND_PROCEED
        assert len(decision.entities_to_mask) == 1

    # ========================================
    # BLOCK_ON_VIOLATION 정책 테스트
    # ========================================

    def test_block_ssn(self, default_engine: PIIPolicyEngine) -> None:
        """주민등록번호는 차단"""
        entities = [self._create_entity(PIIType.SSN, "900101-1234567")]
        decision = default_engine.evaluate(entities)

        assert decision.action == PolicyAction.BLOCK_ON_VIOLATION
        assert decision.requires_human_review is True

    def test_block_card_number(self, default_engine: PIIPolicyEngine) -> None:
        """카드번호는 차단"""
        entities = [self._create_entity(PIIType.CARD, "1234-5678-9012-3456")]
        decision = default_engine.evaluate(entities)

        assert decision.action == PolicyAction.BLOCK_ON_VIOLATION

    def test_strict_policy_blocks_all(self, strict_engine: PIIPolicyEngine) -> None:
        """엄격한 정책은 모든 PII 차단"""
        entities = [self._create_entity(PIIType.PHONE, "010-1234-5678")]
        decision = strict_engine.evaluate(entities)

        assert decision.action == PolicyAction.BLOCK_ON_VIOLATION

    # ========================================
    # QUARANTINE 임계값 테스트
    # ========================================

    def test_quarantine_when_exceeds_threshold(self, default_engine: PIIPolicyEngine) -> None:
        """PII 개수가 임계값 초과 시 격리"""
        # 20개 이상의 마스킹 대상 PII 생성
        entities = [self._create_entity(PIIType.PHONE, f"010-1234-{i:04d}") for i in range(25)]
        decision = default_engine.evaluate(entities)

        assert decision.action == PolicyAction.QUARANTINE
        assert "초과" in decision.reason or "threshold" in decision.reason.lower()

    def test_no_quarantine_below_threshold(self, default_engine: PIIPolicyEngine) -> None:
        """PII 개수가 임계값 미만이면 정상 처리"""
        entities = [self._create_entity(PIIType.PHONE, f"010-1234-{i:04d}") for i in range(5)]
        decision = default_engine.evaluate(entities)

        # 격리가 아닌 마스킹 처리
        assert decision.action == PolicyAction.MASK_AND_PROCEED

    # ========================================
    # 신뢰도 필터링 테스트
    # ========================================

    def test_low_confidence_filtered(self, default_engine: PIIPolicyEngine) -> None:
        """신뢰도가 낮은 엔티티는 필터링"""
        entities = [
            self._create_entity(PIIType.PHONE, "010-1234-5678", confidence=0.5),  # 필터링
            self._create_entity(PIIType.EMAIL, "test@example.com", confidence=0.9),  # 유지
        ]
        decision = default_engine.evaluate(entities)

        # 신뢰도 0.7 미만은 필터링됨
        # 이메일만 마스킹 대상
        assert decision.action == PolicyAction.MASK_AND_PROCEED
        assert len(decision.entities_to_mask) == 1
        assert decision.entities_to_mask[0].entity_type == PIIType.EMAIL

    def test_all_low_confidence_results_in_review(self, default_engine: PIIPolicyEngine) -> None:
        """모든 엔티티가 신뢰도 낮으면 REVIEW_ONLY"""
        entities = [
            self._create_entity(PIIType.PHONE, "010-1234-5678", confidence=0.3),
            self._create_entity(PIIType.EMAIL, "test@example.com", confidence=0.4),
        ]
        decision = default_engine.evaluate(entities)

        # 모두 필터링되어 처리할 엔티티 없음
        assert decision.action == PolicyAction.REVIEW_ONLY

    # ========================================
    # 복합 시나리오 테스트
    # ========================================

    def test_mixed_actions_priority(self, default_engine: PIIPolicyEngine) -> None:
        """여러 정책이 혼합된 경우 우선순위 적용"""
        entities = [
            self._create_entity(PIIType.PHONE, "010-1234-5678"),  # mask
            self._create_entity(PIIType.SSN, "900101-1234567"),  # block (우선)
            self._create_entity(PIIType.PERSON_NAME, "홍길동"),  # review
        ]
        decision = default_engine.evaluate(entities)

        # block이 mask/review보다 우선
        assert decision.action == PolicyAction.BLOCK_ON_VIOLATION

    def test_mask_and_review_mixed(self, default_engine: PIIPolicyEngine) -> None:
        """마스킹과 리뷰가 혼합된 경우"""
        entities = [
            self._create_entity(PIIType.PHONE, "010-1234-5678"),  # mask
            self._create_entity(PIIType.PERSON_NAME, "홍길동"),  # review
        ]
        decision = default_engine.evaluate(entities)

        # mask가 review보다 우선 (적극적 처리)
        assert decision.action == PolicyAction.MASK_AND_PROCEED
        assert len(decision.entities_to_mask) == 1

    def test_empty_entities(self, default_engine: PIIPolicyEngine) -> None:
        """빈 엔티티 리스트 처리"""
        decision = default_engine.evaluate([])

        assert decision.action == PolicyAction.REVIEW_ONLY
        assert len(decision.entities_to_mask) == 0
        assert decision.requires_human_review is False

    # ========================================
    # 정책 정보 테스트
    # ========================================

    def test_decision_includes_reason(self, default_engine: PIIPolicyEngine) -> None:
        """결정에 사유가 포함됨"""
        entities = [self._create_entity(PIIType.SSN, "900101-1234567")]
        decision = default_engine.evaluate(entities)

        assert len(decision.reason) > 0
        assert "ssn" in decision.reason.lower() or "민감" in decision.reason

    def test_decision_includes_policy_name(self, default_engine: PIIPolicyEngine) -> None:
        """결정에 정책명이 포함됨"""
        entities = [self._create_entity(PIIType.PHONE, "010-1234-5678")]
        decision = default_engine.evaluate(entities)

        # reason에 정책명 또는 관련 정보 포함
        assert len(decision.reason) > 0


class TestPIIPolicy:
    """PIIPolicy 데이터 클래스 테스트"""

    def test_default_policy_creation(self) -> None:
        """기본 정책 생성"""
        policy = PIIPolicy.default()

        assert policy.name == "default"
        assert policy.quarantine_threshold == 20
        assert policy.min_confidence == 0.7
        assert PIIType.PHONE in policy.entity_actions
        assert policy.entity_actions[PIIType.SSN] == PolicyAction.BLOCK_ON_VIOLATION

    def test_custom_policy_creation(self) -> None:
        """커스텀 정책 생성"""
        policy = PIIPolicy(
            name="custom",
            entity_actions={
                PIIType.PHONE: PolicyAction.REVIEW_ONLY,
            },
            quarantine_threshold=10,
            min_confidence=0.5,
        )

        assert policy.name == "custom"
        assert policy.quarantine_threshold == 10
        assert policy.entity_actions[PIIType.PHONE] == PolicyAction.REVIEW_ONLY
