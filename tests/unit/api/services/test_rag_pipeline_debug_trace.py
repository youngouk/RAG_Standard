"""
RAGPipeline 디버깅 추적 테스트

Task 4: RAGPipeline에서 enable_debug_trace 파라미터를 추가하고
각 단계별 디버깅 정보를 수집하는 테스트
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.schemas.debug import DebugTrace
from app.api.services.rag_pipeline import RAGPipeline


@pytest.mark.unit
class TestRAGPipelineDebugTrace:
    """RAGPipeline 디버깅 추적 테스트"""

    @pytest.mark.asyncio
    async def test_debug_trace_collected_during_pipeline(self):
        """
        파이프라인 실행 중 디버깅 추적 정보 수집

        Given: RAGPipeline 실행
        When: execute() 호출 시 enable_debug_trace=True
        Then: debug_trace 객체에 모든 단계 정보 수집됨
        """
        # Mock 의존성
        config = {
            "self_rag": {"enabled": True},
            "query_expansion": {"enabled": True},
            "rag": {"top_k": 8, "rerank_top_k": 8},
            "retrieval": {"min_score": 0.05},
            "reranking": {"enabled": True},
        }

        # Mock 모듈들
        query_router = MagicMock()
        query_router.enabled = False

        query_expansion = AsyncMock()
        query_expansion.expand_query = AsyncMock(return_value=MagicMock(
            expansions=["강남 맛집 추천", "서울 강남구 음식점"],
            metadata={"raw_expanded_queries": [
                {"query": "강남 맛집 추천", "weight": 1.0},
                {"query": "서울 강남구 음식점", "weight": 0.8},
            ]}
        ))

        # Mock IMultiQueryRetriever protocol
        from app.modules.core.retrieval.interfaces import IMultiQueryRetriever

        retrieval_module = AsyncMock(spec=IMultiQueryRetriever)
        retrieval_module._search_and_merge = AsyncMock(return_value=[
            MagicMock(
                page_content="강남역 근처 맛집...",
                metadata={
                    "id": "doc-123",
                    "title": "강남 맛집 TOP 10",
                    "score": 0.92,
                    "bm25_score": 0.78,
                }
            )
        ])
        retrieval_module.rerank = AsyncMock(return_value=[
            MagicMock(
                page_content="강남역 근처 맛집...",
                metadata={
                    "id": "doc-123",
                    "title": "강남 맛집 TOP 10",
                    "score": 0.92,
                    "bm25_score": 0.78,
                    "rerank_score": 0.95,
                }
            )
        ])

        generation_module = AsyncMock()
        generation_module.generate_answer = AsyncMock(return_value=MagicMock(
            answer="강남 맛집 추천드립니다.",
            tokens_used=100,
            model_used="gemini-flash",
            provider="google",
            generation_time=1.5,
            model_info={"provider": "google", "model": "gemini-flash"},
        ))

        session_module = AsyncMock()
        session_module.get_context_string = AsyncMock(return_value=None)

        self_rag_module = AsyncMock()
        self_rag_module.verify_existing_answer = AsyncMock(return_value=MagicMock(
            used_self_rag=True,
            regenerated=True,
            answer="강남 맛집 재생성 답변",
            tokens_used=120,
            complexity=MagicMock(score=0.85),
            initial_quality=MagicMock(overall=0.73, reasoning="초기 품질 낮음"),
            final_quality=MagicMock(overall=0.89),
        ))

        async def circuit_breaker_call(func, fallback):
            """Circuit breaker mock that actually awaits async functions"""
            return await func()

        circuit_breaker_factory = MagicMock()
        circuit_breaker_factory.get = MagicMock(return_value=MagicMock(
            call=AsyncMock(side_effect=circuit_breaker_call)
        ))

        cost_tracker = MagicMock()
        performance_metrics = MagicMock()
        extract_topic_func = MagicMock(return_value="맛집")

        pipeline = RAGPipeline(
            config=config,
            query_router=query_router,
            query_expansion=query_expansion,
            retrieval_module=retrieval_module,
            generation_module=generation_module,
            session_module=session_module,
            self_rag_module=self_rag_module,
            extract_topic_func=extract_topic_func,
            circuit_breaker_factory=circuit_breaker_factory,
            cost_tracker=cost_tracker,
            performance_metrics=performance_metrics,
        )

        # 파이프라인 실행 (debug_trace 활성화)
        result = await pipeline.execute(
            message="강남 맛집 추천",
            session_id="test-session",
            options={"enable_debug_trace": True},  # ⭐ 디버깅 추적 활성화
        )

        # 검증: debug_trace 존재
        assert "debug_trace" in result
        assert result["debug_trace"] is not None

        trace = result["debug_trace"]
        assert isinstance(trace, DebugTrace)

        # 검증: 쿼리 변환 정보
        assert trace.query_transformation.original == "강남 맛집 추천"
        # expanded는 원본과 동일하면 None (쿼리 확장 없음)
        assert trace.query_transformation.final_query == "강남 맛집 추천"

        # 검증: 검색 문서 정보
        assert len(trace.retrieved_documents) > 0
        assert trace.retrieved_documents[0].vector_score >= 0.0
        assert trace.retrieved_documents[0].id == "doc-123"

        # 검증: Self-RAG 평가 정보
        assert trace.self_rag_evaluation is not None
        assert trace.self_rag_evaluation.initial_quality >= 0.0
        assert trace.self_rag_evaluation.regenerated is True
        assert trace.self_rag_evaluation.final_quality >= 0.0

    @pytest.mark.asyncio
    async def test_debug_trace_disabled_by_default(self):
        """
        디버깅 추적 기본 비활성화

        Given: enable_debug_trace=False (기본값)
        When: execute() 호출
        Then: debug_trace 필드 없음 (성능 최적화)
        """
        config = {
            "self_rag": {"enabled": False},
            "rag": {"top_k": 8, "rerank_top_k": 8},
            "retrieval": {"min_score": 0.05},
            "reranking": {"enabled": False},
        }

        query_router = MagicMock()
        query_router.enabled = False

        query_expansion = None

        from app.modules.core.retrieval.interfaces import IMultiQueryRetriever

        retrieval_module = AsyncMock(spec=IMultiQueryRetriever)
        retrieval_module._search_and_merge = AsyncMock(return_value=[
            MagicMock(
                page_content="테스트 문서",
                metadata={"id": "doc-1", "score": 0.8}
            )
        ])
        retrieval_module.rerank = AsyncMock(return_value=[
            MagicMock(
                page_content="테스트 문서",
                metadata={"id": "doc-1", "score": 0.8}
            )
        ])

        generation_module = AsyncMock()
        generation_module.generate_answer = AsyncMock(return_value=MagicMock(
            answer="테스트 답변",
            tokens_used=50,
            model_used="gemini-flash",
            provider="google",
            generation_time=1.0,
            model_info={"provider": "google", "model": "gemini-flash"},
        ))

        session_module = AsyncMock()
        session_module.get_context_string = AsyncMock(return_value=None)

        self_rag_module = None

        async def circuit_breaker_call(func, fallback):
            """Circuit breaker mock that actually awaits async functions"""
            return await func()

        circuit_breaker_factory = MagicMock()
        circuit_breaker_factory.get = MagicMock(return_value=MagicMock(
            call=AsyncMock(side_effect=circuit_breaker_call)
        ))

        cost_tracker = MagicMock()
        performance_metrics = MagicMock()
        extract_topic_func = MagicMock(return_value="테스트")

        pipeline = RAGPipeline(
            config=config,
            query_router=query_router,
            query_expansion=query_expansion,
            retrieval_module=retrieval_module,
            generation_module=generation_module,
            session_module=session_module,
            self_rag_module=self_rag_module,
            extract_topic_func=extract_topic_func,
            circuit_breaker_factory=circuit_breaker_factory,
            cost_tracker=cost_tracker,
            performance_metrics=performance_metrics,
        )

        # 파이프라인 실행 (enable_debug_trace 미지정 = 기본값 False)
        result = await pipeline.execute(
            message="테스트 질문",
            session_id="test-session",
            options={},  # enable_debug_trace 미지정
        )

        # 검증: debug_trace 없음
        assert "debug_trace" not in result or result.get("debug_trace") is None

    @pytest.mark.asyncio
    async def test_debug_trace_query_expansion_disabled(self):
        """
        쿼리 확장 비활성화 시 디버깅 추적

        Given: query_expansion=None (비활성화)
        When: enable_debug_trace=True
        Then: expanded=None, final_query=original
        """
        config = {
            "self_rag": {"enabled": False},
            "rag": {"top_k": 8, "rerank_top_k": 8},
            "retrieval": {"min_score": 0.05},
        }

        query_router = MagicMock()
        query_router.enabled = False

        query_expansion = None  # 쿼리 확장 비활성화

        from app.modules.core.retrieval.interfaces import IMultiQueryRetriever

        retrieval_module = AsyncMock(spec=IMultiQueryRetriever)
        retrieval_module._search_and_merge = AsyncMock(return_value=[
            MagicMock(
                page_content="문서 내용",
                metadata={"id": "doc-1", "score": 0.9}
            )
        ])

        generation_module = AsyncMock()
        generation_module.generate_answer = AsyncMock(return_value=MagicMock(
            answer="답변",
            tokens_used=30,
            model_used="gemini-flash",
            provider="google",
            generation_time=0.5,
            model_info={"provider": "google", "model": "gemini-flash"},
        ))

        session_module = AsyncMock()
        session_module.get_context_string = AsyncMock(return_value=None)

        async def circuit_breaker_call(func, fallback):
            """Circuit breaker mock that actually awaits async functions"""
            return await func()

        circuit_breaker_factory = MagicMock()
        circuit_breaker_factory.get = MagicMock(return_value=MagicMock(
            call=AsyncMock(side_effect=circuit_breaker_call)
        ))

        cost_tracker = MagicMock()
        performance_metrics = MagicMock()
        extract_topic_func = MagicMock(return_value="테스트")

        pipeline = RAGPipeline(
            config=config,
            query_router=query_router,
            query_expansion=query_expansion,
            retrieval_module=retrieval_module,
            generation_module=generation_module,
            session_module=session_module,
            self_rag_module=None,
            extract_topic_func=extract_topic_func,
            circuit_breaker_factory=circuit_breaker_factory,
            cost_tracker=cost_tracker,
            performance_metrics=performance_metrics,
        )

        result = await pipeline.execute(
            message="원본 쿼리",
            session_id="test-session",
            options={"enable_debug_trace": True},
        )

        assert "debug_trace" in result
        trace = result["debug_trace"]

        # 쿼리 확장 비활성화 → expanded=None
        assert trace.query_transformation.original == "원본 쿼리"
        assert trace.query_transformation.expanded is None
        assert trace.query_transformation.final_query == "원본 쿼리"

    @pytest.mark.asyncio
    async def test_debug_trace_self_rag_disabled(self):
        """
        Self-RAG 비활성화 시 디버깅 추적

        Given: self_rag.enabled=False
        When: enable_debug_trace=True
        Then: self_rag_evaluation=None
        """
        config = {
            "self_rag": {"enabled": False},
            "rag": {"top_k": 8, "rerank_top_k": 8},
            "retrieval": {"min_score": 0.05},
        }

        query_router = MagicMock()
        query_router.enabled = False

        from app.modules.core.retrieval.interfaces import IMultiQueryRetriever

        retrieval_module = AsyncMock(spec=IMultiQueryRetriever)
        retrieval_module._search_and_merge = AsyncMock(return_value=[
            MagicMock(
                page_content="문서",
                metadata={"id": "doc-1", "score": 0.85}
            )
        ])

        generation_module = AsyncMock()
        generation_module.generate_answer = AsyncMock(return_value=MagicMock(
            answer="답변",
            tokens_used=40,
            model_used="gemini-flash",
            provider="google",
            generation_time=0.8,
            model_info={"provider": "google", "model": "gemini-flash"},
        ))

        session_module = AsyncMock()
        session_module.get_context_string = AsyncMock(return_value=None)

        self_rag_module = None  # Self-RAG 비활성화

        async def circuit_breaker_call(func, fallback):
            """Circuit breaker mock that actually awaits async functions"""
            return await func()

        circuit_breaker_factory = MagicMock()
        circuit_breaker_factory.get = MagicMock(return_value=MagicMock(
            call=AsyncMock(side_effect=circuit_breaker_call)
        ))

        cost_tracker = MagicMock()
        performance_metrics = MagicMock()
        extract_topic_func = MagicMock(return_value="테스트")

        pipeline = RAGPipeline(
            config=config,
            query_router=query_router,
            query_expansion=None,
            retrieval_module=retrieval_module,
            generation_module=generation_module,
            session_module=session_module,
            self_rag_module=self_rag_module,
            extract_topic_func=extract_topic_func,
            circuit_breaker_factory=circuit_breaker_factory,
            cost_tracker=cost_tracker,
            performance_metrics=performance_metrics,
        )

        result = await pipeline.execute(
            message="질문",
            session_id="test-session",
            options={"enable_debug_trace": True},
        )

        assert "debug_trace" in result
        trace = result["debug_trace"]

        # Self-RAG 비활성화 → self_rag_evaluation=None
        assert trace.self_rag_evaluation is None
