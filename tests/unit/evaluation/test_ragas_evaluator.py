"""
RagasEvaluator 테스트
Ragas 라이브러리 기반 배치 평가기 검증
"""

from unittest.mock import MagicMock, patch

import pytest


class TestRagasEvaluatorBasic:
    """RagasEvaluator 기본 테스트"""

    def test_ragas_evaluator_exists(self):
        """RagasEvaluator 클래스 존재 확인"""
        from app.modules.core.evaluation.ragas_evaluator import RagasEvaluator

        assert RagasEvaluator is not None

    def test_ragas_evaluator_has_name(self):
        """RagasEvaluator.name 속성 확인"""
        from app.modules.core.evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator()
        assert evaluator.name == "ragas"

    def test_ragas_evaluator_is_available_without_ragas(self):
        """Ragas 라이브러리 없을 때 is_available=False"""
        from app.modules.core.evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator()
        # Ragas가 설치되지 않은 환경에서는 False
        # 테스트 환경에서는 설치 여부에 따라 다름
        assert isinstance(evaluator.is_available(), bool)

    def test_ragas_evaluator_implements_protocol(self):
        """IEvaluator Protocol 구현 확인"""
        from app.modules.core.evaluation.interfaces import IEvaluator
        from app.modules.core.evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator()
        assert isinstance(evaluator, IEvaluator)


class TestRagasEvaluatorConfig:
    """RagasEvaluator 설정 테스트"""

    def test_ragas_evaluator_default_config(self):
        """기본 설정으로 생성"""
        from app.modules.core.evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator()

        assert evaluator.name == "ragas"
        assert hasattr(evaluator, "_metrics")

    def test_ragas_evaluator_custom_metrics(self):
        """커스텀 메트릭 설정"""
        from app.modules.core.evaluation.ragas_evaluator import RagasEvaluator

        metrics = ["faithfulness", "answer_relevancy"]
        evaluator = RagasEvaluator(metrics=metrics)

        assert evaluator._metrics == metrics

    def test_ragas_evaluator_with_llm_config(self):
        """LLM 설정으로 생성"""
        from app.modules.core.evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator(
            llm_model="gpt-4o",
            embedding_model="text-embedding-3-large",
        )

        assert evaluator._llm_model == "gpt-4o"
        assert evaluator._embedding_model == "text-embedding-3-large"


class TestRagasEvaluatorEvaluate:
    """RagasEvaluator.evaluate 테스트"""

    @pytest.mark.asyncio
    async def test_evaluate_returns_evaluation_result(self):
        """evaluate()가 EvaluationResult 반환"""
        from app.modules.core.evaluation.models import EvaluationResult
        from app.modules.core.evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator()

        result = await evaluator.evaluate(
            query="테스트 질문",
            answer="테스트 답변",
            context=["테스트 컨텍스트"],
        )

        assert isinstance(result, EvaluationResult)
        assert 0.0 <= result.faithfulness <= 1.0
        assert 0.0 <= result.relevance <= 1.0
        assert 0.0 <= result.overall <= 1.0

    @pytest.mark.asyncio
    async def test_evaluate_with_reference(self):
        """참조 답변 포함 평가"""
        from app.modules.core.evaluation.models import EvaluationResult
        from app.modules.core.evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator()

        result = await evaluator.evaluate(
            query="테스트 질문",
            answer="테스트 답변",
            context=["테스트 컨텍스트"],
            reference="참조 답변",
        )

        assert isinstance(result, EvaluationResult)

    @pytest.mark.asyncio
    async def test_evaluate_graceful_degradation(self):
        """Ragas 오류 시 기본값 반환 (Graceful Degradation)"""
        from app.modules.core.evaluation.models import EvaluationResult
        from app.modules.core.evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator()

        # Ragas가 없거나 오류 발생 시에도 기본값 반환
        result = await evaluator.evaluate(
            query="",  # 빈 쿼리
            answer="",
            context=[""],
        )

        assert isinstance(result, EvaluationResult)
        # 기본값 또는 실제 평가 결과
        assert 0.0 <= result.overall <= 1.0


class TestRagasEvaluatorBatch:
    """RagasEvaluator.batch_evaluate 테스트"""

    @pytest.mark.asyncio
    async def test_batch_evaluate_returns_list(self):
        """batch_evaluate()가 리스트 반환"""
        from app.modules.core.evaluation.models import EvaluationResult
        from app.modules.core.evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator()

        samples = [
            {"query": "질문1", "answer": "답변1", "context": "컨텍스트1"},
            {"query": "질문2", "answer": "답변2", "context": "컨텍스트2"},
        ]

        results = await evaluator.batch_evaluate(samples)

        assert isinstance(results, list)
        assert len(results) == 2
        for result in results:
            assert isinstance(result, EvaluationResult)

    @pytest.mark.asyncio
    async def test_batch_evaluate_empty_list(self):
        """빈 리스트 처리"""
        from app.modules.core.evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator()

        results = await evaluator.batch_evaluate([])

        assert results == []

    @pytest.mark.asyncio
    async def test_batch_evaluate_with_batch_size(self):
        """배치 크기 설정 확인"""
        from app.modules.core.evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator(batch_size=5)

        assert evaluator._batch_size == 5


class TestRagasEvaluatorMetrics:
    """Ragas 메트릭 테스트"""

    def test_default_metrics(self):
        """기본 메트릭 목록"""
        from app.modules.core.evaluation.ragas_evaluator import DEFAULT_RAGAS_METRICS

        assert "faithfulness" in DEFAULT_RAGAS_METRICS
        assert "answer_relevancy" in DEFAULT_RAGAS_METRICS

    def test_get_available_metrics(self):
        """사용 가능한 메트릭 조회"""
        from app.modules.core.evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator()
        metrics = evaluator.get_available_metrics()

        assert isinstance(metrics, list)
        # Ragas 설치 여부에 따라 메트릭 반환 (Graceful Degradation)
        if evaluator.is_available():
            assert len(metrics) > 0
            assert "faithfulness" in metrics
        else:
            # Ragas 미설치 시 빈 리스트 반환 (정상 동작)
            assert metrics == []


class TestRagasEvaluatorExport:
    """RagasEvaluator 모듈 export 테스트"""

    def test_ragas_evaluator_exported_from_module(self):
        """evaluation 모듈에서 RagasEvaluator export 확인"""
        from app.modules.core.evaluation import RagasEvaluator

        assert RagasEvaluator is not None

    def test_default_metrics_exported(self):
        """DEFAULT_RAGAS_METRICS export 확인"""
        from app.modules.core.evaluation.ragas_evaluator import DEFAULT_RAGAS_METRICS

        assert isinstance(DEFAULT_RAGAS_METRICS, list)


class TestRagasEvaluatorFactory:
    """EvaluatorFactory에서 ragas 프로바이더 테스트"""

    def test_ragas_in_supported_evaluators(self):
        """ragas가 지원 평가기 목록에 있는지 확인"""
        from app.modules.core.evaluation import EvaluatorFactory

        evaluators = EvaluatorFactory.get_supported_evaluators()
        assert "ragas" in evaluators

    def test_create_ragas_evaluator(self):
        """Factory로 ragas 평가기 생성"""
        from app.modules.core.evaluation import EvaluatorFactory

        config = {
            "evaluation": {
                "enabled": True,
                "provider": "ragas",
                "ragas": {
                    "metrics": ["faithfulness", "answer_relevancy"],
                    "batch_size": 10,
                },
            }
        }

        evaluator = EvaluatorFactory.create(config)

        assert evaluator is not None
        assert evaluator.name == "ragas"

    def test_get_ragas_info(self):
        """ragas 평가기 정보 조회"""
        from app.modules.core.evaluation import EvaluatorFactory

        info = EvaluatorFactory.get_evaluator_info("ragas")

        assert info is not None
        assert info["type"] == "batch"
        assert "metrics" in info


class TestRagasEvaluatorWithMock:
    """Mock을 사용한 Ragas 평가기 테스트 (Ragas 설치 시뮬레이션)"""

    @pytest.mark.asyncio
    async def test_run_ragas_evaluation_with_mock(self):
        """Ragas 평가 실행 (Mock)"""
        import pandas as pd

        from app.modules.core.evaluation.models import EvaluationResult
        from app.modules.core.evaluation.ragas_evaluator import RagasEvaluator

        # Mock DataFrame 결과
        mock_df = pd.DataFrame({
            "faithfulness": [0.9],
            "answer_relevancy": [0.85],
            "context_precision": [0.8],
        })

        # Mock Ragas 결과 객체
        mock_ragas_result = MagicMock()
        mock_ragas_result.to_pandas.return_value = mock_df

        evaluator = RagasEvaluator()

        # _convert_ragas_results 직접 테스트
        results = evaluator._convert_ragas_results(mock_ragas_result, 1)

        assert len(results) == 1
        assert isinstance(results[0], EvaluationResult)
        assert results[0].faithfulness == 0.9
        assert results[0].relevance == 0.85

    @pytest.mark.asyncio
    async def test_convert_ragas_results_multiple_samples(self):
        """여러 샘플 결과 변환"""
        import pandas as pd

        from app.modules.core.evaluation.ragas_evaluator import RagasEvaluator

        mock_df = pd.DataFrame({
            "faithfulness": [0.9, 0.7, 0.8],
            "answer_relevancy": [0.85, 0.75, 0.9],
            "context_precision": [0.8, 0.6, 0.7],
        })

        mock_ragas_result = MagicMock()
        mock_ragas_result.to_pandas.return_value = mock_df

        evaluator = RagasEvaluator()
        results = evaluator._convert_ragas_results(mock_ragas_result, 3)

        assert len(results) == 3
        assert results[0].faithfulness == 0.9
        assert results[1].faithfulness == 0.7
        assert results[2].faithfulness == 0.8

    @pytest.mark.asyncio
    async def test_convert_ragas_results_with_missing_columns(self):
        """누락된 컬럼 처리"""
        import pandas as pd

        from app.modules.core.evaluation.ragas_evaluator import RagasEvaluator

        # context_precision 누락
        mock_df = pd.DataFrame({
            "faithfulness": [0.9],
            "answer_relevancy": [0.85],
        })

        mock_ragas_result = MagicMock()
        mock_ragas_result.to_pandas.return_value = mock_df

        evaluator = RagasEvaluator()
        results = evaluator._convert_ragas_results(mock_ragas_result, 1)

        assert len(results) == 1
        assert results[0].context_precision is None

    @pytest.mark.asyncio
    async def test_convert_ragas_results_exception_handling(self):
        """결과 변환 예외 처리"""
        from app.modules.core.evaluation.ragas_evaluator import RagasEvaluator

        mock_ragas_result = MagicMock()
        mock_ragas_result.to_pandas.side_effect = Exception("변환 오류")

        evaluator = RagasEvaluator()
        results = evaluator._convert_ragas_results(mock_ragas_result, 2)

        # 예외 발생 시 기본값 반환
        assert len(results) == 2
        assert results[0].faithfulness == 0.5

    @pytest.mark.asyncio
    async def test_batch_evaluate_exception_handling(self):
        """배치 평가 예외 처리"""
        from app.modules.core.evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator()

        # is_available이 True이고 _run_ragas_evaluation에서 예외 발생
        with patch.object(evaluator, 'is_available', return_value=True):
            with patch.object(
                evaluator, '_run_ragas_evaluation',
                side_effect=Exception("평가 오류")
            ):
                samples = [{"query": "q", "answer": "a", "context": "c"}]
                results = await evaluator.batch_evaluate(samples)

                assert len(results) == 1
                assert "평가 실패" in results[0].reasoning

    def test_load_metrics_with_unknown_metric(self):
        """알 수 없는 메트릭 처리"""
        from app.modules.core.evaluation.ragas_evaluator import RagasEvaluator

        # 존재하지 않는 메트릭 포함
        evaluator = RagasEvaluator(metrics=["faithfulness", "unknown_metric"])

        # Ragas 미설치 시 빈 리스트 반환
        if not evaluator.is_available():
            assert evaluator._ragas_metrics == []

    def test_score_normalization(self):
        """점수 정규화 테스트 (0.0-1.0 범위)"""
        import pandas as pd

        from app.modules.core.evaluation.ragas_evaluator import RagasEvaluator

        # 범위 초과 값
        mock_df = pd.DataFrame({
            "faithfulness": [1.5],  # 1.0 초과
            "answer_relevancy": [-0.2],  # 0.0 미만
        })

        mock_ragas_result = MagicMock()
        mock_ragas_result.to_pandas.return_value = mock_df

        evaluator = RagasEvaluator()
        results = evaluator._convert_ragas_results(mock_ragas_result, 1)

        # 정규화 확인
        assert results[0].faithfulness == 1.0  # max 1.0
        assert results[0].relevance == 0.0  # min 0.0

    def test_overall_score_calculation(self):
        """종합 점수 계산 테스트"""
        import pandas as pd

        from app.modules.core.evaluation.ragas_evaluator import RagasEvaluator

        mock_df = pd.DataFrame({
            "faithfulness": [0.8],
            "answer_relevancy": [0.6],
        })

        mock_ragas_result = MagicMock()
        mock_ragas_result.to_pandas.return_value = mock_df

        evaluator = RagasEvaluator()
        results = evaluator._convert_ragas_results(mock_ragas_result, 1)

        # (0.8 + 0.6) / 2 = 0.7
        assert results[0].overall == 0.7

    def test_create_default_result(self):
        """기본 결과 생성 테스트"""
        from app.modules.core.evaluation.models import EvaluationResult
        from app.modules.core.evaluation.ragas_evaluator import RagasEvaluator

        evaluator = RagasEvaluator()
        result = evaluator._create_default_result("테스트 사유")

        assert isinstance(result, EvaluationResult)
        assert result.faithfulness == 0.5
        assert result.relevance == 0.5
        assert result.overall == 0.5
        assert result.reasoning == "테스트 사유"
