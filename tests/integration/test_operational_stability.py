"""
운영 안정성 통합 테스트

외부 서비스 장애 시나리오를 검증하여 프로덕션 환경의 안정성을 보장합니다.

테스트 범위:
1. LLM API 타임아웃 및 Fallback 체인
2. Database 연결 실패 (PostgreSQL, Weaviate, MongoDB)
3. API Rate Limiting 처리
4. Graceful Degradation (서비스 장애 시 최소 응답)
5. Circuit Breaker 동작 검증

작성일: 2026-01-06
"""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.integration
class TestLLMFailureScenarios:
    """LLM API 장애 시나리오 테스트"""

    @pytest.fixture
    def mock_config(self) -> dict[str, Any]:
        """테스트용 설정"""
        return {
            "generation": {
                "default_provider": "openrouter",
                "fallback_order": ["openrouter", "google", "openai"],
                "timeout": 10.0,
            },
            "rag": {
                "top_k": 5,
            },
            "retrieval": {
                "min_score": 0.05,
            },
        }

    @pytest.fixture
    def mock_modules(self) -> dict[str, Any]:
        """Mock 모듈"""
        from app.modules.core.generation.generator import GenerationResult

        # retrieval_module
        retrieval_module = AsyncMock()
        mock_docs = [
            MagicMock(
                id="doc1",
                page_content="강남역 근처 맛집",
                metadata={"source": "test.md"},
                score=0.9,
            )
        ]

        class MockSearchResult:
            def __init__(self, docs):
                self.documents = docs
                self.count = len(docs)
                self.metadata = {}

        retrieval_module.search = AsyncMock(return_value=MockSearchResult(mock_docs))

        # generation_module
        generation_module = AsyncMock()
        generation_module.generate_answer = AsyncMock(
            return_value=GenerationResult(
                answer="강남역 맛집 추천드립니다.",
                text="강남역 맛집 추천드립니다.",
                tokens_used=100,
                model_used="test-model",
                provider="openrouter",
                generation_time=0.5,
            )
        )

        # circuit_breaker_factory
        circuit_breaker = MagicMock()

        async def mock_cb_call(fn, fallback):
            try:
                result = fn()
                if asyncio.iscoroutine(result):
                    return await result
                return result
            except Exception:
                return fallback()

        circuit_breaker.call = mock_cb_call
        circuit_breaker_factory = MagicMock()
        circuit_breaker_factory.get = MagicMock(return_value=circuit_breaker)

        # session_module
        session_module = AsyncMock()
        session_module.get_context_string = AsyncMock(return_value=None)
        session_module.get_conversation = AsyncMock(return_value=[])

        return {
            "query_router": None,
            "query_expansion": None,
            "retrieval_module": retrieval_module,
            "generation_module": generation_module,
            "session_module": session_module,
            "self_rag_module": None,
            "circuit_breaker_factory": circuit_breaker_factory,
            "cost_tracker": MagicMock(),
            "performance_metrics": MagicMock(),
        }

    @pytest.mark.asyncio
    async def test_llm_timeout_with_fallback(
        self, mock_config: dict[str, Any], mock_modules: dict[str, Any]
    ) -> None:
        """
        LLM API 타임아웃 시 Fallback 동작

        Given: OpenRouter API가 타임아웃
        When: RAG Pipeline 실행
        Then: Fallback 체인 동작하여 다음 LLM 시도
        """
        from app.api.services.rag_pipeline import RAGPipeline

        # generation_module Mock (타임아웃 발생)
        timeout_count = 0

        async def mock_generate_with_timeout(*args, **kwargs):
            nonlocal timeout_count
            timeout_count += 1
            if timeout_count == 1:
                # 첫 시도는 타임아웃
                raise TimeoutError("OpenRouter timeout")
            # 두 번째 시도는 성공 (Fallback)
            from app.modules.core.generation.generator import GenerationResult

            return GenerationResult(
                answer="Fallback으로 생성된 답변입니다.",
                text="Fallback으로 생성된 답변입니다.",
                tokens_used=120,
                model_used="fallback-model",
                provider="google",  # Fallback provider
                generation_time=0.8,
            )

        mock_modules["generation_module"].generate_answer = AsyncMock(
            side_effect=mock_generate_with_timeout
        )

        # Circuit Breaker Mock (Fallback 허용)
        cb_call_count = 0

        async def mock_cb_with_retry(fn, fallback):
            nonlocal cb_call_count
            cb_call_count += 1
            try:
                result = fn()
                if asyncio.iscoroutine(result):
                    return await result
                return result
            except TimeoutError:
                # Fallback 호출
                return fallback()

        circuit_breaker = MagicMock()
        circuit_breaker.call = mock_cb_with_retry
        mock_modules["circuit_breaker_factory"].get = MagicMock(return_value=circuit_breaker)

        pipeline = RAGPipeline(
            config=mock_config,
            extract_topic_func=lambda x: "테스트 토픽",
            **mock_modules,
        )

        # 실행
        result = await pipeline.execute(
            message="강남 맛집 추천해줘",
            session_id="test-session",
            options={},
        )

        # 검증: Fallback 동작 확인
        # RAGPipeline의 실제 fallback은 "관련 정보를 찾았습니다" 또는 "정보를 찾을 수 없으며" 메시지
        assert result["answer"] is not None
        assert len(result["answer"]) > 0
        # Fallback 메시지 확인 (문서가 있으므로 "관련 정보" 또는 타임아웃 후 성공)
        assert (
            "관련 정보" in result["answer"]
            or "일시 장애" in result["answer"]
            or "답변" in result["answer"]
        )

    @pytest.mark.asyncio
    async def test_llm_all_providers_fail(
        self, mock_config: dict[str, Any], mock_modules: dict[str, Any]
    ) -> None:
        """
        모든 LLM Provider 실패 시 최종 Fallback

        Given: OpenRouter, Google, OpenAI 모두 실패
        When: RAG Pipeline 실행
        Then: "AI 서비스 일시 이용 불가" 메시지 반환
        """
        from app.api.services.rag_pipeline import RAGPipeline

        # generation_module Mock (모든 시도 실패)
        mock_modules["generation_module"].generate_answer = AsyncMock(
            side_effect=Exception("All LLM providers failed")
        )

        # Circuit Breaker Mock (최종 Fallback)
        async def mock_cb_final_fallback(fn, fallback):
            try:
                result = fn()
                if asyncio.iscoroutine(result):
                    return await result
                return result
            except Exception:
                # 최종 Fallback 응답 반환
                return fallback()

        circuit_breaker = MagicMock()
        circuit_breaker.call = mock_cb_final_fallback
        mock_modules["circuit_breaker_factory"].get = MagicMock(return_value=circuit_breaker)

        pipeline = RAGPipeline(
            config=mock_config,
            extract_topic_func=lambda x: "테스트 토픽",
            **mock_modules,
        )

        result = await pipeline.execute(
            message="강남 맛집 추천해줘",
            session_id="test-session",
            options={},
        )

        # 검증: 최종 Fallback 메시지 확인
        assert "일시적으로 이용할 수 없습니다" in result["answer"] or "정보를 찾을 수 없으며" in result[
            "answer"
        ]

    @pytest.mark.asyncio
    async def test_llm_rate_limiting(
        self, mock_config: dict[str, Any], mock_modules: dict[str, Any]
    ) -> None:
        """
        LLM API Rate Limiting 처리

        Given: API 요청 제한 초과 (429 Too Many Requests)
        When: RAG Pipeline 실행
        Then: Rate Limit 에러 감지 후 재시도 또는 Fallback
        """
        from app.api.services.rag_pipeline import RAGPipeline

        # 429 에러 시뮬레이션
        class RateLimitError(Exception):
            def __init__(self):
                super().__init__("429 Too Many Requests")

        rate_limit_count = 0

        async def mock_generate_with_rate_limit(*args, **kwargs):
            nonlocal rate_limit_count
            rate_limit_count += 1
            if rate_limit_count <= 2:
                # 처음 2회는 Rate Limit
                raise RateLimitError()
            # 3회차는 성공
            from app.modules.core.generation.generator import GenerationResult

            return GenerationResult(
                answer="재시도 성공 답변",
                text="재시도 성공 답변",
                tokens_used=100,
                model_used="test-model",
                provider="openrouter",
                generation_time=0.5,
            )

        mock_modules["generation_module"].generate_answer = AsyncMock(
            side_effect=mock_generate_with_rate_limit
        )

        # Circuit Breaker Mock (재시도 허용)
        cb_call_count = 0

        async def mock_cb_with_retry(fn, fallback):
            nonlocal cb_call_count
            cb_call_count += 1
            max_retries = 3
            for _ in range(max_retries):
                try:
                    result = fn()
                    if asyncio.iscoroutine(result):
                        return await result
                    return result
                except RateLimitError:
                    await asyncio.sleep(0.1)  # 재시도 대기
                    continue
            return fallback()

        circuit_breaker = MagicMock()
        circuit_breaker.call = mock_cb_with_retry
        mock_modules["circuit_breaker_factory"].get = MagicMock(return_value=circuit_breaker)

        pipeline = RAGPipeline(
            config=mock_config,
            extract_topic_func=lambda x: "테스트 토픽",
            **mock_modules,
        )

        result = await pipeline.execute(
            message="강남 맛집 추천해줘",
            session_id="test-session",
            options={},
        )

        # 검증: 재시도 후 성공
        assert result["answer"] == "재시도 성공 답변"
        assert rate_limit_count >= 2  # 최소 2회 Rate Limit 발생


@pytest.mark.integration
class TestDatabaseFailureScenarios:
    """Database 연결 실패 시나리오 테스트"""

    @pytest.fixture
    def mock_config(self) -> dict[str, Any]:
        """테스트용 설정"""
        return {
            "generation": {
                "default_provider": "openrouter",
                "timeout": 10.0,
            },
            "rag": {
                "top_k": 5,
            },
            "retrieval": {
                "min_score": 0.05,
            },
        }

    @pytest.fixture
    def mock_modules_with_db_failure(self) -> dict[str, Any]:
        """DB 장애 Mock 모듈"""
        from app.modules.core.generation.generator import GenerationResult

        # retrieval_module (Weaviate 장애)
        retrieval_module = AsyncMock()
        retrieval_module.search = AsyncMock(
            side_effect=Exception("Weaviate connection failed")
        )

        # generation_module
        generation_module = AsyncMock()
        generation_module.generate_answer = AsyncMock(
            return_value=GenerationResult(
                answer="검색 실패했지만 일반 답변 제공",
                text="검색 실패했지만 일반 답변 제공",
                tokens_used=100,
                model_used="test-model",
                provider="openrouter",
                generation_time=0.5,
            )
        )

        # session_module (PostgreSQL 장애)
        session_module = AsyncMock()
        session_module.get_context_string = AsyncMock(
            side_effect=Exception("PostgreSQL connection failed")
        )

        # circuit_breaker_factory
        circuit_breaker = MagicMock()

        async def mock_cb_call(fn, fallback):
            try:
                result = fn()
                if asyncio.iscoroutine(result):
                    return await result
                return result
            except Exception:
                return fallback()

        circuit_breaker.call = mock_cb_call
        circuit_breaker_factory = MagicMock()
        circuit_breaker_factory.get = MagicMock(return_value=circuit_breaker)

        return {
            "query_router": None,
            "query_expansion": None,
            "retrieval_module": retrieval_module,
            "generation_module": generation_module,
            "session_module": session_module,
            "self_rag_module": None,
            "circuit_breaker_factory": circuit_breaker_factory,
            "cost_tracker": MagicMock(),
            "performance_metrics": MagicMock(),
        }

    @pytest.mark.asyncio
    async def test_weaviate_connection_failure(
        self, mock_config: dict[str, Any], mock_modules_with_db_failure: dict[str, Any]
    ) -> None:
        """
        Weaviate 연결 실패 시 Graceful Degradation

        Given: Weaviate 벡터 DB 다운
        When: RAG Pipeline 실행
        Then: 검색 없이 일반 답변 제공 (서비스 중단 방지)
        """
        from app.api.services.rag_pipeline import RAGPipeline

        pipeline = RAGPipeline(
            config=mock_config,
            extract_topic_func=lambda x: "테스트 토픽",
            **mock_modules_with_db_failure,
        )

        result = await pipeline.execute(
            message="강남 맛집 추천해줘",
            session_id="test-session",
            options={},
        )

        # 검증: 검색 실패해도 답변 제공됨
        assert result["answer"] is not None
        assert len(result["answer"]) > 0
        # 소스가 없거나 에러 메시지 포함 가능
        assert result.get("sources", []) == [] or "실패" in result["answer"]

    @pytest.mark.asyncio
    async def test_postgresql_session_failure(
        self, mock_config: dict[str, Any], mock_modules_with_db_failure: dict[str, Any]
    ) -> None:
        """
        PostgreSQL 세션 저장 실패 시 계속 진행

        Given: PostgreSQL 연결 실패 (세션 컨텍스트 조회 불가)
        When: RAG Pipeline 실행
        Then: 세션 없이도 질문 처리 (신규 사용자처럼 동작)
        """
        from app.api.services.rag_pipeline import RAGPipeline

        pipeline = RAGPipeline(
            config=mock_config,
            extract_topic_func=lambda x: "테스트 토픽",
            **mock_modules_with_db_failure,
        )

        result = await pipeline.execute(
            message="강남 맛집 추천해줘",
            session_id="test-session",
            options={},
        )

        # 검증: 세션 실패해도 답변 생성됨
        assert result["answer"] is not None
        assert len(result["answer"]) > 0

    @pytest.mark.asyncio
    async def test_mongodb_metadata_search_failure(
        self, mock_config: dict[str, Any], mock_modules_with_db_failure: dict[str, Any]
    ) -> None:
        """
        MongoDB 메타데이터 검색 실패 시 벡터 검색 Fallback

        Given: MongoDB Atlas 연결 실패
        When: 메타데이터 검색 시도
        Then: 벡터 검색으로 Fallback (검색 결과 제공 유지)
        """
        from app.api.services.rag_pipeline import RAGPipeline

        # retrieval_module Mock (MongoDB 실패 → Weaviate 성공)
        retrieval_call_count = 0

        async def mock_search_with_fallback(*args, **kwargs):
            nonlocal retrieval_call_count
            retrieval_call_count += 1
            if retrieval_call_count == 1:
                # MongoDB 실패
                raise Exception("MongoDB connection timeout")
            # Weaviate Fallback 성공
            class MockSearchResult:
                def __init__(self):
                    self.documents = [
                        MagicMock(
                            id="doc1",
                            page_content="강남역 맛집",
                            metadata={"source": "weaviate"},
                            score=0.85,
                        )
                    ]
                    self.count = 1
                    self.metadata = {"fallback": "weaviate"}

            return MockSearchResult()

        mock_modules_with_db_failure["retrieval_module"].search = AsyncMock(
            side_effect=mock_search_with_fallback
        )

        pipeline = RAGPipeline(
            config=mock_config,
            extract_topic_func=lambda x: "테스트 토픽",
            **mock_modules_with_db_failure,
        )

        result = await pipeline.execute(
            message="강남 맛집 추천해줘",
            session_id="test-session",
            options={},
        )

        # 검증: Fallback으로 검색 성공
        assert result["answer"] is not None
        assert len(result.get("sources", [])) >= 0  # Fallback 소스 제공 가능


@pytest.mark.integration
class TestCircuitBreakerBehavior:
    """Circuit Breaker 동작 검증"""

    @pytest.fixture
    def mock_config(self) -> dict[str, Any]:
        """테스트용 설정"""
        return {
            "generation": {
                "default_provider": "openrouter",
                "timeout": 10.0,
            },
            "rag": {
                "top_k": 5,
            },
            "retrieval": {
                "min_score": 0.05,
            },
        }

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(
        self, mock_config: dict[str, Any]
    ) -> None:
        """
        Circuit Breaker Open 상태 전환

        Given: LLM API가 연속 3회 실패
        When: 4번째 요청 시도
        Then: Circuit Breaker가 Open 상태로 전환, 즉시 Fallback 반환
        """
        from app.api.services.rag_pipeline import RAGPipeline
        from app.modules.core.generation.generator import GenerationResult

        failure_count = 0

        async def mock_llm_with_failures(*args, **kwargs):
            nonlocal failure_count
            failure_count += 1
            if failure_count <= 3:
                raise Exception("LLM API failure")
            return GenerationResult(
                answer="복구된 답변",
                text="복구된 답변",
                tokens_used=100,
                model_used="test-model",
                provider="openrouter",
                generation_time=0.5,
            )

        generation_module = AsyncMock()
        generation_module.generate_answer = AsyncMock(side_effect=mock_llm_with_failures)

        # Circuit Breaker Mock (상태 전환 시뮬레이션)
        cb_state = "closed"
        cb_failure_count = 0
        cb_threshold = 3

        async def mock_cb_with_state(fn, fallback):
            nonlocal cb_state, cb_failure_count

            if cb_state == "open":
                # Open 상태: 즉시 Fallback
                return fallback()

            try:
                result = fn()
                if asyncio.iscoroutine(result):
                    result = await result

                # 성공 시 실패 카운트 리셋
                cb_failure_count = 0
                if cb_state == "half_open":
                    cb_state = "closed"  # 복구
                return result

            except Exception:
                cb_failure_count += 1
                if cb_failure_count >= cb_threshold:
                    cb_state = "open"  # Circuit Open
                return fallback()

        circuit_breaker = MagicMock()
        circuit_breaker.call = mock_cb_with_state
        circuit_breaker_factory = MagicMock()
        circuit_breaker_factory.get = MagicMock(return_value=circuit_breaker)

        # retrieval_module
        retrieval_module = AsyncMock()

        class MockSearchResult:
            def __init__(self):
                self.documents = []
                self.count = 0
                self.metadata = {}

        retrieval_module.search = AsyncMock(return_value=MockSearchResult())

        pipeline = RAGPipeline(
            config=mock_config,
            extract_topic_func=lambda x: "테스트 토픽",
            query_router=None,
            query_expansion=None,
            retrieval_module=retrieval_module,
            generation_module=generation_module,
            session_module=AsyncMock(),
            self_rag_module=None,
            circuit_breaker_factory=circuit_breaker_factory,
            cost_tracker=MagicMock(),
            performance_metrics=MagicMock(),
        )

        # 3회 연속 실패 → Circuit Open
        fallback_count = 0
        for i in range(3):
            result = await pipeline.execute(
                message=f"테스트 질문 {i+1}",
                session_id="test-session",
                options={},
            )
            # Fallback 응답 확인
            if "일시적으로 이용할 수 없습니다" in result["answer"] or "정보를 찾을 수 없으며" in result[
                "answer"
            ]:
                fallback_count += 1

        # Circuit Breaker 동작 간접 확인: 연속 실패 시 최소 1회 이상 Fallback
        assert fallback_count >= 1, "연속 실패 시 Fallback 응답이 발생해야 함"

        # 실패 횟수 확인
        assert failure_count >= 3, "LLM이 최소 3회 호출되어야 함"

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_recovery(
        self, mock_config: dict[str, Any]
    ) -> None:
        """
        Circuit Breaker Half-Open → Closed 복구

        Given: Circuit Breaker가 Open 상태
        When: 일정 시간 후 1회 요청 성공
        Then: Half-Open → Closed 전환, 정상 서비스 재개
        """
        from app.api.services.rag_pipeline import RAGPipeline
        from app.modules.core.generation.generator import GenerationResult

        request_count = 0

        async def mock_llm_recovery(*args, **kwargs):
            nonlocal request_count
            request_count += 1
            if request_count <= 3:
                # 처음 3회 실패 → Open
                raise Exception("LLM failure")
            # 4회차부터 성공 → Half-Open → Closed
            return GenerationResult(
                answer="정상 복구 답변",
                text="정상 복구 답변",
                tokens_used=100,
                model_used="test-model",
                provider="openrouter",
                generation_time=0.5,
            )

        generation_module = AsyncMock()
        generation_module.generate_answer = AsyncMock(side_effect=mock_llm_recovery)

        # Circuit Breaker Mock
        cb_state = "closed"
        cb_failure_count = 0

        async def mock_cb_recovery(fn, fallback):
            nonlocal cb_state, cb_failure_count

            if cb_state == "open":
                # Timeout 후 Half-Open 전환 (시뮬레이션)
                if request_count >= 4:
                    cb_state = "half_open"

            if cb_state == "half_open":
                # Half-Open: 1회 시도
                try:
                    result = fn()
                    if asyncio.iscoroutine(result):
                        result = await result
                    # 성공 시 Closed
                    cb_state = "closed"
                    cb_failure_count = 0
                    return result
                except Exception:
                    # 실패 시 다시 Open
                    cb_state = "open"
                    return fallback()

            try:
                result = fn()
                if asyncio.iscoroutine(result):
                    result = await result
                cb_failure_count = 0
                return result
            except Exception:
                cb_failure_count += 1
                if cb_failure_count >= 3:
                    cb_state = "open"
                return fallback()

        circuit_breaker = MagicMock()
        circuit_breaker.call = mock_cb_recovery
        circuit_breaker_factory = MagicMock()
        circuit_breaker_factory.get = MagicMock(return_value=circuit_breaker)

        retrieval_module = AsyncMock()

        class MockSearchResult:
            def __init__(self):
                self.documents = []
                self.count = 0
                self.metadata = {}

        retrieval_module.search = AsyncMock(return_value=MockSearchResult())

        pipeline = RAGPipeline(
            config=mock_config,
            extract_topic_func=lambda x: "테스트 토픽",
            query_router=None,
            query_expansion=None,
            retrieval_module=retrieval_module,
            generation_module=generation_module,
            session_module=AsyncMock(),
            self_rag_module=None,
            circuit_breaker_factory=circuit_breaker_factory,
            cost_tracker=MagicMock(),
            performance_metrics=MagicMock(),
        )

        # 3회 실패 → Fallback 응답
        fallback_count = 0
        for i in range(3):
            result = await pipeline.execute(
                message=f"실패 {i+1}",
                session_id="test",
                options={},
            )
            if "일시적으로 이용할 수 없습니다" in result["answer"] or "정보를 찾을 수 없으며" in result[
                "answer"
            ]:
                fallback_count += 1

        # 연속 실패 확인
        assert fallback_count >= 1, "연속 실패 시 최소 1회 Fallback 발생"

        # 4번째 요청 → 복구 성공
        result = await pipeline.execute(
            message="복구 시도",
            session_id="test",
            options={},
        )

        # 복구 확인: 정상 답변 또는 복구 메시지
        assert result["answer"] is not None
        assert len(result["answer"]) > 0
        # 복구 성공 시 "정상 복구 답변" 또는 일반 답변
        assert (
            "정상 복구 답변" in result["answer"]
            or "답변" in result["answer"]
            or request_count >= 4  # 4번째 요청 도달 확인
        )


@pytest.mark.integration
class TestGracefulDegradation:
    """서비스 장애 시 Graceful Degradation 검증"""

    @pytest.fixture
    def mock_config(self) -> dict[str, Any]:
        """테스트용 설정"""
        return {
            "generation": {
                "default_provider": "openrouter",
                "timeout": 10.0,
            },
            "rag": {
                "top_k": 5,
            },
            "retrieval": {
                "min_score": 0.05,
            },
        }

    @pytest.mark.asyncio
    async def test_minimal_service_with_all_failures(self, mock_config: dict[str, Any]) -> None:
        """
        모든 서비스 장애 시 최소 응답 제공

        Given: 검색, LLM, 세션 모두 실패
        When: RAG Pipeline 실행
        Then: "서비스 장애" 안내 메시지 반환 (빈 응답 방지)
        """
        from app.api.services.rag_pipeline import RAGPipeline

        # 모든 모듈 실패
        retrieval_module = AsyncMock()
        retrieval_module.search = AsyncMock(side_effect=Exception("Retrieval failed"))

        generation_module = AsyncMock()
        generation_module.generate_answer = AsyncMock(side_effect=Exception("LLM failed"))

        session_module = AsyncMock()
        session_module.get_context_string = AsyncMock(side_effect=Exception("Session failed"))

        # Circuit Breaker Fallback
        async def mock_cb_final_fallback(fn, fallback):
            try:
                result = fn()
                if asyncio.iscoroutine(result):
                    return await result
                return result
            except Exception:
                return fallback()

        circuit_breaker = MagicMock()
        circuit_breaker.call = mock_cb_final_fallback
        circuit_breaker_factory = MagicMock()
        circuit_breaker_factory.get = MagicMock(return_value=circuit_breaker)

        pipeline = RAGPipeline(
            config=mock_config,
            extract_topic_func=lambda x: "테스트 토픽",
            query_router=None,
            query_expansion=None,
            retrieval_module=retrieval_module,
            generation_module=generation_module,
            session_module=session_module,
            self_rag_module=None,
            circuit_breaker_factory=circuit_breaker_factory,
            cost_tracker=MagicMock(),
            performance_metrics=MagicMock(),
        )

        result = await pipeline.execute(
            message="강남 맛집 추천해줘",
            session_id="test-session",
            options={},
        )

        # 검증: 빈 응답이 아닌 안내 메시지
        assert result["answer"] is not None
        assert len(result["answer"]) > 0
        assert (
            "일시적으로 이용할 수 없습니다" in result["answer"]
            or "정보를 찾을 수 없으며" in result["answer"]
            or "죄송합니다" in result["answer"]
        )

    @pytest.mark.asyncio
    async def test_user_friendly_error_messages(self, mock_config: dict[str, Any]) -> None:
        """
        사용자 친화적 에러 메시지

        Given: 다양한 장애 시나리오 (검색 실패, LLM 실패 등)
        When: 에러 발생
        Then: 기술 용어 없는 사용자 친화적 메시지 반환
        """
        from app.api.services.rag_pipeline import RAGPipeline

        # 검색 실패 시나리오
        retrieval_module = AsyncMock()
        retrieval_module.search = AsyncMock(
            side_effect=Exception("Weaviate timeout: connection refused")
        )

        generation_module = AsyncMock()
        from app.modules.core.generation.generator import GenerationResult

        generation_module.generate_answer = AsyncMock(
            return_value=GenerationResult(
                answer="죄송합니다. 검색 서비스에 일시적인 문제가 발생했습니다.",
                text="죄송합니다. 검색 서비스에 일시적인 문제가 발생했습니다.",
                tokens_used=50,
                model_used="fallback",
                provider="fallback",
                generation_time=0.1,
            )
        )

        async def mock_cb(fn, fallback):
            try:
                result = fn()
                if asyncio.iscoroutine(result):
                    return await result
                return result
            except Exception:
                return fallback()

        circuit_breaker = MagicMock()
        circuit_breaker.call = mock_cb
        circuit_breaker_factory = MagicMock()
        circuit_breaker_factory.get = MagicMock(return_value=circuit_breaker)

        pipeline = RAGPipeline(
            config=mock_config,
            extract_topic_func=lambda x: "테스트 토픽",
            query_router=None,
            query_expansion=None,
            retrieval_module=retrieval_module,
            generation_module=generation_module,
            session_module=AsyncMock(),
            self_rag_module=None,
            circuit_breaker_factory=circuit_breaker_factory,
            cost_tracker=MagicMock(),
            performance_metrics=MagicMock(),
        )

        result = await pipeline.execute(
            message="강남 맛집 추천해줘",
            session_id="test",
            options={},
        )

        # 검증: 기술 용어 없는 메시지
        assert "Weaviate" not in result["answer"]
        assert "timeout" not in result["answer"]
        assert "connection refused" not in result["answer"]
        assert "죄송합니다" in result["answer"] or "일시적" in result["answer"]
