"""
평가 시스템 모듈

LLM 답변 품질 평가 및 사용자 피드백 관리.

주요 컴포넌트:
- IEvaluator: 평가기 인터페이스 (Protocol)
- IFeedbackStore: 피드백 저장소 인터페이스 (Protocol)
- EvaluationResult: 평가 결과 데이터 모델
- FeedbackData: 피드백 데이터 모델
- EvaluatorFactory: 설정 기반 평가기 팩토리
- SUPPORTED_EVALUATORS: 지원 평가기 레지스트리

사용 예시:
    ```python
    from app.modules.core.evaluation import (
        IEvaluator,
        EvaluationResult,
        EvaluatorFactory,
    )

    # 설정 기반 평가기 생성 (권장)
    evaluator = EvaluatorFactory.create(config, llm_client=llm)

    # 지원 평가기 조회
    EvaluatorFactory.get_supported_evaluators()

    # Protocol 기반이므로 isinstance 검사 가능
    def process_evaluation(evaluator: IEvaluator):
        result = await evaluator.evaluate(query, answer, context)
        if result.is_acceptable():
            return answer
    ```
"""
from .factory import SUPPORTED_EVALUATORS, EvaluatorFactory
from .interfaces import IEvaluator, IFeedbackStore
from .internal_evaluator import InternalEvaluator
from .models import EvaluationResult, FeedbackData
from .ragas_evaluator import RagasEvaluator

__all__ = [
    # 인터페이스
    "IEvaluator",
    "IFeedbackStore",
    # 데이터 모델
    "EvaluationResult",
    "FeedbackData",
    # 구현체
    "InternalEvaluator",
    "RagasEvaluator",
    # 팩토리
    "EvaluatorFactory",
    "SUPPORTED_EVALUATORS",
]
