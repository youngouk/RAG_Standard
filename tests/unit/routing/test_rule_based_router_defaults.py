"""
RuleBasedRouter 기본 규칙 테스트

Phase 2 R2.3: _get_default_rules() 단순화
TDD RED 단계 - 테스트 먼저 작성
"""

from unittest.mock import patch


class TestRuleBasedRouterDefaults:
    """RuleBasedRouter 기본 규칙 테스트"""

    def test_default_rules_minimal(self) -> None:
        """기본 규칙은 최소한의 안전 규칙만 포함"""
        from app.modules.core.routing.rule_based_router import RuleBasedRouter

        with patch.object(RuleBasedRouter, "_load_config", return_value={}):
            with patch.object(RuleBasedRouter, "_load_rules", return_value={}):
                router = RuleBasedRouter(enabled=True)

                # _get_default_rules()는 최소한의 규칙만 반환
                default_rules = router._get_default_rules()

                # 필수 안전 규칙만 포함 (greeting, thanks, prompt_injection)
                assert "prompt_injection" in default_rules, "프롬프트 인젝션 규칙 필수"

                # 과도한 규칙 제거 확인 (harmful_content 등은 routing_rules_v2.yaml에 있음)
                # 총 규칙 수가 적어야 함 (폴백용이므로)
                assert len(default_rules) <= 5, f"기본 규칙은 5개 이하여야 함: {list(default_rules.keys())}"

    def test_default_rules_contain_essential_safety(self) -> None:
        """필수 안전 규칙 포함 확인"""
        from app.modules.core.routing.rule_based_router import RuleBasedRouter

        with patch.object(RuleBasedRouter, "_load_config", return_value={}):
            with patch.object(RuleBasedRouter, "_load_rules", return_value={}):
                router = RuleBasedRouter(enabled=True)
                default_rules = router._get_default_rules()

                # prompt_injection은 반드시 포함
                assert "prompt_injection" in default_rules
                pi_rule = default_rules["prompt_injection"]

                # 차단 액션 확인
                assert pi_rule["route"] == "blocked"
                assert pi_rule["priority"] == 10  # 최우선

    def test_dynamic_rule_manager_takes_precedence(self) -> None:
        """DynamicRuleManager가 기본 규칙보다 우선"""
        from app.modules.core.routing.rule_based_router import RuleBasedRouter

        with patch.object(RuleBasedRouter, "_load_config", return_value={}):
            with patch.object(RuleBasedRouter, "_load_rules", return_value={}):
                router = RuleBasedRouter(enabled=True)

                # rule_manager가 초기화되어 있어야 함
                assert router.rule_manager is not None
