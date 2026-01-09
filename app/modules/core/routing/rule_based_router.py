"""
RuleBasedRouter - 규칙 기반 쿼리 라우팅 모듈

이 모듈은 사용자 쿼리를 빠르게 분석하여 적절한 라우트로 보내는 규칙 기반 라우터입니다.
- 인사말, 상식 질문 등을 즉시 응답 (direct_answer)
- 일반 질문을 RAG 파이프라인으로 라우팅
- 프롬프트 인젝션, 유해 컨텐츠, 범위 이탈 탐지

성능 목표: 3-8ms 응답 시간
"""

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import yaml

from ....lib.logger import get_logger
from .rule_manager import DynamicRuleManager  # 동적 YAML 규칙 관리자

logger = get_logger(__name__)


@dataclass
class RuleMatch:
    """
    규칙 매칭 결과를 나타내는 데이터 클래스

    Attributes:
        rule_name: 매칭된 규칙의 이름 (예: "greeting", "inquiry")
        route: 라우팅 결정 ("rag", "direct_answer", "blocked")
        domain: 도메인 분류 (예: "chitchat", "domain_1", "domain_2", "general")
        intent: 사용자 의도 (예: "greeting", "inquiry", "complaint")
        confidence: 매칭 신뢰도 점수 (0.0 ~ 1.0)
        direct_answer: 즉시 응답할 텍스트 (선택적, route="direct_answer"인 경우)
        metadata: 추가 메타데이터 (선택적)
    """

    rule_name: str
    route: str  # "rag", "direct_answer", "blocked"
    domain: str
    intent: str
    confidence: float
    direct_answer: str | None = None
    metadata: dict[str, Any] | None = None


class RuleBasedRouter:
    """
    규칙 기반 쿼리 라우터

    주요 기능:
    1. 쿼리 정규화 및 캐싱 (성능 최적화)
    2. 안전성 필터 (프롬프트 인젝션, 유해 컨텐츠, 범위 이탈)
    3. 즉시 응답 (인사말, 상식 질문)
    4. 일반 RAG 라우팅

    사용 예시:
        router = RuleBasedRouter(enabled=True)
        result = await router.check_rules("안녕하세요")
        if result and result.route == "direct_answer":
            return result.direct_answer
    """

    def __init__(self, enabled: bool = True, config: dict | None = None):
        """
        RuleBasedRouter 초기화 (DynamicRuleManager 통합)

        Args:
            enabled: 라우터 활성화 여부 (기본값: True)
            config: 설정 딕셔너리 (선택적, None이면 config.yaml 로드)
        """
        self.enabled = enabled
        self.config = config or self._load_config()
        self.rules = self._load_rules()

        # DynamicRuleManager 초기화 (배포 없이 규칙 수정 가능)
        # 경로: app/modules/core/routing/rule_based_router.py → app/config/
        rules_v2_path = (
            Path(__file__).parent.parent.parent.parent / "config" / "routing_rules_v2.yaml"
        )
        self.rule_manager = DynamicRuleManager(
            rule_path=rules_v2_path, auto_reload=True  # 5분마다 자동 리로드
        )
        # 규칙 즉시 로드
        self.rule_manager.load_rules()

        # 통계 추적
        self._stats: dict[str, Any] = {
            "total_checks": 0,
            "cache_hits": 0,
            "rule_matches": 0,
            "direct_answers": 0,
            "blocked_queries": 0,
            "cache_hit_rate": 0.0,
        }

        # v3.0.0: routing_rules_v2.yaml 통합 완료
        legacy_count = len(self.rules)
        v2_exists = rules_v2_path.exists()

        logger.info(
            f"🔀 RuleBasedRouter initialized (enabled={enabled}, "
            f"v2_rules={v2_exists}, legacy_fallback={legacy_count} rules)"
        )

    def _load_config(self) -> dict:
        """설정 파일 로드 (config.yaml)"""
        try:
            # 경로: app/modules/core/routing/rule_based_router.py → app/config/
            config_path = Path(__file__).parent.parent.parent.parent / "config" / "config.yaml"
            with open(config_path, encoding="utf-8") as f:
                full_config = yaml.safe_load(f)
                return cast(dict[Any, Any], full_config.get("query_routing", {}))
        except Exception as e:
            logger.warning(f"⚠️ Failed to load config.yaml, using defaults: {e}")
            return {
                "enabled": True,
                "safety_checks": {
                    "prompt_injection": True,
                    "harmful_content": True,
                    "out_of_scope": True,
                },
                "direct_answer": {
                    "enabled": True,
                    "chitchat_threshold": 0.8,
                    "simple_qa_threshold": 0.7,
                },
            }

    def _load_rules(self) -> dict[str, dict]:
        """
        규칙 정의 로드 (레거시 폴백용)

        v3.0.0부터 DynamicRuleManager (routing_rules_v2.yaml)가 우선 사용됨.
        이 메서드는 v2 매칭 실패 시 폴백용으로만 작동.

        규칙 구조:
        {
            "rule_name": {
                "keywords": ["키워드1", "키워드2"],
                "patterns": ["정규식1", "정규식2"],  # 선택적
                "route": "rag" | "direct_answer" | "blocked",
                "domain": "도메인",
                "intent": "의도",
                "direct_answer": "즉시 응답 텍스트",  # route="direct_answer"인 경우
                "priority": 1-10,  # 선택적, 높을수록 우선
            }
        }
        """
        try:
            # 경로: app/modules/core/routing/rule_based_router.py → app/config/
            rules_path = (
                Path(__file__).parent.parent.parent.parent / "config" / "routing_rules.yaml"
            )
            if rules_path.exists():
                with open(rules_path, encoding="utf-8") as f:
                    logger.info("📄 Loading legacy routing_rules.yaml as fallback")
                    return yaml.safe_load(f) or {}
            else:
                # v3.0.0부터 정상 - routing_rules_v2.yaml만 사용
                logger.info("✅ Using routing_rules_v2.yaml only (no legacy fallback)")
                return {}  # 빈 딕셔너리 반환 (DynamicRuleManager에만 의존)
        except Exception as e:
            logger.error(f"❌ Failed to load routing_rules.yaml: {e}")
            return {}  # 에러 시에도 빈 딕셔너리 반환

    def _get_default_rules(self) -> dict[str, dict]:
        """
        최소한의 기본 규칙 정의 (폴백용)

        v3.3.0 리팩토링:
        - DynamicRuleManager (routing_rules_v2.yaml)가 우선 사용됨
        - 이 메서드는 v2 규칙 로드 실패 시 폴백으로만 사용
        - 필수 안전 규칙만 유지하여 코드 단순화
        """
        return {
            # 프롬프트 인젝션 탐지 (필수 안전 규칙)
            "prompt_injection": {
                "keywords": [
                    "이전 지시",
                    "시스템 프롬프트",
                    "역할 변경",
                    "ignore",
                    "previous instructions",
                    "system prompt",
                    "jailbreak",
                ],
                "patterns": [
                    r"이전\s*(지시|명령|프롬프트).*무시",
                    r"ignore\s+(previous|all)\s+instructions",
                ],
                "route": "blocked",
                "domain": "security",
                "intent": "injection",
                "direct_answer": "🚫 보안상의 이유로 요청을 처리할 수 없습니다.",
                "priority": 10,
            },
            # 기본 인사말 (폴백)
            "greeting": {
                "keywords": ["안녕", "hi", "hello"],
                "route": "direct_answer",
                "domain": "chitchat",
                "intent": "greeting",
                "direct_answer": "안녕하세요! 무엇을 도와드릴까요?",
                "priority": 9,
            },
            # 감사 인사 (폴백)
            "thanks": {
                "keywords": ["고마워", "감사", "thanks"],
                "route": "direct_answer",
                "domain": "chitchat",
                "intent": "thanks",
                "direct_answer": "도움이 되셨다니 기쁩니다!",
                "priority": 9,
            },
        }
        # 참고: 상세 규칙은 routing_rules_v2.yaml에서 관리
        # - harmful_content (유해 표현)
        # - out_of_scope (범위 이탈)
        # - cost_inquiry (비용 문의)
        # 등은 DynamicRuleManager가 처리

    @staticmethod
    @lru_cache(maxsize=1000)
    def _normalize_query(query: str) -> str:
        """
        쿼리 정규화 (캐싱 적용)

        - 소문자 변환
        - 과도한 공백 제거
        - 양 끝 공백 제거

        Args:
            query: 원본 쿼리

        Returns:
            정규화된 쿼리
        """
        return re.sub(r"\s+", " ", query.lower().strip())

    def _match_rule(self, query: str, rule: dict) -> float:
        """
        쿼리와 규칙 간의 매칭 점수 계산

        매칭 알고리즘:
        1. 키워드 매칭: 키워드가 쿼리에 포함되어 있는지 확인
        2. 패턴 매칭 (선택적): 정규식 패턴이 일치하는지 확인
        3. 점수 계산: 키워드 하나라도 매칭되면 높은 점수

        Args:
            query: 정규화된 쿼리
            rule: 규칙 정의 딕셔너리

        Returns:
            매칭 점수 (0.0 ~ 1.0)
        """
        score = 0.0

        # 키워드 매칭
        keywords = rule.get("keywords", [])
        if keywords:
            matched_keywords = sum(1 for kw in keywords if kw.lower() in query)
            if matched_keywords > 0:
                # 키워드가 하나라도 매칭되면 기본 점수 0.7
                # 추가 매칭마다 보너스 점수 (최대 1.0)
                keyword_score = min(0.7 + (matched_keywords - 1) * 0.1, 1.0)
                score += keyword_score

        # 패턴 매칭 (정규식) - 키워드 매칭이 없을 때 사용
        if score == 0:
            patterns = rule.get("patterns", [])
            if patterns:
                matched_patterns = sum(
                    1 for pattern in patterns if re.search(pattern, query, re.IGNORECASE)
                )
                if matched_patterns > 0:
                    pattern_score = min(0.8 + (matched_patterns - 1) * 0.1, 1.0)
                    score += pattern_score

        return min(score, 1.0)  # 최대 1.0

    async def check_rules(self, query: str) -> RuleMatch | None:
        """
        쿼리에 대한 규칙 매칭 수행 (3단계 우선순위 처리)

        처리 흐름:
        1. 라우터가 비활성화되어 있으면 None 반환
        2. 쿼리 정규화
        3. 빈 쿼리 체크
        4. DynamicRuleManager로 먼저 매칭 시도 (3단계 우선순위 처리)
           - 1순위: 차단 규칙 (block, security_check) → 즉시 반환
           - 2순위: 복합 쿼리 감지 (greeting + service_keyword) → LLM 라우터로 위임 (None)
           - 3순위: 일반 규칙 매칭 (단순 인사말, 기타)
        5. 매칭 실패 시 기존 규칙으로 폴백 (하위 호환성)

        복합 쿼리 예시:
            "안녕하세요, 서비스 예약하고 싶어요" → None 반환 (LLM 라우터가 판단)
            "안녕하세요" → greeting 직접 응답
            "서비스 예약" → RAG 파이프라인

        Args:
            query: 사용자 쿼리 문자열

        Returns:
            RuleMatch 객체 (매칭 성공) 또는 None (LLM 라우터로 위임)
        """
        # 라우터 비활성화 체크
        if not self.enabled:
            return None

        # 통계 업데이트
        self._stats["total_checks"] += 1

        # 쿼리 정규화
        normalized = self._normalize_query(query)

        # 빈 쿼리 체크
        if not normalized:
            return None

        # 1단계: DynamicRuleManager로 먼저 매칭 시도
        try:
            dynamic_match = self.rule_manager.match_rule(query, language="ko")

            if dynamic_match and dynamic_match.get("action") != "rag":  # rag는 기본 액션이므로 스킵
                action: str = str(dynamic_match.get("action", ""))
                rule_name: str = str(dynamic_match.get("rule_name", "unknown"))

                # ========================================
                # 3단계 우선순위 처리
                # ========================================

                # 1순위: 차단 규칙은 즉시 반환 (최고 우선순위)
                if action in ["block", "security_check"]:
                    self._stats["rule_matches"] += 1

                    result = RuleMatch(
                        rule_name=rule_name,
                        route=self._convert_action_to_route(action),
                        domain=dynamic_match.get("description", "security"),
                        intent=rule_name,
                        confidence=1.0,
                        direct_answer=dynamic_match.get("response"),
                        metadata={
                            "source": "DynamicRuleManager",
                            "matched_keyword": dynamic_match.get("matched_keyword"),
                            "priority": dynamic_match.get("priority"),
                        },
                    )

                    self._stats["blocked_queries"] += 1

                    logger.info(
                        f"🚨 차단 규칙 매칭: {rule_name} "
                        f"(keyword={dynamic_match.get('matched_keyword')})"
                    )

                    return result

                # 2순위: 복합 쿼리 감지 (인사말 + 도메인 서비스 키워드)
                if action == "direct_answer" and rule_name == "greeting":
                    # 도메인 서비스 관련 키워드 체크 (routing_rules_v2.yaml의 settings.service_keywords에서 로드)
                    # 이를 통해 "안녕하세요, 비용 알려주세요" 같은 복합 쿼리를 LLM 라우터로 위임 가능
                    service_settings = self.rule_manager.settings.get("service_keywords", {})
                    # 언어별 키워드 추출 (기본: ko)
                    service_keywords = service_settings.get("ko", [])

                    has_product_keyword = any(kw in normalized for kw in service_keywords)

                    if has_product_keyword:
                        logger.info(
                            f"🔀 복합 쿼리 감지: greeting + service_keyword "
                            f"→ LLM 라우터로 위임 (matched_greeting: {dynamic_match.get('matched_keyword')})"
                        )
                        # LLM 라우터가 판단하도록 None 반환
                        return None

                # 3순위: 일반 규칙 매칭 (단순 인사말 또는 기타)
                self._stats["rule_matches"] += 1

                result = RuleMatch(
                    rule_name=rule_name,
                    route=self._convert_action_to_route(action),
                    domain=dynamic_match.get("description", "dynamic"),
                    intent=rule_name,
                    confidence=1.0,  # DynamicRuleManager는 명확한 매칭
                    direct_answer=dynamic_match.get("response"),
                    metadata={
                        "source": "DynamicRuleManager",
                        "matched_keyword": dynamic_match.get("matched_keyword"),
                        "priority": dynamic_match.get("priority"),
                    },
                )

                # 통계 업데이트
                if result.route == "direct_answer":
                    self._stats["direct_answers"] += 1
                elif result.route == "blocked":
                    self._stats["blocked_queries"] += 1

                logger.debug(
                    f"✅ Dynamic rule matched: {result.rule_name} "
                    f"(route={result.route}, keyword={dynamic_match.get('matched_keyword')})"
                )

                return result
        except Exception as e:
            logger.warning(f"⚠️ DynamicRuleManager matching failed, fallback to static rules: {e}")

        # 2단계: 기존 규칙으로 폴백 (하위 호환성)

        # 우선순위 순으로 정렬된 규칙 목록
        sorted_rules = sorted(
            self.rules.items(),
            key=lambda x: x[1].get("priority", 5),
            reverse=True,  # 우선순위 높은 순
        )

        # 규칙 순회 및 매칭
        for rule_name, rule_def in sorted_rules:
            score = self._match_rule(normalized, rule_def)

            # 임계값 체크 (0.6 이상)
            if score >= 0.6:
                self._stats["rule_matches"] += 1

                # RuleMatch 객체 생성
                result = RuleMatch(
                    rule_name=rule_name,
                    route=rule_def["route"],
                    domain=rule_def["domain"],
                    intent=rule_def["intent"],
                    confidence=score,
                    direct_answer=rule_def.get("direct_answer"),
                    metadata={
                        "query": query,
                        "normalized_query": normalized,
                        "priority": rule_def.get("priority", 5),
                    },
                )

                # 통계 업데이트
                if result.route == "direct_answer":
                    self._stats["direct_answers"] += 1
                elif result.route == "blocked":
                    self._stats["blocked_queries"] += 1

                logger.debug(
                    f"✅ Rule matched: {rule_name} "
                    f"(route={result.route}, confidence={score:.2f})"
                )

                return result

        # 매칭 실패
        return None

    def get_stats(self) -> dict[str, Any]:
        """
        라우터 통계 반환

        Returns:
            통계 딕셔너리 (total_checks, cache_hits, rule_matches 등)
        """
        stats = self._stats.copy()

        # 캐시 히트율 계산
        if stats["total_checks"] > 0:
            # LRU 캐시 정보 가져오기
            cache_info = self._normalize_query.cache_info()
            stats["cache_hits"] = cache_info.hits
            stats["cache_misses"] = cache_info.misses
            stats["cache_hit_rate"] = (
                cache_info.hits / (cache_info.hits + cache_info.misses) * 100
                if (cache_info.hits + cache_info.misses) > 0
                else 0.0
            )
        else:
            stats["cache_hit_rate"] = 0.0

        return stats

    def reset_stats(self) -> None:
        """통계 초기화"""
        self._stats = {
            "total_checks": 0,
            "cache_hits": 0,
            "rule_matches": 0,
            "direct_answers": 0,
            "blocked_queries": 0,
        }
        # 캐시도 초기화
        self._normalize_query.cache_clear()
        logger.info("📊 Router statistics reset")

    def _convert_action_to_route(self, action: str) -> str:
        """
        DynamicRuleManager의 action을 RuleMatch의 route로 변환

        Args:
            action: DynamicRuleManager의 action (security_check, block, expand_scope, direct_answer, rag)

        Returns:
            RuleMatch의 route (rag, direct_answer, blocked)
        """
        action_to_route = {
            "security_check": "blocked",
            "block": "blocked",
            "direct_answer": "direct_answer",
            "expand_scope": "rag",
            "rag": "rag",
        }

        return action_to_route.get(action, "rag")  # 기본값: rag
