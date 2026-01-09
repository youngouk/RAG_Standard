"""
Admin Router 단위 테스트

POST /api/admin/evaluate 배치 평가 API 테스트
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.routers.admin_router import batch_evaluate, get_available_providers
from app.api.schemas.evaluation import (
    BatchEvaluateRequest,
    EvaluationSampleSchema,
)
from app.modules.core.evaluation.models import EvaluationResult


class TestBatchEvaluateEndpoint:
    """배치 평가 API 테스트"""

    @pytest.fixture
    def sample_request(self) -> BatchEvaluateRequest:
        """테스트용 요청 데이터"""
        return BatchEvaluateRequest(
            samples=[
                EvaluationSampleSchema(
                    query="테스트 질문",
                    answer="테스트 답변",
                    context="테스트 컨텍스트",
                )
            ],
            provider="internal",
        )

    @pytest.fixture
    def mock_evaluation_result(self) -> EvaluationResult:
        """테스트용 평가 결과"""
        return EvaluationResult(
            faithfulness=0.85,
            relevance=0.90,
            overall=0.875,
            reasoning="테스트 평가 완료",
        )

    @pytest.mark.asyncio
    async def test_batch_evaluate_success(
        self, sample_request: BatchEvaluateRequest, mock_evaluation_result: EvaluationResult
    ):
        """배치 평가 성공 테스트"""
        with patch(
            "app.api.routers.admin_router.EvaluatorFactory"
        ) as mock_factory:
            # Mock 설정
            mock_evaluator = MagicMock()
            mock_evaluator.batch_evaluate = AsyncMock(
                return_value=[mock_evaluation_result]
            )
            mock_factory.create.return_value = mock_evaluator

            # 실행
            response = await batch_evaluate(sample_request)

            # 검증
            assert response.success is True
            assert response.sample_count == 1
            assert len(response.results) == 1
            assert response.results[0].faithfulness == 0.85
            assert response.results[0].relevance == 0.90
            assert response.provider == "internal"

    @pytest.mark.asyncio
    async def test_batch_evaluate_with_multiple_samples(
        self, mock_evaluation_result: EvaluationResult
    ):
        """다중 샘플 평가 테스트"""
        request = BatchEvaluateRequest(
            samples=[
                EvaluationSampleSchema(
                    query=f"질문 {i}",
                    answer=f"답변 {i}",
                    context=f"컨텍스트 {i}",
                )
                for i in range(3)
            ],
            provider="internal",
        )

        with patch(
            "app.api.routers.admin_router.EvaluatorFactory"
        ) as mock_factory:
            mock_evaluator = MagicMock()
            mock_evaluator.batch_evaluate = AsyncMock(
                return_value=[mock_evaluation_result] * 3
            )
            mock_factory.create.return_value = mock_evaluator

            response = await batch_evaluate(request)

            assert response.success is True
            assert response.sample_count == 3
            assert len(response.results) == 3

    @pytest.mark.asyncio
    async def test_batch_evaluate_summary_calculation(
        self, sample_request: BatchEvaluateRequest
    ):
        """요약 통계 계산 테스트"""
        results = [
            EvaluationResult(faithfulness=0.8, relevance=0.9, overall=0.85, reasoning=""),
            EvaluationResult(faithfulness=0.9, relevance=0.8, overall=0.85, reasoning=""),
        ]

        request = BatchEvaluateRequest(
            samples=[
                EvaluationSampleSchema(query="q1", answer="a1", context="c1"),
                EvaluationSampleSchema(query="q2", answer="a2", context="c2"),
            ],
            provider="internal",
        )

        with patch(
            "app.api.routers.admin_router.EvaluatorFactory"
        ) as mock_factory:
            mock_evaluator = MagicMock()
            mock_evaluator.batch_evaluate = AsyncMock(return_value=results)
            mock_factory.create.return_value = mock_evaluator

            response = await batch_evaluate(request)

            # 요약 통계 검증
            assert "avg_faithfulness" in response.summary
            assert "avg_relevance" in response.summary
            assert "avg_overall" in response.summary
            assert response.summary["avg_faithfulness"] == 0.85
            assert response.summary["avg_relevance"] == 0.85

    @pytest.mark.asyncio
    async def test_batch_evaluate_with_ragas_provider(self):
        """Ragas 프로바이더 테스트"""
        request = BatchEvaluateRequest(
            samples=[
                EvaluationSampleSchema(
                    query="질문",
                    answer="답변",
                    context="컨텍스트",
                )
            ],
            provider="ragas",
        )

        with patch(
            "app.api.routers.admin_router.EvaluatorFactory"
        ) as mock_factory:
            mock_evaluator = MagicMock()
            mock_evaluator.batch_evaluate = AsyncMock(
                return_value=[
                    EvaluationResult(
                        faithfulness=0.9,
                        relevance=0.85,
                        overall=0.875,
                        reasoning="Ragas 평가",
                    )
                ]
            )
            mock_factory.create.return_value = mock_evaluator

            response = await batch_evaluate(request)

            assert response.provider == "ragas"
            assert response.success is True


class TestGetAvailableProviders:
    """프로바이더 조회 API 테스트"""

    @pytest.mark.asyncio
    async def test_get_providers(self):
        """프로바이더 목록 조회 테스트"""
        with patch(
            "app.api.routers.admin_router.EvaluatorFactory"
        ) as mock_factory:
            mock_factory.get_supported_evaluators.return_value = ["internal", "ragas"]

            response = await get_available_providers()

            assert "providers" in response
            assert "default" in response
            assert response["default"] == "internal"
            assert "description" in response


class TestBatchEvaluateErrorHandling:
    """배치 평가 에러 핸들링 테스트"""

    @pytest.mark.asyncio
    async def test_batch_evaluate_value_error(self):
        """ValueError 발생 시 400 에러 반환"""
        request = BatchEvaluateRequest(
            samples=[
                EvaluationSampleSchema(
                    query="질문",
                    answer="답변",
                    context="컨텍스트",
                )
            ],
            provider="internal",
        )

        with patch(
            "app.api.routers.admin_router.EvaluatorFactory"
        ) as mock_factory:
            mock_evaluator = MagicMock()
            mock_evaluator.batch_evaluate = AsyncMock(
                side_effect=ValueError("잘못된 입력값")
            )
            mock_factory.create.return_value = mock_evaluator

            # HTTPException 발생 확인
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await batch_evaluate(request)

            assert exc_info.value.status_code == 400
            assert "잘못된 입력값" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_batch_evaluate_generic_error(self):
        """일반 Exception 발생 시 500 에러 반환"""
        request = BatchEvaluateRequest(
            samples=[
                EvaluationSampleSchema(
                    query="질문",
                    answer="답변",
                    context="컨텍스트",
                )
            ],
            provider="internal",
        )

        with patch(
            "app.api.routers.admin_router.EvaluatorFactory"
        ) as mock_factory:
            mock_evaluator = MagicMock()
            mock_evaluator.batch_evaluate = AsyncMock(
                side_effect=Exception("내부 서버 오류")
            )
            mock_factory.create.return_value = mock_evaluator

            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await batch_evaluate(request)

            assert exc_info.value.status_code == 500
            assert "평가 실행 중 오류가 발생했습니다" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_batch_evaluate_pydantic_validation_empty_samples(self):
        """빈 샘플 리스트에 대한 Pydantic 검증"""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            BatchEvaluateRequest(
                samples=[],
                provider="internal",
            )

        # min_length=1 검증 에러 확인
        assert "too_short" in str(exc_info.value)


class TestBatchEvaluateEdgeCases:
    """배치 평가 엣지 케이스 테스트"""

    @pytest.mark.asyncio
    async def test_batch_evaluate_with_reference(self):
        """Reference 필드 포함 평가"""
        request = BatchEvaluateRequest(
            samples=[
                EvaluationSampleSchema(
                    query="질문",
                    answer="답변",
                    context="컨텍스트",
                    reference="정답",  # Reference 포함
                )
            ],
            provider="internal",
        )

        with patch(
            "app.api.routers.admin_router.EvaluatorFactory"
        ) as mock_factory:
            mock_evaluator = MagicMock()
            mock_evaluator.batch_evaluate = AsyncMock(
                return_value=[
                    EvaluationResult(
                        faithfulness=0.95,
                        relevance=0.90,
                        overall=0.925,
                        reasoning="정답 참조 평가",
                    )
                ]
            )
            mock_factory.create.return_value = mock_evaluator

            await batch_evaluate(request)

            # batch_evaluate 호출 시 reference가 포함되었는지 확인
            call_args = mock_evaluator.batch_evaluate.call_args[0][0]
            assert call_args[0]["reference"] == "정답"

    @pytest.mark.asyncio
    async def test_batch_evaluate_with_context_precision(self):
        """Context Precision 포함 결과 테스트"""
        request = BatchEvaluateRequest(
            samples=[
                EvaluationSampleSchema(
                    query="질문",
                    answer="답변",
                    context="컨텍스트",
                )
            ],
            provider="internal",
        )

        with patch(
            "app.api.routers.admin_router.EvaluatorFactory"
        ) as mock_factory:
            mock_evaluator = MagicMock()
            mock_evaluator.batch_evaluate = AsyncMock(
                return_value=[
                    EvaluationResult(
                        faithfulness=0.85,
                        relevance=0.90,
                        overall=0.875,
                        reasoning="평가 완료",
                        context_precision=0.80,  # Context Precision 추가
                    )
                ]
            )
            mock_factory.create.return_value = mock_evaluator

            response = await batch_evaluate(request)

            assert response.results[0].context_precision == 0.80

    @pytest.mark.asyncio
    async def test_batch_evaluate_summary_with_extreme_values(self):
        """극단적인 값을 가진 샘플들의 요약 통계"""
        request = BatchEvaluateRequest(
            samples=[
                EvaluationSampleSchema(query=f"q{i}", answer=f"a{i}", context=f"c{i}")
                for i in range(3)
            ],
            provider="internal",
        )

        results = [
            EvaluationResult(faithfulness=1.0, relevance=1.0, overall=1.0, reasoning=""),
            EvaluationResult(faithfulness=0.0, relevance=0.0, overall=0.0, reasoning=""),
            EvaluationResult(faithfulness=0.5, relevance=0.5, overall=0.5, reasoning=""),
        ]

        with patch(
            "app.api.routers.admin_router.EvaluatorFactory"
        ) as mock_factory:
            mock_evaluator = MagicMock()
            mock_evaluator.batch_evaluate = AsyncMock(return_value=results)
            mock_factory.create.return_value = mock_evaluator

            response = await batch_evaluate(request)

            # 요약 통계 검증
            assert response.summary["min_overall"] == 0.0
            assert response.summary["max_overall"] == 1.0
            assert response.summary["avg_overall"] == 0.5

    @pytest.mark.asyncio
    async def test_batch_evaluate_config_merge(self):
        """설정 병합 테스트 (set_config 사용)"""
        from app.api.routers.admin_router import set_config

        # 기존 설정 주입
        base_config = {
            "generation": {
                "default_provider": "openrouter",
            }
        }
        set_config(base_config)

        request = BatchEvaluateRequest(
            samples=[
                EvaluationSampleSchema(
                    query="질문",
                    answer="답변",
                    context="컨텍스트",
                )
            ],
            provider="ragas",  # 평가기만 변경
        )

        with patch(
            "app.api.routers.admin_router.EvaluatorFactory"
        ) as mock_factory:
            mock_evaluator = MagicMock()
            mock_evaluator.batch_evaluate = AsyncMock(
                return_value=[
                    EvaluationResult(
                        faithfulness=0.9,
                        relevance=0.85,
                        overall=0.875,
                        reasoning="",
                    )
                ]
            )
            mock_factory.create.return_value = mock_evaluator

            await batch_evaluate(request)

            # 평가기 생성 시 설정이 병합되었는지 확인
            create_call_args = mock_factory.create.call_args[0][0]
            assert "generation" in create_call_args  # 기존 설정 포함
            assert create_call_args["evaluation"]["provider"] == "ragas"  # 평가기 설정 오버라이드

    @pytest.mark.asyncio
    async def test_batch_evaluate_rounding_precision(self):
        """요약 통계 소수점 4자리 반올림 검증"""
        request = BatchEvaluateRequest(
            samples=[
                EvaluationSampleSchema(query="q1", answer="a1", context="c1"),
                EvaluationSampleSchema(query="q2", answer="a2", context="c2"),
            ],
            provider="internal",
        )

        results = [
            EvaluationResult(
                faithfulness=0.123456, relevance=0.234567, overall=0.345678, reasoning=""
            ),
            EvaluationResult(
                faithfulness=0.234567, relevance=0.345678, overall=0.456789, reasoning=""
            ),
        ]

        with patch(
            "app.api.routers.admin_router.EvaluatorFactory"
        ) as mock_factory:
            mock_evaluator = MagicMock()
            mock_evaluator.batch_evaluate = AsyncMock(return_value=results)
            mock_factory.create.return_value = mock_evaluator

            response = await batch_evaluate(request)

            # 소수점 4자리 반올림 검증
            assert response.summary["avg_faithfulness"] == 0.1790
            assert response.summary["avg_relevance"] == 0.2901
            assert response.summary["avg_overall"] == 0.4012
