"""
IEvaluator 인터페이스 및 모델 테스트
Protocol 기반 인터페이스가 올바르게 정의되었는지 검증
"""
import pytest


class TestEvaluationModels:
    """평가 모델 테스트"""

    def test_evaluation_result_model_exists(self):
        """EvaluationResult 모델 존재 확인"""
        from app.modules.core.evaluation.models import EvaluationResult
        assert EvaluationResult is not None

    def test_evaluation_result_has_required_fields(self):
        """EvaluationResult 필수 필드 확인"""
        from app.modules.core.evaluation.models import EvaluationResult
        result = EvaluationResult(
            faithfulness=0.85,
            relevance=0.90,
            overall=0.875,
            reasoning="테스트 평가",
        )
        assert result.faithfulness == 0.85
        assert result.relevance == 0.90
        assert result.overall == 0.875
        assert result.reasoning == "테스트 평가"

    def test_evaluation_result_validation_faithfulness_range(self):
        """EvaluationResult faithfulness 범위 검증 (0.0-1.0)"""
        from app.modules.core.evaluation.models import EvaluationResult
        with pytest.raises(ValueError, match="faithfulness"):
            EvaluationResult(
                faithfulness=1.5,  # 범위 초과
                relevance=0.90,
                overall=0.875,
            )

    def test_evaluation_result_validation_relevance_range(self):
        """EvaluationResult relevance 범위 검증 (0.0-1.0)"""
        from app.modules.core.evaluation.models import EvaluationResult
        with pytest.raises(ValueError, match="relevance"):
            EvaluationResult(
                faithfulness=0.85,
                relevance=-0.1,  # 음수 불가
                overall=0.875,
            )

    def test_evaluation_result_optional_fields(self):
        """EvaluationResult 선택 필드 확인"""
        from app.modules.core.evaluation.models import EvaluationResult
        result = EvaluationResult(
            faithfulness=0.85,
            relevance=0.90,
            overall=0.875,
            context_precision=0.80,
            answer_similarity=0.95,
        )
        assert result.context_precision == 0.80
        assert result.answer_similarity == 0.95

    def test_feedback_data_model_exists(self):
        """FeedbackData 모델 존재 확인"""
        from app.modules.core.evaluation.models import FeedbackData
        assert FeedbackData is not None

    def test_feedback_data_has_required_fields(self):
        """FeedbackData 필수 필드 확인"""
        from app.modules.core.evaluation.models import FeedbackData
        feedback = FeedbackData(
            session_id="session-123",
            message_id="msg-456",
            rating=1,
            comment="좋은 답변입니다",
        )
        assert feedback.session_id == "session-123"
        assert feedback.message_id == "msg-456"
        assert feedback.rating == 1
        assert feedback.comment == "좋은 답변입니다"

    def test_feedback_data_rating_validation(self):
        """FeedbackData rating 검증 (1 또는 -1)"""
        from app.modules.core.evaluation.models import FeedbackData
        with pytest.raises(ValueError, match="rating"):
            FeedbackData(
                session_id="session-123",
                message_id="msg-456",
                rating=0,  # 0은 불가
            )

    def test_feedback_data_negative_rating(self):
        """FeedbackData 부정적 피드백 (rating=-1)"""
        from app.modules.core.evaluation.models import FeedbackData
        feedback = FeedbackData(
            session_id="session-123",
            message_id="msg-456",
            rating=-1,
            comment="답변이 부정확합니다",
        )
        assert feedback.rating == -1


class TestIEvaluatorProtocol:
    """IEvaluator 프로토콜 테스트"""

    def test_ievaluator_is_protocol(self):
        """IEvaluator가 Protocol인지 확인"""
        from app.modules.core.evaluation.interfaces import IEvaluator
        # Protocol은 typing_extensions 또는 typing에서 가져온 Protocol을 상속
        assert hasattr(IEvaluator, "__protocol_attrs__") or isinstance(IEvaluator, type)

    def test_ievaluator_has_evaluate_method(self):
        """IEvaluator에 evaluate 메서드가 있는지 확인"""
        from app.modules.core.evaluation.interfaces import IEvaluator
        assert hasattr(IEvaluator, "evaluate")

    def test_ievaluator_has_batch_evaluate_method(self):
        """IEvaluator에 batch_evaluate 메서드가 있는지 확인"""
        from app.modules.core.evaluation.interfaces import IEvaluator
        assert hasattr(IEvaluator, "batch_evaluate")

    def test_ievaluator_has_is_available_method(self):
        """IEvaluator에 is_available 메서드가 있는지 확인"""
        from app.modules.core.evaluation.interfaces import IEvaluator
        assert hasattr(IEvaluator, "is_available")

    def test_ievaluator_has_name_property(self):
        """IEvaluator에 name 프로퍼티가 있는지 확인"""
        from app.modules.core.evaluation.interfaces import IEvaluator
        assert hasattr(IEvaluator, "name")

    def test_ievaluator_is_runtime_checkable(self):
        """IEvaluator가 runtime_checkable인지 확인"""
        from app.modules.core.evaluation.interfaces import IEvaluator
        # Python 3.11+에서는 _is_runtime_protocol 속성 사용
        # Python 3.8-3.10에서는 _is_runtime_checkable 속성 사용
        is_runtime = getattr(IEvaluator, "_is_runtime_protocol", None) or \
                     getattr(IEvaluator, "_is_runtime_checkable", False)
        assert is_runtime

    def test_concrete_class_implements_ievaluator(self):
        """구체 클래스가 IEvaluator 프로토콜을 구현하는지 확인"""
        from app.modules.core.evaluation.interfaces import IEvaluator
        from app.modules.core.evaluation.models import EvaluationResult

        class MockEvaluator:
            """테스트용 목 평가기"""
            @property
            def name(self) -> str:
                return "mock"

            async def evaluate(
                self,
                query: str,
                answer: str,
                context: list[str],
                reference: str | None = None,
            ) -> EvaluationResult:
                return EvaluationResult(
                    faithfulness=0.9,
                    relevance=0.9,
                    overall=0.9,
                )

            async def batch_evaluate(self, samples: list) -> list[EvaluationResult]:
                return []

            def is_available(self) -> bool:
                return True

        mock = MockEvaluator()
        # runtime_checkable이므로 isinstance로 검사 가능
        assert isinstance(mock, IEvaluator)


class TestModuleExports:
    """모듈 익스포트 테스트"""

    def test_evaluation_module_exports_ievaluator(self):
        """evaluation 모듈에서 IEvaluator 익스포트 확인"""
        from app.modules.core.evaluation import IEvaluator
        assert IEvaluator is not None

    def test_evaluation_module_exports_evaluation_result(self):
        """evaluation 모듈에서 EvaluationResult 익스포트 확인"""
        from app.modules.core.evaluation import EvaluationResult
        assert EvaluationResult is not None

    def test_evaluation_module_exports_feedback_data(self):
        """evaluation 모듈에서 FeedbackData 익스포트 확인"""
        from app.modules.core.evaluation import FeedbackData
        assert FeedbackData is not None
