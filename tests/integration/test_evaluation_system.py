"""
평가 시스템 통합 테스트
전체 평가 워크플로우 검증 (설정 로딩 → 평가기 생성 → 평가 실행)
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml


class TestEvaluationSystemIntegration:
    """평가 시스템 전체 통합 테스트"""

    def test_evaluation_yaml_loads_correctly(self):
        """evaluation.yaml이 올바르게 로드되는지 확인"""
        config_path = Path("app/config/features/evaluation.yaml")
        assert config_path.exists(), "evaluation.yaml 파일이 없습니다"

        with open(config_path) as f:
            config = yaml.safe_load(f)

        # 최상위 키 확인
        assert "evaluation" in config
        eval_config = config["evaluation"]

        # 필수 설정 확인
        assert "enabled" in eval_config
        assert "provider" in eval_config
        assert eval_config["provider"] in ["internal", "ragas"]

    def test_factory_creates_evaluator_from_config(self):
        """설정 기반으로 평가기가 생성되는지 확인"""
        from app.modules.core.evaluation import EvaluatorFactory

        # internal 프로바이더 설정
        config = {
            "evaluation": {
                "enabled": True,
                "provider": "internal",
            }
        }

        # LLM 클라이언트 없이 생성 (is_available=False)
        evaluator = EvaluatorFactory.create(config)

        assert evaluator is not None
        assert evaluator.name == "internal"
        assert evaluator.is_available() is False  # LLM 없음

    def test_factory_returns_none_when_disabled(self):
        """비활성화 설정 시 None 반환 확인"""
        from app.modules.core.evaluation import EvaluatorFactory

        config = {
            "evaluation": {
                "enabled": False,
            }
        }

        evaluator = EvaluatorFactory.create(config)
        assert evaluator is None

    @pytest.mark.asyncio
    async def test_evaluator_evaluate_with_mock_llm(self):
        """Mock LLM으로 평가 실행 확인"""
        from app.modules.core.evaluation import EvaluationResult, InternalEvaluator

        # Mock LLM 클라이언트 생성
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(
            return_value='{"faithfulness": 0.85, "relevance": 0.90}'
        )

        evaluator = InternalEvaluator(llm_client=mock_llm)

        # 평가 실행
        result = await evaluator.evaluate(
            query="서울 맛집 추천해줘",
            answer="서울에 위치한 맛집 3곳을 추천드립니다.",
            context="서울 맛집 A, B, C 업체 정보...",
        )

        # 결과 검증
        assert isinstance(result, EvaluationResult)
        assert result.faithfulness == 0.85
        assert result.relevance == 0.90
        assert result.overall == 0.875  # 평균

    @pytest.mark.asyncio
    async def test_evaluator_batch_evaluate(self):
        """배치 평가 기능 확인"""
        from app.modules.core.evaluation import EvaluationResult, InternalEvaluator

        # Mock LLM 클라이언트 생성
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(
            return_value='{"faithfulness": 0.8, "relevance": 0.85}'
        )

        evaluator = InternalEvaluator(llm_client=mock_llm)

        # 배치 평가 샘플 생성
        samples = [
            {"query": "질문1", "answer": "답변1", "context": "컨텍스트1"},
            {"query": "질문2", "answer": "답변2", "context": "컨텍스트2"},
            {"query": "질문3", "answer": "답변3", "context": "컨텍스트3"},
        ]

        # 배치 평가 실행
        results = await evaluator.batch_evaluate(samples)

        # 결과 검증
        assert len(results) == 3
        for result in results:
            assert isinstance(result, EvaluationResult)
            assert result.faithfulness == 0.8
            assert result.relevance == 0.85

    @pytest.mark.asyncio
    async def test_di_container_creates_evaluator(self):
        """DI Container를 통한 평가기 생성 확인"""
        from app.core.di_container import create_evaluator_instance

        # 활성화된 설정
        config = {
            "evaluation": {
                "enabled": True,
                "provider": "internal",
                "internal": {
                    "model": "google/gemini-2.5-flash-lite",
                    "timeout": 10.0,
                },
            }
        }

        # Mock LLM Factory
        mock_llm_factory = MagicMock()
        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value='{"faithfulness": 0.9}')
        mock_llm_factory.get_client.return_value = mock_client

        evaluator = await create_evaluator_instance(
            config=config,
            llm_factory=mock_llm_factory,
        )

        assert evaluator is not None
        assert evaluator.name == "internal"

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_llm_error(self):
        """LLM 오류 시 기본값 반환 (Graceful Degradation)"""
        from app.modules.core.evaluation import EvaluationResult, InternalEvaluator

        # 오류를 발생시키는 Mock LLM
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(side_effect=Exception("LLM 호출 실패"))

        evaluator = InternalEvaluator(llm_client=mock_llm)

        # 평가 실행 (오류 발생해도 기본값 반환)
        result = await evaluator.evaluate(
            query="테스트 질문",
            answer="테스트 답변",
            context="테스트 컨텍스트",
        )

        # 기본값 반환 확인 (graceful degradation)
        assert isinstance(result, EvaluationResult)
        assert result.faithfulness == 0.5  # 기본값
        assert result.relevance == 0.5  # 기본값
        # 오류 메시지 확인 (한국어 또는 영어)
        assert any(
            keyword in result.reasoning.lower()
            for keyword in ["오류", "error", "실패", "fail"]
        )

    def test_feedback_data_validation(self):
        """FeedbackData 모델 검증"""
        from app.modules.core.evaluation.models import FeedbackData

        # 유효한 피드백
        feedback = FeedbackData(
            session_id="session-123",
            message_id="msg-456",
            rating=1,
            comment="좋은 답변이었습니다",
        )

        assert feedback.is_positive is True
        assert feedback.is_negative is False

        # 부정적 피드백
        negative_feedback = FeedbackData(
            session_id="session-123",
            message_id="msg-456",
            rating=-1,
        )

        assert negative_feedback.is_positive is False
        assert negative_feedback.is_negative is True

    def test_feedback_data_invalid_rating(self):
        """잘못된 rating 값 검증"""
        from app.modules.core.evaluation.models import FeedbackData

        # 잘못된 rating (0)
        with pytest.raises(ValueError):
            FeedbackData(
                session_id="session-123",
                message_id="msg-456",
                rating=0,
            )

        # 잘못된 rating (5)
        with pytest.raises(ValueError):
            FeedbackData(
                session_id="session-123",
                message_id="msg-456",
                rating=5,
            )

    def test_evaluation_result_quality_thresholds(self):
        """품질 임계값 설정 확인"""
        config_path = Path("app/config/features/evaluation.yaml")
        with open(config_path) as f:
            config = yaml.safe_load(f)

        thresholds = config["evaluation"]["thresholds"]

        # 임계값 존재 확인
        assert "min_acceptable" in thresholds
        assert "good_quality" in thresholds
        assert "excellent_quality" in thresholds

        # 값 범위 확인
        assert 0.0 < thresholds["min_acceptable"] < 1.0
        assert thresholds["min_acceptable"] < thresholds["good_quality"]
        assert thresholds["good_quality"] < thresholds["excellent_quality"]

    def test_evaluation_result_is_acceptable(self):
        """EvaluationResult.is_acceptable 메서드 테스트"""
        from app.modules.core.evaluation.models import EvaluationResult

        # 고품질 결과
        high_quality = EvaluationResult(
            faithfulness=0.9,
            relevance=0.85,
            overall=0.875,
        )
        assert high_quality.is_acceptable(threshold=0.7) is True
        assert high_quality.is_acceptable(threshold=0.9) is False

        # 저품질 결과
        low_quality = EvaluationResult(
            faithfulness=0.5,
            relevance=0.4,
            overall=0.45,
        )
        assert low_quality.is_acceptable(threshold=0.7) is False
        assert low_quality.is_acceptable(threshold=0.4) is True


class TestEvaluationAPIIntegration:
    """피드백 API 통합 테스트"""

    def test_feedback_schema_import(self):
        """피드백 스키마 import 확인"""
        from app.api.schemas.feedback import FeedbackRequest, FeedbackResponse

        assert FeedbackRequest is not None
        assert FeedbackResponse is not None

    def test_feedback_endpoint_registered(self):
        """피드백 엔드포인트가 라우터에 등록되어 있는지 확인"""
        from app.api.routers.chat_router import router

        routes = [route.path for route in router.routes]
        feedback_registered = any("feedback" in route for route in routes)
        assert feedback_registered, "피드백 엔드포인트가 등록되지 않았습니다"

    @pytest.mark.asyncio
    async def test_feedback_endpoint_success_response(self):
        """피드백 엔드포인트 성공 응답 확인"""
        from app.api.routers.chat_router import process_feedback
        from app.api.schemas.feedback import FeedbackRequest

        request = FeedbackRequest(
            session_id="session-123",
            message_id="msg-456",
            rating=1,
            comment="좋은 답변이었습니다",
        )

        response = await process_feedback(request)

        assert response.success is True
        assert response.feedback_id is not None
        assert response.message == "피드백이 저장되었습니다"

    @pytest.mark.asyncio
    async def test_feedback_endpoint_golden_candidate(self):
        """Golden Dataset 후보 등록 확인"""
        from app.api.routers.chat_router import process_feedback
        from app.api.schemas.feedback import FeedbackRequest

        # 긍정 피드백 + 쿼리/응답 포함 → Golden 후보
        request = FeedbackRequest(
            session_id="session-123",
            message_id="msg-456",
            rating=1,
            query="서울 맛집 추천해줘",
            response="서울에 위치한 맛집 3곳을 추천드립니다...",
        )

        response = await process_feedback(request)

        assert response.success is True
        assert response.golden_candidate is True

    @pytest.mark.asyncio
    async def test_feedback_endpoint_not_golden_candidate(self):
        """Golden Dataset 후보 미등록 케이스"""
        from app.api.routers.chat_router import process_feedback
        from app.api.schemas.feedback import FeedbackRequest

        # 부정 피드백 → Golden 후보 아님
        request = FeedbackRequest(
            session_id="session-123",
            message_id="msg-456",
            rating=-1,
            query="테스트 질문",
            response="테스트 답변",
        )

        response = await process_feedback(request)

        assert response.success is True
        assert response.golden_candidate is False


class TestEvaluatorFactoryRegistry:
    """EvaluatorFactory 레지스트리 테스트"""

    def test_supported_evaluators_registry(self):
        """지원 평가기 레지스트리 확인"""
        from app.modules.core.evaluation.factory import SUPPORTED_EVALUATORS

        assert "internal" in SUPPORTED_EVALUATORS
        assert "ragas" in SUPPORTED_EVALUATORS

    def test_get_supported_evaluators(self):
        """지원 평가기 목록 조회"""
        from app.modules.core.evaluation import EvaluatorFactory

        evaluators = EvaluatorFactory.get_supported_evaluators()

        assert "internal" in evaluators
        assert "ragas" in evaluators

    def test_get_evaluator_info(self):
        """평가기 정보 조회"""
        from app.modules.core.evaluation import EvaluatorFactory

        info = EvaluatorFactory.get_evaluator_info("internal")

        assert info is not None
        assert "description" in info
        assert "type" in info
        assert info["type"] == "realtime"

    def test_get_evaluator_info_unknown(self):
        """알 수 없는 평가기 정보 조회"""
        from app.modules.core.evaluation import EvaluatorFactory

        info = EvaluatorFactory.get_evaluator_info("unknown_evaluator")
        assert info is None
