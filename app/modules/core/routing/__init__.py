"""
Routing Module - 쿼리 라우팅 및 복잡도 분석 모듈

쿼리의 복잡도를 분석하고 적절한 처리 전략을 결정하는 모듈들:
- LLM 기반 쿼리 라우터 (LLMQueryRouter)
- 규칙 기반 라우터 (RuleBasedRouter)
- 복잡도 계산기 (ComplexityCalculator)

사용 예시:
    from app.modules.core.routing import LLMQueryRouter, ComplexityCalculator

    # 복잡도 계산
    calculator = ComplexityCalculator()
    complexity = calculator.calculate(query="복잡한 질문")

    # LLM 라우터
    router = LLMQueryRouter(config)
    await router.initialize()
    routing_decision = await router.route_query(query="질문", context={})
"""

# LLM Query Router
# Complexity Calculator
from .complexity_calculator import ComplexityCalculator, ComplexityResult
from .llm_query_router import LLMQueryRouter, QueryProfile, RoutingDecision

# Rule-Based Router
from .rule_based_router import RuleBasedRouter, RuleMatch

__all__ = [
    # LLM Router
    "LLMQueryRouter",
    "QueryProfile",
    "RoutingDecision",
    # Rule-Based Router
    "RuleBasedRouter",
    "RuleMatch",
    # Complexity Calculator
    "ComplexityCalculator",
    "ComplexityResult",
]
