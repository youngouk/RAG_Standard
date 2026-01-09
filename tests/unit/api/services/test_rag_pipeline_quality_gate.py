"""
Self-RAG 품질 게이트 테스트

TDD 방식으로 저품질 답변 거부 로직을 검증합니다.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.services.rag_pipeline import RAGPipeline
from app.modules.core.generation.generator import GenerationResult
from app.modules.core.self_rag.evaluator import QualityScore
from app.modules.core.self_rag.orchestrator import SelfRAGResult


@pytest.mark.unit
class TestRAGPipelineQualityGate:
    """Self-RAG 품질 게이트 테스트"""

    @pytest.fixture
    def config_with_quality_gate(self):
        """품질 게이트 활성화 설정"""
        return {
            "self_rag": {
                "enabled": True,
                "min_quality_to_answer": 0.6,  # 최소 품질 임계값
                "quality_threshold": 0.8,
            }
        }

    @pytest.fixture
    def mock_self_rag_module(self):
        """Self-RAG 모듈 Mock"""
        module = AsyncMock()
        return module

    @pytest.mark.asyncio
    async def test_low_quality_answer_rejected(
        self, config_with_quality_gate, mock_self_rag_module
    ):
        """
        저품질 답변 거부 테스트

        Given: 품질 점수 0.5 (임계값 0.6 미만)
        When: self_rag_verify() 호출
        Then: "확실한 정보를 찾지 못했습니다" 거부 메시지 반환
        """
        # Mock Self-RAG 결과 (저품질)
        mock_self_rag_module.verify_existing_answer.return_value = SelfRAGResult(
            answer="부정확한 답변",
            used_self_rag=True,
            regenerated=False,
            complexity=MagicMock(score=0.7),
            initial_quality=QualityScore(
                relevance=0.6,
                grounding=0.4,
                completeness=0.5,
                confidence=0.5,
                overall=0.5,  # 임계값 미만
                reasoning="답변이 문서 근거 부족",
                raw_response={},
            ),
            final_quality=QualityScore(
                relevance=0.6,
                grounding=0.4,
                completeness=0.5,
                confidence=0.5,
                overall=0.5,
                reasoning="재생성 없음",
                raw_response={},
            ),
            processing_time=1.0,
            tokens_used=100,
        )

        # RAGPipeline 인스턴스 생성
        pipeline = RAGPipeline(
            config=config_with_quality_gate,
            query_router=MagicMock(),
            query_expansion=AsyncMock(),
            retrieval_module=AsyncMock(),
            generation_module=AsyncMock(),
            session_module=AsyncMock(),
            self_rag_module=mock_self_rag_module,
            extract_topic_func=MagicMock(),
            circuit_breaker_factory=MagicMock(),
            cost_tracker=MagicMock(),
            performance_metrics=MagicMock(),
        )

        # 기존 답변
        generation_result = GenerationResult(
            answer="부정확한 답변",
            text="부정확한 답변",
            tokens_used=100,
            model_used="test-model",
            provider="test",
            generation_time=1.0,
        )

        # Self-RAG 검증 실행
        result = await pipeline.self_rag_verify(
            message="서울 맛집 추천",
            session_id="test-session",
            generation_result=generation_result,
            documents=[],
            options={},
        )

        # 검증: 거부 메시지 반환
        assert "확실한 정보를 찾지 못했습니다" in result.answer
        assert result.refusal_reason == "quality_too_low"
        assert result.quality_score == 0.5

    @pytest.mark.asyncio
    async def test_high_quality_answer_accepted(
        self, config_with_quality_gate, mock_self_rag_module
    ):
        """
        고품질 답변 통과 테스트

        Given: 품질 점수 0.87 (임계값 0.6 이상)
        When: self_rag_verify() 호출
        Then: 원본 답변 그대로 반환
        """
        # Mock Self-RAG 결과 (고품질)
        mock_self_rag_module.verify_existing_answer.return_value = SelfRAGResult(
            answer="강남 맛집 3곳을 추천드립니다...",
            used_self_rag=True,
            regenerated=False,
            complexity=MagicMock(score=0.7),
            initial_quality=QualityScore(
                relevance=0.85,
                grounding=0.9,
                completeness=0.88,
                confidence=0.85,
                overall=0.87,  # 임계값 이상
                reasoning="답변이 문서 기반 정확",
                raw_response={},
            ),
            final_quality=QualityScore(
                relevance=0.85,
                grounding=0.9,
                completeness=0.88,
                confidence=0.85,
                overall=0.87,
                reasoning="재생성 없음",
                raw_response={},
            ),
            processing_time=1.0,
            tokens_used=150,
        )

        pipeline = RAGPipeline(
            config=config_with_quality_gate,
            query_router=MagicMock(),
            query_expansion=AsyncMock(),
            retrieval_module=AsyncMock(),
            generation_module=AsyncMock(),
            session_module=AsyncMock(),
            self_rag_module=mock_self_rag_module,
            extract_topic_func=MagicMock(),
            circuit_breaker_factory=MagicMock(),
            cost_tracker=MagicMock(),
            performance_metrics=MagicMock(),
        )

        generation_result = GenerationResult(
            answer="강남 맛집 3곳을 추천드립니다...",
            text="강남 맛집 3곳을 추천드립니다...",
            tokens_used=150,
            model_used="test-model",
            provider="test",
            generation_time=1.0,
        )

        # Self-RAG 검증 실행
        result = await pipeline.self_rag_verify(
            message="강남 맛집 추천",
            session_id="test-session",
            generation_result=generation_result,
            documents=[],
            options={},
        )

        # 검증: 원본 답변 유지
        assert result.answer == "강남 맛집 3곳을 추천드립니다..."
        assert not hasattr(result, "refusal_reason") or result.refusal_reason is None
        assert result.quality_score == 0.87

    @pytest.mark.asyncio
    async def test_quality_score_exactly_at_threshold(
        self, config_with_quality_gate, mock_self_rag_module
    ):
        """
        경계값 테스트: 품질 점수 정확히 0.6

        Given: 품질 점수 = 0.6 (임계값)
        When: self_rag_verify() 호출
        Then: 답변 통과 (>= 조건이므로 0.6은 통과)
        """
        # Mock Self-RAG 결과 (경계값)
        mock_self_rag_module.verify_existing_answer.return_value = SelfRAGResult(
            answer="경계값 테스트 답변",
            used_self_rag=True,
            regenerated=False,
            complexity=MagicMock(score=0.7),
            initial_quality=QualityScore(
                relevance=0.6,
                grounding=0.6,
                completeness=0.6,
                confidence=0.6,
                overall=0.6,  # 정확히 임계값
                reasoning="경계값 테스트",
                raw_response={},
            ),
            final_quality=QualityScore(
                relevance=0.6,
                grounding=0.6,
                completeness=0.6,
                confidence=0.6,
                overall=0.6,
                reasoning="경계값",
                raw_response={},
            ),
            processing_time=1.0,
            tokens_used=100,
        )

        pipeline = RAGPipeline(
            config=config_with_quality_gate,
            query_router=MagicMock(),
            query_expansion=AsyncMock(),
            retrieval_module=AsyncMock(),
            generation_module=AsyncMock(),
            session_module=AsyncMock(),
            self_rag_module=mock_self_rag_module,
            extract_topic_func=MagicMock(),
            circuit_breaker_factory=MagicMock(),
            cost_tracker=MagicMock(),
            performance_metrics=MagicMock(),
        )

        generation_result = GenerationResult(
            answer="경계값 테스트 답변",
            text="경계값 테스트 답변",
            tokens_used=100,
            model_used="test-model",
            provider="test",
            generation_time=1.0,
        )

        result = await pipeline.self_rag_verify(
            message="경계값 테스트",
            session_id="test-session",
            generation_result=generation_result,
            documents=[],
            options={},
        )

        # 검증: 0.6은 >= 조건이므로 통과해야 함
        assert result.answer == "경계값 테스트 답변"
        assert not hasattr(result, "refusal_reason") or result.refusal_reason is None
        assert result.quality_score == 0.6

    @pytest.mark.asyncio
    async def test_quality_score_just_below_threshold(
        self, config_with_quality_gate, mock_self_rag_module
    ):
        """
        경계값 테스트: 품질 점수 0.59999 (임계값 직전)

        Given: 품질 점수 = 0.59999 (임계값 미만)
        When: self_rag_verify() 호출
        Then: 답변 거부
        """
        mock_self_rag_module.verify_existing_answer.return_value = SelfRAGResult(
            answer="경계값 직전 테스트",
            used_self_rag=True,
            regenerated=False,
            complexity=MagicMock(score=0.7),
            initial_quality=QualityScore(
                relevance=0.59999,
                grounding=0.59999,
                completeness=0.59999,
                confidence=0.59999,
                overall=0.59999,  # 임계값 직전
                reasoning="경계값 직전",
                raw_response={},
            ),
            final_quality=QualityScore(
                relevance=0.59999,
                grounding=0.59999,
                completeness=0.59999,
                confidence=0.59999,
                overall=0.59999,
                reasoning="경계값 직전",
                raw_response={},
            ),
            processing_time=1.0,
            tokens_used=100,
        )

        pipeline = RAGPipeline(
            config=config_with_quality_gate,
            query_router=MagicMock(),
            query_expansion=AsyncMock(),
            retrieval_module=AsyncMock(),
            generation_module=AsyncMock(),
            session_module=AsyncMock(),
            self_rag_module=mock_self_rag_module,
            extract_topic_func=MagicMock(),
            circuit_breaker_factory=MagicMock(),
            cost_tracker=MagicMock(),
            performance_metrics=MagicMock(),
        )

        generation_result = GenerationResult(
            answer="경계값 직전 테스트",
            text="경계값 직전 테스트",
            tokens_used=100,
            model_used="test-model",
            provider="test",
            generation_time=1.0,
        )

        result = await pipeline.self_rag_verify(
            message="경계값 직전 테스트",
            session_id="test-session",
            generation_result=generation_result,
            documents=[],
            options={},
        )

        # 검증: 0.59999 < 0.6 이므로 거부되어야 함
        assert "확실한 정보를 찾지 못했습니다" in result.answer
        assert result.refusal_reason == "quality_too_low"
        assert result.quality_score == 0.59999

    @pytest.mark.asyncio
    async def test_quality_score_none_handling(
        self, config_with_quality_gate, mock_self_rag_module
    ):
        """
        None 처리 테스트

        Given: Self-RAG 평가 실패로 final_quality=None
        When: self_rag_verify() 호출
        Then: 품질 점수 0.0으로 폴백 → 거부
        """
        mock_self_rag_module.verify_existing_answer.return_value = SelfRAGResult(
            answer="평가 실패 테스트",
            used_self_rag=True,
            regenerated=False,
            complexity=MagicMock(score=0.7),
            initial_quality=None,  # 평가 실패
            final_quality=None,  # 평가 실패
            processing_time=1.0,
            tokens_used=100,
        )

        pipeline = RAGPipeline(
            config=config_with_quality_gate,
            query_router=MagicMock(),
            query_expansion=AsyncMock(),
            retrieval_module=AsyncMock(),
            generation_module=AsyncMock(),
            session_module=AsyncMock(),
            self_rag_module=mock_self_rag_module,
            extract_topic_func=MagicMock(),
            circuit_breaker_factory=MagicMock(),
            cost_tracker=MagicMock(),
            performance_metrics=MagicMock(),
        )

        generation_result = GenerationResult(
            answer="평가 실패 테스트",
            text="평가 실패 테스트",
            tokens_used=100,
            model_used="test-model",
            provider="test",
            generation_time=1.0,
        )

        result = await pipeline.self_rag_verify(
            message="None 처리 테스트",
            session_id="test-session",
            generation_result=generation_result,
            documents=[],
            options={},
        )

        # 검증: None은 0.0으로 폴백 → 거부
        assert "확실한 정보를 찾지 못했습니다" in result.answer
        assert result.refusal_reason == "quality_too_low"

    @pytest.mark.asyncio
    async def test_quality_gate_disabled(self, mock_self_rag_module):
        """
        품질 게이트 비활성화 시 테스트

        Given: self_rag.enabled=False
        When: self_rag_verify() 호출
        Then: 원본 답변 그대로 반환 (검증 스킵)
        """
        config_disabled = {
            "self_rag": {
                "enabled": False,
            }
        }

        pipeline = RAGPipeline(
            config=config_disabled,
            query_router=MagicMock(),
            query_expansion=AsyncMock(),
            retrieval_module=AsyncMock(),
            generation_module=AsyncMock(),
            session_module=AsyncMock(),
            self_rag_module=mock_self_rag_module,
            extract_topic_func=MagicMock(),
            circuit_breaker_factory=MagicMock(),
            cost_tracker=MagicMock(),
            performance_metrics=MagicMock(),
        )

        generation_result = GenerationResult(
            answer="원본 답변",
            text="원본 답변",
            tokens_used=100,
            model_used="test-model",
            provider="test",
            generation_time=1.0,
        )

        # Self-RAG 검증 (스킵됨)
        result = await pipeline.self_rag_verify(
            message="테스트 질문",
            session_id="test-session",
            generation_result=generation_result,
            documents=[],
            options={},
        )

        # 검증: 원본 답변 유지, Self-RAG 미호출
        assert result.answer == "원본 답변"
        mock_self_rag_module.verify_existing_answer.assert_not_called()
