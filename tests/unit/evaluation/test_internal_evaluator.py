"""
InternalEvaluator 단위 테스트

LLM 기반 실시간 내부 평가기 검증.
TDD 방식으로 먼저 테스트 작성 후 구현체 개발.

테스트 범위:
- 초기화 및 IEvaluator Protocol 준수
- LLM 클라이언트 유무에 따른 동작
- 평가 결과 파싱 및 에러 처리
- 배치 평가 기능
"""
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestInternalEvaluatorInit:
    """InternalEvaluator 초기화 테스트"""

    def test_internal_evaluator_exists(self):
        """InternalEvaluator 클래스 존재 확인"""
        from app.modules.core.evaluation.internal_evaluator import InternalEvaluator

        assert InternalEvaluator is not None

    def test_internal_evaluator_implements_ievaluator(self):
        """InternalEvaluator가 IEvaluator Protocol 구현 확인"""
        from app.modules.core.evaluation.interfaces import IEvaluator
        from app.modules.core.evaluation.internal_evaluator import InternalEvaluator

        mock_client = MagicMock()
        evaluator = InternalEvaluator(llm_client=mock_client)
        assert isinstance(evaluator, IEvaluator)

    def test_internal_evaluator_name(self):
        """평가기 이름 확인"""
        from app.modules.core.evaluation.internal_evaluator import InternalEvaluator

        mock_client = MagicMock()
        evaluator = InternalEvaluator(llm_client=mock_client)
        assert evaluator.name == "internal"

    def test_internal_evaluator_is_available_with_client(self):
        """LLM 클라이언트가 있으면 사용 가능"""
        from app.modules.core.evaluation.internal_evaluator import InternalEvaluator

        mock_client = MagicMock()
        evaluator = InternalEvaluator(llm_client=mock_client)
        assert evaluator.is_available() is True

    def test_internal_evaluator_is_not_available_without_client(self):
        """LLM 클라이언트가 없으면 사용 불가"""
        from app.modules.core.evaluation.internal_evaluator import InternalEvaluator

        evaluator = InternalEvaluator(llm_client=None)
        assert evaluator.is_available() is False

    def test_internal_evaluator_default_model(self):
        """기본 모델명 확인"""
        from app.modules.core.evaluation.internal_evaluator import InternalEvaluator

        mock_client = MagicMock()
        evaluator = InternalEvaluator(llm_client=mock_client)
        # 내부 속성 확인 (기본 모델이 설정되어 있어야 함)
        assert evaluator._model == "google/gemini-2.5-flash-lite"

    def test_internal_evaluator_custom_model(self):
        """커스텀 모델 설정 확인"""
        from app.modules.core.evaluation.internal_evaluator import InternalEvaluator

        mock_client = MagicMock()
        evaluator = InternalEvaluator(
            llm_client=mock_client,
            model="openai/gpt-4",
        )
        assert evaluator._model == "openai/gpt-4"

    def test_internal_evaluator_custom_timeout(self):
        """커스텀 타임아웃 설정 확인"""
        from app.modules.core.evaluation.internal_evaluator import InternalEvaluator

        mock_client = MagicMock()
        evaluator = InternalEvaluator(
            llm_client=mock_client,
            timeout=30.0,
        )
        assert evaluator._timeout == 30.0


class TestInternalEvaluatorEvaluate:
    """InternalEvaluator.evaluate() 테스트"""

    @pytest.mark.asyncio
    async def test_evaluate_returns_evaluation_result(self):
        """evaluate()가 EvaluationResult 반환"""
        from app.modules.core.evaluation.internal_evaluator import InternalEvaluator
        from app.modules.core.evaluation.models import EvaluationResult

        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(
            return_value='''
        {
            "faithfulness": 0.9,
            "relevance": 0.85,
            "reasoning": "답변이 컨텍스트에 잘 근거하고 있습니다."
        }
        '''
        )

        evaluator = InternalEvaluator(llm_client=mock_client)

        result = await evaluator.evaluate(
            query="테스트 질문",
            answer="테스트 답변",
            context=["컨텍스트 1", "컨텍스트 2"],
        )

        assert isinstance(result, EvaluationResult)
        assert 0.0 <= result.faithfulness <= 1.0
        assert 0.0 <= result.relevance <= 1.0
        assert 0.0 <= result.overall <= 1.0

    @pytest.mark.asyncio
    async def test_evaluate_calculates_overall_correctly(self):
        """overall 점수가 올바르게 계산되는지 확인"""
        from app.modules.core.evaluation.internal_evaluator import InternalEvaluator

        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(
            return_value='''
        {
            "faithfulness": 0.8,
            "relevance": 0.6,
            "reasoning": "테스트"
        }
        '''
        )

        evaluator = InternalEvaluator(llm_client=mock_client)

        result = await evaluator.evaluate(
            query="질문",
            answer="답변",
            context=["컨텍스트"],
        )

        # overall = faithfulness * 0.5 + relevance * 0.5 = 0.8 * 0.5 + 0.6 * 0.5 = 0.7
        expected_overall = 0.8 * 0.5 + 0.6 * 0.5
        assert abs(result.overall - expected_overall) < 0.01

    @pytest.mark.asyncio
    async def test_evaluate_without_client_returns_default(self):
        """LLM 클라이언트 없이 평가 시 기본값 반환"""
        from app.modules.core.evaluation.internal_evaluator import InternalEvaluator

        evaluator = InternalEvaluator(llm_client=None)

        result = await evaluator.evaluate(
            query="테스트 질문",
            answer="테스트 답변",
            context=["컨텍스트"],
        )

        assert result.overall == 0.5
        assert (
            "평가 불가" in result.reasoning or "unavailable" in result.reasoning.lower()
        )

    @pytest.mark.asyncio
    async def test_evaluate_handles_llm_error_gracefully(self):
        """LLM 에러 시 기본값 반환"""
        from app.modules.core.evaluation.internal_evaluator import InternalEvaluator

        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(side_effect=Exception("API Error"))

        evaluator = InternalEvaluator(llm_client=mock_client)

        result = await evaluator.evaluate(
            query="테스트 질문",
            answer="테스트 답변",
            context=["컨텍스트"],
        )

        assert result.overall == 0.5

    @pytest.mark.asyncio
    async def test_evaluate_parses_json_with_code_block(self):
        """```json``` 코드 블록 내의 JSON 파싱"""
        from app.modules.core.evaluation.internal_evaluator import InternalEvaluator

        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(
            return_value='''
        평가 결과입니다:

        ```json
        {
            "faithfulness": 0.95,
            "relevance": 0.90,
            "reasoning": "매우 우수한 답변입니다."
        }
        ```
        '''
        )

        evaluator = InternalEvaluator(llm_client=mock_client)

        result = await evaluator.evaluate(
            query="질문",
            answer="답변",
            context=["컨텍스트"],
        )

        assert result.faithfulness == 0.95
        assert result.relevance == 0.90

    @pytest.mark.asyncio
    async def test_evaluate_parses_json_with_plain_code_block(self):
        """``` ``` 코드 블록 내의 JSON 파싱"""
        from app.modules.core.evaluation.internal_evaluator import InternalEvaluator

        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(
            return_value='''
        ```
        {
            "faithfulness": 0.85,
            "relevance": 0.80,
            "reasoning": "좋은 답변입니다."
        }
        ```
        '''
        )

        evaluator = InternalEvaluator(llm_client=mock_client)

        result = await evaluator.evaluate(
            query="질문",
            answer="답변",
            context=["컨텍스트"],
        )

        assert result.faithfulness == 0.85
        assert result.relevance == 0.80

    @pytest.mark.asyncio
    async def test_evaluate_handles_invalid_json_gracefully(self):
        """잘못된 JSON 응답 시 기본값 반환"""
        from app.modules.core.evaluation.internal_evaluator import InternalEvaluator

        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value="이건 JSON이 아닙니다.")

        evaluator = InternalEvaluator(llm_client=mock_client)

        result = await evaluator.evaluate(
            query="질문",
            answer="답변",
            context=["컨텍스트"],
        )

        assert result.overall == 0.5
        assert "파싱 실패" in result.reasoning

    @pytest.mark.asyncio
    async def test_evaluate_stores_raw_scores(self):
        """raw_scores에 원본 점수 저장 확인"""
        from app.modules.core.evaluation.internal_evaluator import InternalEvaluator

        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(
            return_value='''
        {
            "faithfulness": 0.9,
            "relevance": 0.85,
            "reasoning": "테스트",
            "extra_field": "extra_value"
        }
        '''
        )

        evaluator = InternalEvaluator(llm_client=mock_client)

        result = await evaluator.evaluate(
            query="질문",
            answer="답변",
            context=["컨텍스트"],
        )

        assert "faithfulness" in result.raw_scores
        assert "relevance" in result.raw_scores
        assert result.raw_scores.get("extra_field") == "extra_value"

    @pytest.mark.asyncio
    async def test_evaluate_with_reference(self):
        """reference 파라미터와 함께 평가"""
        from app.modules.core.evaluation.internal_evaluator import InternalEvaluator

        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(
            return_value='''
        {
            "faithfulness": 0.9,
            "relevance": 0.85,
            "reasoning": "테스트"
        }
        '''
        )

        evaluator = InternalEvaluator(llm_client=mock_client)

        # reference 파라미터가 있어도 정상 동작
        result = await evaluator.evaluate(
            query="질문",
            answer="답변",
            context=["컨텍스트"],
            reference="참조 답변",
        )

        assert result.faithfulness == 0.9


class TestInternalEvaluatorBatchEvaluate:
    """InternalEvaluator.batch_evaluate() 테스트"""

    @pytest.mark.asyncio
    async def test_batch_evaluate_returns_list(self):
        """batch_evaluate()가 결과 리스트 반환"""
        from app.modules.core.evaluation.internal_evaluator import InternalEvaluator

        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(
            return_value='''
        {"faithfulness": 0.9, "relevance": 0.85, "reasoning": "Good"}
        '''
        )

        evaluator = InternalEvaluator(llm_client=mock_client)

        samples = [
            {"query": "질문1", "answer": "답변1", "context": ["ctx1"]},
            {"query": "질문2", "answer": "답변2", "context": ["ctx2"]},
        ]

        results = await evaluator.batch_evaluate(samples)

        assert len(results) == 2
        assert all(r.overall >= 0.0 for r in results)

    @pytest.mark.asyncio
    async def test_batch_evaluate_empty_list(self):
        """빈 리스트 평가 시 빈 결과 반환"""
        from app.modules.core.evaluation.internal_evaluator import InternalEvaluator

        mock_client = AsyncMock()
        evaluator = InternalEvaluator(llm_client=mock_client)

        results = await evaluator.batch_evaluate([])

        assert results == []

    @pytest.mark.asyncio
    async def test_batch_evaluate_with_reference(self):
        """reference가 포함된 샘플 배치 평가"""
        from app.modules.core.evaluation.internal_evaluator import InternalEvaluator

        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(
            return_value='''
        {"faithfulness": 0.9, "relevance": 0.85, "reasoning": "Good"}
        '''
        )

        evaluator = InternalEvaluator(llm_client=mock_client)

        samples = [
            {
                "query": "질문1",
                "answer": "답변1",
                "context": ["ctx1"],
                "reference": "참조1",
            },
        ]

        results = await evaluator.batch_evaluate(samples)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_batch_evaluate_handles_partial_failure(self):
        """일부 평가 실패 시에도 전체 결과 반환"""
        from app.modules.core.evaluation.internal_evaluator import InternalEvaluator

        mock_client = AsyncMock()
        # 첫 번째 호출은 성공, 두 번째는 실패, 세 번째는 성공
        mock_client.generate = AsyncMock(
            side_effect=[
                '{"faithfulness": 0.9, "relevance": 0.85, "reasoning": "Good"}',
                Exception("API Error"),
                '{"faithfulness": 0.8, "relevance": 0.75, "reasoning": "OK"}',
            ]
        )

        evaluator = InternalEvaluator(llm_client=mock_client)

        samples = [
            {"query": "질문1", "answer": "답변1", "context": ["ctx1"]},
            {"query": "질문2", "answer": "답변2", "context": ["ctx2"]},
            {"query": "질문3", "answer": "답변3", "context": ["ctx3"]},
        ]

        results = await evaluator.batch_evaluate(samples)

        assert len(results) == 3
        # 첫 번째는 성공적으로 평가됨
        assert results[0].faithfulness == 0.9
        # 두 번째는 기본값
        assert results[1].overall == 0.5
        # 세 번째는 성공적으로 평가됨
        assert results[2].faithfulness == 0.8


class TestInternalEvaluatorPromptBuilding:
    """InternalEvaluator._build_prompt() 테스트"""

    def test_build_prompt_includes_query(self):
        """프롬프트에 질문 포함 확인"""
        from app.modules.core.evaluation.internal_evaluator import InternalEvaluator

        mock_client = MagicMock()
        evaluator = InternalEvaluator(llm_client=mock_client)

        prompt = evaluator._build_prompt(
            query="테스트 질문입니다",
            answer="테스트 답변",
            context=["컨텍스트"],
        )

        assert "테스트 질문입니다" in prompt

    def test_build_prompt_includes_answer(self):
        """프롬프트에 답변 포함 확인"""
        from app.modules.core.evaluation.internal_evaluator import InternalEvaluator

        mock_client = MagicMock()
        evaluator = InternalEvaluator(llm_client=mock_client)

        prompt = evaluator._build_prompt(
            query="질문",
            answer="테스트 답변입니다",
            context=["컨텍스트"],
        )

        assert "테스트 답변입니다" in prompt

    def test_build_prompt_includes_context(self):
        """프롬프트에 컨텍스트 포함 확인"""
        from app.modules.core.evaluation.internal_evaluator import InternalEvaluator

        mock_client = MagicMock()
        evaluator = InternalEvaluator(llm_client=mock_client)

        prompt = evaluator._build_prompt(
            query="질문",
            answer="답변",
            context=["첫 번째 컨텍스트", "두 번째 컨텍스트"],
        )

        assert "첫 번째 컨텍스트" in prompt
        assert "두 번째 컨텍스트" in prompt

    def test_build_prompt_includes_evaluation_criteria(self):
        """프롬프트에 평가 기준 포함 확인"""
        from app.modules.core.evaluation.internal_evaluator import InternalEvaluator

        mock_client = MagicMock()
        evaluator = InternalEvaluator(llm_client=mock_client)

        prompt = evaluator._build_prompt(
            query="질문",
            answer="답변",
            context=["컨텍스트"],
        )

        assert "faithfulness" in prompt
        assert "relevance" in prompt
