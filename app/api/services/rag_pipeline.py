"""
RAG Pipeline 모듈

7개 독립 단계로 분해된 RAG 파이프라인 오케스트레이터.
각 단계는 독립적으로 테스트 및 최적화 가능.

단계:
1. route_query: 쿼리 라우팅 (규칙 기반 + LLM 폴백)
2. prepare_context: 세션 컨텍스트 + 쿼리 확장
3. retrieve_documents: MongoDB Atlas 하이브리드 검색
4. rerank_documents: 리랭킹 (선택적)
5. generate_answer: LLM 답변 생성
6. format_sources: Source 객체 변환
7. build_result: 최종 응답 구성

작성일: 2025-01-27
목적: TASK-H4 구현 - 150줄 블랙박스 함수 → 7개 독립 메서드
"""

import asyncio
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, cast

from ...lib.circuit_breaker import CircuitBreakerOpenError
from ...lib.cost_tracker import CostTracker
from ...lib.errors import ErrorCode, GenerationError, RetrievalError
from ...lib.langfuse_client import langfuse_context, observe  # Langfuse 트레이싱
from ...lib.logger import get_logger
from ...lib.metrics import PerformanceMetrics
from ...lib.prompt_sanitizer import contains_output_leakage, validate_document
from ...lib.score_normalizer import RRFScoreNormalizer  # RRF 점수 정규화
from ...lib.types import RAGResultDict
from ...modules.core.agent.interfaces import AgentResult
from ...modules.core.agent.orchestrator import AgentOrchestrator
from ...modules.core.generation.generator import GenerationResult
from ...modules.core.privacy.masker import PrivacyMasker
from ...modules.core.retrieval.interfaces import IMultiQueryRetriever, SearchResult
from ...modules.core.routing.rule_based_router import RuleBasedRouter
from ...modules.core.sql_search import SQLSearchResult, SQLSearchService
from ..schemas.debug import DebugTrace

logger = get_logger(__name__)


@dataclass
class RouteDecision:
    """
    쿼리 라우팅 결정 결과

    Attributes:
        should_continue: RAG 파이프라인 계속 진행 여부
        immediate_response: 즉시 응답 (direct_answer/blocked인 경우)
        metadata: 라우팅 메타데이터 (route, confidence, intent, domain 등)

    Examples:
        # 즉시 응답 (파이프라인 중단)
        RouteDecision(
            should_continue=False,
            immediate_response={"answer": "안녕하세요!", ...},
            metadata={"route": "direct_answer", "confidence": 0.95}
        )

        # RAG 계속 진행
        RouteDecision(
            should_continue=True,
            immediate_response=None,
            metadata={"route": "rag", "domain": "document_query"}
        )
    """

    should_continue: bool
    immediate_response: RAGResultDict | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PreparedContext:
    """
        세션 컨텍스트 + 쿼리 확장 결과 (Multi-Query RRF 지원)

        Attributes:
            session_context: 세션 컨텍스트 문자열 (최근 5개 대화)
            expanded_query: 확장된 쿼리 (첫 번째 쿼리, 하위 호환성)
            original_query: 원본 쿼리 (참조용)
            expanded_queries: 확장된 쿼리 리스트 (Multi-Query RRF용, 기본 5개)
            query_weights: 쿼리 가중치 리스트 (1.0, 0.8, 0.6, 0.4, 0.2)

        Examples:
            # Multi-Query RRF
            PreparedContext(
                session_context="사용자: 안녕하세요
    봇: 안녕하세요! 무엇을 도와드릴까요?",
                expanded_query="부산시 주민등록 발급 방법 및 필요 서류",
                original_query="주민등록 발급",
                expanded_queries=["부산시 주민등록 발급 방법", "주민등록등본 신청", ...],
                query_weights=[1.0, 0.8, 0.6, 0.4, 0.2]
            )
    """

    session_context: str | None
    expanded_query: str
    original_query: str
    expanded_queries: list[str] = field(default_factory=list)  # Multi-Query RRF용
    query_weights: list[float] = field(default_factory=list)  # 쿼리 가중치


@dataclass
class RetrievalResults:
    """
    문서 검색 결과

    Attributes:
        documents: Document 객체 리스트 (langchain_core.documents.Document)
        count: 검색된 문서 수

    Examples:
        RetrievalResults(
            documents=[
                Document(page_content="...", metadata={"source": "doc1.pdf", "score": 0.89}),
                Document(page_content="...", metadata={"source": "doc2.pdf", "score": 0.76})
            ],
            count=2
        )
    """

    documents: list[Any]
    count: int


@dataclass
class RerankResults:
    """
    리랭킹 결과

    Attributes:
        documents: 리랭킹된 Document 객체 리스트
        count: 리랭킹된 문서 수
        reranked: 실제로 리랭킹이 수행되었는지 여부

    Examples:
        # 리랭킹 성공
        RerankResults(documents=[...], count=10, reranked=True)

        # 리랭킹 실패 (원본 반환)
        RerankResults(documents=[...], count=15, reranked=False)
    """

    documents: list[Any]
    count: int
    reranked: bool


# GenerationResult는 generator.py에서 import (L30)


@dataclass
class FormattedSources:
    """
    포맷팅된 소스 리스트

    Attributes:
        sources: Source 객체 리스트 (app.models.prompts.Source)
        count: 소스 개수

    Examples:
        FormattedSources(
            sources=[Source(id=0, document="doc1.pdf", relevance=0.89, ...), ...],
            count=5
        )
    """

    sources: list[Any]
    count: int


class PipelineTracker:
    """
    RAG 파이프라인 단계별 타이밍 추적 클래스

    8개 단계 각각의 실행 시간을 기록하고, 병목 지점을 식별.

    사용법:
        tracker = PipelineTracker()
        tracker.start_pipeline()

        tracker.start_stage("route_query")
        # ... 작업 수행 ...
        tracker.end_stage("route_query")

        tracker.end_pipeline()
        metrics = tracker.get_metrics()

    메트릭 형식:
        {
            'total_duration_ms': 1250.5,
            'stages': {
                'route_query': {'duration_ms': 45.2, 'percentage': 3.6},
                'retrieve_documents': {'duration_ms': 823.1, 'percentage': 65.8},
                ...
            },
            'slowest_stage': 'retrieve_documents'
        }
    """

    def __init__(self):
        """PipelineTracker 초기화"""
        self.stages: dict[str, dict[str, Any]] = {}  # Multi-Query RRF 메타데이터를 위해 Any 허용
        self.start_time: float = 0.0
        self.end_time: float = 0.0

    def start_pipeline(self) -> None:
        """파이프라인 시작 시간 기록"""
        self.start_time = time.time()
        logger.debug("Pipeline tracking 시작")

    def start_stage(self, stage_name: str) -> None:
        """
        단계 시작 시간 기록

        Args:
            stage_name: 단계 이름 (예: "route_query", "retrieve_documents")
        """
        if stage_name not in self.stages:
            self.stages[stage_name] = {}
        self.stages[stage_name]["start"] = time.time()

    def end_stage(self, stage_name: str) -> None:
        """
        단계 종료 시간 기록 및 duration 계산

        Args:
            stage_name: 단계 이름
        """
        if stage_name in self.stages and "start" in self.stages[stage_name]:
            self.stages[stage_name]["end"] = time.time()
            self.stages[stage_name]["duration"] = (
                self.stages[stage_name]["end"] - self.stages[stage_name]["start"]
            )
        else:
            logger.warning(
                "Stage가 시작되지 않았거나 이미 종료됨",
                extra={"stage_name": stage_name}
            )

    def end_pipeline(self) -> None:
        """파이프라인 종료 시간 기록"""
        self.end_time = time.time()
        logger.debug("Pipeline tracking 종료")

    def get_metrics(self) -> dict[str, Any]:
        """
        성능 메트릭 반환

        Returns:
            메트릭 딕셔너리:
            - total_duration_ms: 전체 실행 시간 (밀리초)
            - stages: 각 단계별 실행 시간 및 비율
            - slowest_stage: 가장 느린 단계 이름
        """
        total_duration = self.end_time - self.start_time if self.end_time > 0 else 0
        stage_metrics = {}
        for stage, times in self.stages.items():
            duration = times.get("duration", 0)
            percentage = duration / total_duration * 100 if total_duration > 0 else 0
            stage_metrics[stage] = {
                "duration_ms": round(duration * 1000, 1),
                "percentage": round(percentage, 1),
            }
        slowest_stage = None
        if self.stages:
            slowest_stage = max(self.stages.items(), key=lambda x: x[1].get("duration", 0))[0]
        return {
            "total_duration_ms": round(total_duration * 1000, 1),
            "stages": stage_metrics,
            "slowest_stage": slowest_stage,
        }

    def log_summary(self) -> None:
        """성능 메트릭 요약 로그 출력"""
        metrics = self.get_metrics()
        logger.info("=" * 60)
        logger.info("Pipeline Performance Summary")
        logger.info(
            "총 실행 시간",
            extra={"total_duration_ms": metrics['total_duration_ms']}
        )
        logger.info(
            "가장 느린 단계",
            extra={"slowest_stage": metrics.get('slowest_stage', 'N/A')}
        )
        logger.info("-" * 60)
        for stage, data in metrics["stages"].items():
            logger.info(
                "단계별 성능",
                extra={
                    "stage": stage,
                    "duration_ms": data['duration_ms'],
                    "percentage": data['percentage']
                }
            )
        logger.info("=" * 60)


class RAGPipeline:
    """
    RAG 파이프라인 오케스트레이터

    8개 독립 단계로 분해된 파이프라인:
    1. route_query: 쿼리 라우팅
    2. prepare_context: 컨텍스트 준비
    3. retrieve_documents: 문서 검색
    4. rerank_documents: 리랭킹
    5. generate_answer: 답변 생성
    6. self_rag_verify: Self-RAG 품질 검증 (선택적)
    7. format_sources: 소스 포맷팅
    8. build_result: 결과 구성

    각 단계는 독립적으로 테스트 및 최적화 가능.
    """

    # 기본값 (YAML 설정이 없을 때만 사용)
    FALLBACK_RETRIEVAL_LIMIT = 8
    FALLBACK_MIN_SCORE = 0.05
    FALLBACK_RERANK_TOP_N = 8

    def __init__(
        self,
        config: dict[str, Any],
        query_router: Any | None,
        query_expansion: Any | None,
        retrieval_module: Any,
        generation_module: Any,
        session_module: Any,
        self_rag_module: Any | None,
        extract_topic_func: Callable,
        circuit_breaker_factory: Any,
        cost_tracker: CostTracker,
        performance_metrics: PerformanceMetrics,
        sql_search_service: SQLSearchService | None = None,
        agent_orchestrator: AgentOrchestrator | None = None,
    ):
        """
        RAGPipeline 초기화 (의존성 주입)

        Args:
            config: 설정 딕셔너리
            query_router: 쿼리 라우터 (선택적)
            query_expansion: 쿼리 확장 모듈 (선택적)
            retrieval_module: 검색 모듈 (필수)
            generation_module: 생성 모듈 (필수)
            session_module: 세션 모듈 (필수)
            self_rag_module: Self-RAG 모듈 (선택적)
            extract_topic_func: 토픽 추출 함수
            circuit_breaker_factory: Circuit Breaker Factory (필수)
            cost_tracker: 비용 추적기 (필수)
            performance_metrics: 성능 메트릭 (필수)
            sql_search_service: SQL 검색 서비스 (선택적, Phase 3)
            agent_orchestrator: Agent 오케스트레이터 (선택적, Agentic RAG)
        """
        self.config = config
        self.query_router = query_router
        self.query_expansion = query_expansion
        self.retrieval_module = retrieval_module
        self.generation_module = generation_module
        self.session_module = session_module
        self.self_rag_module = self_rag_module
        self.extract_topic_func = extract_topic_func
        self.circuit_breaker_factory = circuit_breaker_factory
        self.cost_tracker = cost_tracker
        self.performance_metrics = performance_metrics
        self.sql_search_service = sql_search_service  # SQL 검색 서비스 (Phase 3)
        self.agent_orchestrator = agent_orchestrator  # Agent 오케스트레이터 (Agentic RAG)

        # YAML 설정에서 retrieval 파라미터 로드
        rag_config = config.get("rag", {})
        retrieval_config = config.get("retrieval", {})

        self.retrieval_limit = rag_config.get(
            "top_k", retrieval_config.get("top_k", self.FALLBACK_RETRIEVAL_LIMIT)
        )
        self.min_score = retrieval_config.get("min_score", self.FALLBACK_MIN_SCORE)
        self.rerank_top_n = rag_config.get("rerank_top_k", self.FALLBACK_RERANK_TOP_N)

        # RRF 점수 정규화 (0~1 범위 변환)
        score_norm_config = rag_config.get("score_normalization", {})
        self.score_normalizer = RRFScoreNormalizer.from_config(score_norm_config)

        # 개인정보 마스킹 (파일명, 답변 텍스트)
        # privacy.yaml 화이트리스트 로드 (오탐 방지: 이모님, 헬퍼님, 담당 등)
        # privacy.enabled: false → 마스킹 완전 비활성화
        privacy_config = config.get("privacy", {})
        privacy_enabled = privacy_config.get("enabled", True)

        if privacy_enabled:
            whitelist = privacy_config.get("whitelist", [])
            masking_config = privacy_config.get("masking", {})
            char_config = privacy_config.get("characters", {})

            self.privacy_masker = PrivacyMasker(
                mask_phone=masking_config.get("phone", True),
                mask_name=masking_config.get("name", True),
                mask_email=masking_config.get("email", False),
                phone_mask_char=char_config.get("phone", "*"),
                name_mask_char=char_config.get("name", "*"),
                whitelist=whitelist,  # 공용 화이트리스트 (privacy.yaml)
            )
        else:
            self.privacy_masker = None  # PII 마스킹 비활성화
            logger.info(
                "PII 마스킹 비활성화",
                extra={"config_key": "privacy.enabled", "value": False}
            )

        logger.info(
            "RAG 파라미터 설정",
            extra={
                "top_k": self.retrieval_limit,
                "rerank_top_k": self.rerank_top_n,
                "min_score": self.min_score
            }
        )

        from ..schemas.chat_schemas import Source

        self.Source = Source
        logger.info(
            "RAGPipeline 초기화 완료",
            extra={
                "sql_search": "활성화" if sql_search_service else "비활성화",
                "agent": "활성화" if agent_orchestrator else "비활성화",
                "score_normalization": "활성화" if score_norm_config.get('enabled', True) else "비활성화"
            }
        )

    def _create_fallback_response(
        self, message: str, start_time: float, routing_metadata: dict[str, Any]
    ) -> RAGResultDict:
        """라우팅 실패 시 기본 응답 생성"""
        processing_time = time.time() - start_time
        return cast(
            RAGResultDict,
            {
                "answer": "응답을 생성할 수 없습니다.",
                "sources": [],
                "tokens_used": 0,
                "topic": self.extract_topic_func(message),
                "processing_time": processing_time,
                "search_results": 0,
                "ranked_results": 0,
                "model_info": {"provider": "system", "model": "fallback"},
                "routing_metadata": routing_metadata,
            },
        )

    async def _execute_parallel_search(
        self,
        message: str,
        prepared_context: PreparedContext,
        options: dict[str, Any],
    ) -> tuple[RetrievalResults, SQLSearchResult | None]:
        """SQL + RAG 병렬 검색 실행"""
        if self.sql_search_service and self.sql_search_service.is_enabled():
            logger.info("SQL 검색 + RAG 검색 병렬 실행 시작")
            rag_task = self.retrieve_documents(
                prepared_context.expanded_queries,
                prepared_context.query_weights,
                prepared_context.session_context,
                options,
            )
            sql_task = self._execute_sql_search(message)

            rag_result, sql_result = await asyncio.gather(
                rag_task, sql_task, return_exceptions=True
            )

            if isinstance(rag_result, Exception):
                logger.error("RAG 검색 실패", extra={"error": str(rag_result)}, exc_info=True)
                raise rag_result
            retrieval_results = rag_result

            sql_search_result = None
            if isinstance(sql_result, Exception):
                logger.warning(
                    "SQL 검색 실패 (무시)",
                    extra={"error": str(sql_result)},
                    exc_info=True
                )
            else:
                sql_search_result = sql_result
                if sql_search_result and sql_search_result.used:
                    row_count = sql_search_result.query_result.row_count if sql_search_result.query_result else 0
                    logger.info(
                        "SQL 검색 성공",
                        extra={
                            "row_count": row_count,
                            "total_time": sql_search_result.total_time
                        }
                    )

            return retrieval_results, sql_search_result
        else:
            retrieval_results = await self.retrieve_documents(
                prepared_context.expanded_queries,
                prepared_context.query_weights,
                prepared_context.session_context,
                options,
            )
            return retrieval_results, None

    def _track_debug_documents(
        self, enable_debug_trace: bool, debug_trace_data: dict[str, Any], documents: list[Any]
    ) -> None:
        """디버그 추적용 문서 정보 기록"""
        if not enable_debug_trace:
            return

        debug_trace_data["retrieved_documents"] = [
            {
                "id": doc.metadata.get("id", "") if hasattr(doc, "metadata") else "",
                "title": doc.metadata.get("title", "") if hasattr(doc, "metadata") else "",
                "chunk_text": (getattr(doc, "page_content", "")[:200] if hasattr(doc, "page_content") else ""),
                "vector_score": doc.metadata.get("score", 0.0) if hasattr(doc, "metadata") else 0.0,
                "bm25_score": doc.metadata.get("bm25_score") if hasattr(doc, "metadata") else None,
                "rerank_score": None,
                "used_in_answer": False,
            }
            for doc in documents
        ]

    def _update_retrieval_metrics(
        self,
        tracker: PipelineTracker,
        prepared_context: PreparedContext,
        sql_search_result: SQLSearchResult | None,
    ) -> None:
        """검색 메트릭 업데이트"""
        tracker.stages["retrieve_documents"]["multi_query_count"] = len(
            prepared_context.expanded_queries
        )
        tracker.stages["retrieve_documents"]["rrf_enabled"] = (
            len(prepared_context.expanded_queries) > 1
        )
        tracker.stages["retrieve_documents"]["query_weights"] = prepared_context.query_weights
        tracker.stages["retrieve_documents"]["sql_search_used"] = (
            sql_search_result.used if sql_search_result else False
        )

    def _create_debug_trace(
        self,
        enable_debug_trace: bool,
        debug_trace_data: dict[str, Any],
        message: str,
    ) -> DebugTrace | None:
        """DebugTrace 객체 생성"""
        if not enable_debug_trace or not debug_trace_data:
            return None

        try:
            if "query_transformation" not in debug_trace_data:
                debug_trace_data["query_transformation"] = {
                    "original": message,
                    "expanded": None,
                    "final_query": message,
                }
            if "retrieved_documents" not in debug_trace_data:
                debug_trace_data["retrieved_documents"] = []

            debug_trace = DebugTrace(**debug_trace_data)
            logger.debug(
                "DebugTrace 생성 완료",
                extra={"document_count": len(debug_trace.retrieved_documents)}
            )
            return debug_trace
        except Exception as e:
            logger.warning(
                "DebugTrace 생성 실패",
                extra={"error": str(e)},
                exc_info=True
            )
            return None

    @observe(name="RAG Pipeline", capture_input=True, capture_output=True)
    async def execute(
        self, message: str, session_id: str, options: dict[str, Any] | None = None
    ) -> RAGResultDict:
        """
        전체 RAG 파이프라인 실행 (7단계 오케스트레이션)

        Args:
            message: 사용자 쿼리
            session_id: 세션 ID
            options: 추가 옵션 (limit, min_score, top_n, enable_debug_trace 등)

        Returns:
            표준 응답 딕셔너리

        Raises:
            RoutingError: 라우팅 실패 시
            RetrievalError: 검색 실패 시
            GenerationError: 답변 생성 실패 시
        """
        start_time = time.time()
        options = options or {}
        logger.info("RAG Pipeline 시작", extra={"query": message[:50]})

        enable_debug_trace = options.get("enable_debug_trace", False)
        debug_trace_data: dict[str, Any] = {} if enable_debug_trace else {}

        use_agent = options.get("use_agent", False)
        if use_agent and self.agent_orchestrator:
            logger.info("Agent 모드 활성화", extra={"orchestrator": "AgentOrchestrator"})
            return await self._execute_agent_mode(message, session_id, start_time)

        tracker = PipelineTracker()
        tracker.start_pipeline()
        tracker.start_stage("route_query")
        route_decision = await self.route_query(message, session_id, start_time)
        tracker.end_stage("route_query")

        if not route_decision.should_continue:
            logger.info("라우팅 결과: 즉시 응답 반환 (RAG 파이프라인 중단)")
            if route_decision.immediate_response is None:
                logger.error("immediate_response가 None입니다. 완전한 기본 응답 반환")
                return self._create_fallback_response(message, start_time, route_decision.metadata)
            return route_decision.immediate_response

        if enable_debug_trace:
            debug_trace_data["original_query"] = message

        tracker.start_stage("prepare_context")
        prepared_context = await self.prepare_context(message, session_id)
        tracker.end_stage("prepare_context")

        if enable_debug_trace:
            debug_trace_data["query_transformation"] = {
                "original": message,
                "expanded": prepared_context.expanded_query if prepared_context.expanded_query != message else None,
                "final_query": prepared_context.expanded_query,
            }

        tracker.start_stage("retrieve_documents")
        retrieval_results, sql_search_result = await self._execute_parallel_search(
            message, prepared_context, options
        )
        tracker.end_stage("retrieve_documents")

        self._track_debug_documents(enable_debug_trace, debug_trace_data, retrieval_results.documents)
        self._update_retrieval_metrics(tracker, prepared_context, sql_search_result)

        tracker.start_stage("rerank_documents")
        rerank_results = await self.rerank_documents(
            prepared_context.expanded_query, retrieval_results.documents, options
        )
        tracker.end_stage("rerank_documents")

        if enable_debug_trace and rerank_results.reranked:
            for i, doc in enumerate(rerank_results.documents):
                if i < len(debug_trace_data["retrieved_documents"]):
                    rerank_score = doc.metadata.get("rerank_score", 0.0) if hasattr(doc, "metadata") else 0.0
                    debug_trace_data["retrieved_documents"][i]["rerank_score"] = rerank_score

        tracker.start_stage("generate_answer")
        generation_options = {**options}
        if sql_search_result and sql_search_result.used:
            generation_options["sql_context"] = sql_search_result.formatted_context
            logger.debug(
                "SQL 컨텍스트 전달",
                extra={"context_length": len(sql_search_result.formatted_context)}
            )
        generation_result = await self.generate_answer(
            message, rerank_results.documents, prepared_context.session_context, generation_options
        )
        tracker.end_stage("generate_answer")

        tracker.start_stage("self_rag_verify")
        options_with_debug = {**options}
        if enable_debug_trace:
            options_with_debug["_debug_trace_data"] = debug_trace_data
        generation_result = await self.self_rag_verify(
            message, session_id, generation_result, rerank_results.documents, options_with_debug
        )
        tracker.end_stage("self_rag_verify")

        tracker.start_stage("format_sources")
        formatted_sources = self.format_sources(rerank_results.documents, sql_search_result)
        tracker.end_stage("format_sources")

        tracker.start_stage("build_result")
        debug_trace = self._create_debug_trace(enable_debug_trace, debug_trace_data, message)
        result = self.build_result(
            answer=generation_result.answer,
            sources=formatted_sources.sources,
            tokens_used=generation_result.tokens_used,
            topic=self.extract_topic_func(message),
            processing_time=time.time() - start_time,
            search_count=retrieval_results.count,
            ranked_count=rerank_results.count,
            model_info=generation_result.model_info,
            routing_metadata=route_decision.metadata,
            debug_trace=debug_trace,
        )
        tracker.end_stage("build_result")
        tracker.end_pipeline()
        performance_metrics = tracker.get_metrics()
        tracker.log_summary()
        result["performance_metrics"] = performance_metrics
        logger.info(
            "RAG Pipeline 완료",
            extra={"processing_time": result['processing_time']}
        )
        return result

    async def route_query(self, message: str, session_id: str, start_time: float) -> RouteDecision:
        """
        1단계: 쿼리 라우팅 (규칙 기반 + LLM 폴백)

        - 규칙 기반 라우터 우선 시도 (YAML 규칙)
        - LLM 라우터 폴백 (규칙 실패 시)
        - direct_answer/blocked 처리

        Args:
            message: 사용자 쿼리
            session_id: 세션 ID
            start_time: 파이프라인 시작 시간

        Returns:
            RouteDecision: 라우팅 결정 (계속 진행 여부 + 즉시 응답)

        Raises:
            RoutingError: 라우팅 실패 시
        """
        logger.debug("[1단계] 쿼리 라우팅 시작")
        routing_metadata = {}
        session_context = None
        if self.session_module:
            try:
                conversation = await self.session_module.get_conversation(
                    session_id, max_exchanges=5
                )
                if conversation and isinstance(conversation, list):
                    session_context = "\n".join(
                        [
                            f"User: {ex.get('user', '')}\nAssistant: {ex.get('assistant', '')}"
                            for ex in conversation
                        ]
                    )
            except Exception as e:
                logger.warning(
                    "세션 컨텍스트 조회 실패",
                    extra={"error": str(e)},
                    exc_info=True
                )
        try:
            rule_router = RuleBasedRouter(enabled=True)
            rule_match = await rule_router.check_rules(message)
            if rule_match:
                routing_metadata = {
                    "route": rule_match.route,
                    "intent": rule_match.intent,
                    "domain": rule_match.domain,
                    "confidence": rule_match.confidence,
                    "source": "rule_based",
                    "rule_name": rule_match.rule_name,
                }
                logger.info(
                    "[규칙 기반 라우터] 매칭",
                    extra={
                        "rule_name": rule_match.rule_name,
                        "route": rule_match.route,
                        "domain": rule_match.domain
                    }
                )
                if rule_match.route == "direct_answer" and rule_match.direct_answer:
                    processing_time = time.time() - start_time
                    immediate_response = {
                        "answer": rule_match.direct_answer,
                        "sources": [],
                        "tokens_used": 0,
                        "topic": self.extract_topic_func(message),
                        "processing_time": processing_time,
                        "search_count": 0,
                        "ranked_count": 0,
                        "model_info": {"provider": "rule_based", "model": "N/A"},
                        "routing_metadata": routing_metadata,
                    }

                    logger.info(
                        "[즉시 응답] 규칙 기반 답변 반환",
                        extra={"processing_time": processing_time}
                    )
                    return RouteDecision(
                        should_continue=False,
                        immediate_response=cast(RAGResultDict, immediate_response),
                        metadata=routing_metadata,
                    )
                return RouteDecision(
                    should_continue=True, immediate_response=None, metadata=routing_metadata
                )
        except Exception as rule_error:
            logger.warning(
                "[RuleBasedRouter] 오류",
                extra={"error": str(rule_error)},
                exc_info=True
            )
        if not self.query_router or not self.query_router.enabled:
            logger.info("[LLM 라우터] 비활성화 - RAG 계속 진행")
            return RouteDecision(
                should_continue=True, immediate_response=None, metadata=routing_metadata
            )
        try:
            profile, routing = await self.query_router.analyze_and_route(
                message, session_context=session_context
            )

            # 🆕 dataclass 속성 접근으로 수정 (Oracle 권장사항)
            routing_metadata.update(
                {
                    "llm_route": routing.primary_route,  # ✅ .get() → 속성 접근
                    "llm_intent": profile.intent.value if profile.intent else "unknown",  # ✅
                    "llm_domain": profile.domain,  # ✅
                    "llm_confidence": routing.confidence,  # ✅
                    "llm_reasoning": routing.notes or "",  # ✅
                    "data_source": getattr(profile, "data_source", "general"),  # 🆕 신규 필드
                    "source": routing_metadata.get("source", "llm"),
                    "profile": profile,
                }
            )
            logger.info(
                "[LLM 라우터] 라우팅 완료",
                extra={
                    "route": routing.primary_route,
                    "data_source": routing_metadata['data_source'],
                    "intent": profile.intent.value if profile.intent else 'unknown',
                    "confidence": routing.confidence
                }
            )
            if routing.primary_route == "blocked":
                processing_time = time.time() - start_time
                immediate_response = {
                    "answer": "죄송합니다. 해당 질문은 처리할 수 없습니다.",
                    "sources": [],
                    "tokens_used": 0,
                    "topic": self.extract_topic_func(message),
                    "processing_time": processing_time,
                    "search_count": 0,
                    "ranked_count": 0,
                    "model_info": {"provider": "query_router", "model": "N/A"},
                    "routing_metadata": routing_metadata,
                }
                logger.warning(
                    "[차단] 쿼리가 차단됨",
                    extra={"reason": routing.notes}
                )
                return RouteDecision(
                    should_continue=False,
                    immediate_response=cast(RAGResultDict, immediate_response),
                    metadata=routing_metadata,
                )
        except Exception as llm_error:
            logger.warning(
                "[LLM 라우터] 오류",
                extra={"error": str(llm_error)},
                exc_info=True
            )
            routing_metadata["fallback_reason"] = str(llm_error)
        logger.info("[라우팅 완료] RAG 파이프라인 계속 진행")
        return RouteDecision(
            should_continue=True, immediate_response=None, metadata=routing_metadata
        )

    # NOTE: _get_score_multipliers() 함수 제거됨 (2026-01-02)
    # 스코어 가중치는 ScoringService(rag.yaml의 scoring 섹션)에서 관리됩니다.
    # 마이그레이션 가이드: DOMAIN_CUSTOMIZATION_GUIDE.md 참조

    @observe(name="Query Expansion & Context Preparation")
    async def prepare_context(self, message: str, session_id: str) -> PreparedContext:
        """
        2단계: 세션 컨텍스트 조회 + 쿼리 확장

        - 세션 모듈에서 최근 5개 대화 조회
        - 쿼리 확장 모듈로 쿼리 확장 (선택적)

        Args:
            message: 원본 쿼리
            session_id: 세션 ID

        Returns:
            PreparedContext: 세션 컨텍스트 + 확장된 쿼리
        """
        logger.debug("[3단계] 컨텍스트 준비 시작")
        session_context = None
        if self.session_module:
            try:
                context_string = await self.session_module.get_context_string(session_id)
                if context_string:
                    session_context = context_string
                    logger.debug(
                        "세션 컨텍스트 로드 성공",
                        extra={"context_length": len(context_string)}
                    )
                else:
                    logger.debug("세션 컨텍스트 비어있음")
            except Exception as e:
                logger.warning(
                    "세션 컨텍스트 조회 실패",
                    extra={"error": str(e)},
                    exc_info=True
                )
        # Multi-Query RRF: 모든 확장 쿼리와 가중치 추출
        expanded_query = message
        expanded_queries: list[str] = []
        query_weights: list[float] = []

        if self.query_expansion:
            try:
                logger.debug("쿼리 확장 시도")
                expansion_result = await self.query_expansion.expand_query(
                    query=message, context=session_context
                )

                if expansion_result and hasattr(expansion_result, "expansions"):
                    if expansion_result.expansions:
                        # metadata에서 raw_expanded_queries 추출 (weight 정보 포함)
                        raw_queries = expansion_result.metadata.get("raw_expanded_queries", [])

                        if raw_queries:
                            # 원본 데이터에서 쿼리와 가중치 추출
                            for item in raw_queries:
                                if isinstance(item, dict):
                                    query = item.get("query", "")
                                    weight = item.get("weight", 1.0)
                                    if query:
                                        expanded_queries.append(query)
                                        query_weights.append(weight)

                        # raw_queries가 없으면 expansions에서 추출 (가중치는 동일하게)
                        if not expanded_queries:
                            expanded_queries = expansion_result.expansions
                            query_weights = [1.0] * len(expanded_queries)

                        expanded_query = expanded_queries[0]  # 첫 번째 쿼리 (하위 호환성)
                        logger.info(
                            "쿼리 확장 성공",
                            extra={
                                "query_count": len(expanded_queries),
                                "weights": [f'{w:.1f}' for w in query_weights],
                                "original": message[:30],
                                "expanded": expanded_query[:30]
                            }
                        )
                    else:
                        logger.debug("쿼리 확장 결과 없음, 원본 사용")
                        expanded_queries = [message]
                        query_weights = [1.0]
                else:
                    logger.debug("쿼리 확장 결과 없음, 원본 사용")
                    expanded_queries = [message]
                    query_weights = [1.0]
            except Exception as e:
                logger.warning(
                    "쿼리 확장 실패, 원본 사용",
                    extra={"error": str(e)},
                    exc_info=True
                )
                expanded_queries = [message]
                query_weights = [1.0]
        else:
            # query_expansion 모듈 없음
            expanded_queries = [message]
            query_weights = [1.0]

        logger.debug(
            "[3단계] 컨텍스트 준비 완료",
            extra={"expanded_query": expanded_query[:50]}
        )
        return PreparedContext(
            session_context=session_context,
            expanded_query=expanded_query,
            original_query=message,
            expanded_queries=expanded_queries,
            query_weights=query_weights,
        )

    @observe(name="Document Retrieval (Hybrid Search)")
    async def retrieve_documents(
        self,
        search_queries: list[str] | str,
        query_weights: list[float] | None,
        context: str | None,
        options: dict[str, Any],
    ) -> RetrievalResults:
        """
        3단계: MongoDB Atlas 하이브리드 검색 (Multi-Query RRF 지원)

        - Multi-Query RRF: 다중 쿼리로 병렬 검색 후 RRF 알고리즘으로 병합
        - Single Query: 기존 방식 (하위 호환성)
        - Circuit Breaker 보호
        - 성능 메트릭 기록

        Args:
            search_queries: 검색 쿼리 (단일 문자열 또는 리스트)
            query_weights: 쿼리 가중치 리스트 (Multi-Query RRF용, 선택적)
            context: 세션 컨텍스트 (선택적)
            options: 검색 옵션 (limit, min_score 등)

        Note:
            스코어 가중치는 ScoringService(rag.yaml의 scoring 섹션)에서 자동 적용됩니다.

        Returns:
            RetrievalResults: 검색된 문서 리스트 (RRF 병합 완료)

        Raises:
            RetrievalError: 검색 실패 시
        """
        # 하위 호환성: 단일 쿼리를 리스트로 변환
        if isinstance(search_queries, str):
            search_queries = [search_queries]
            query_weights = [1.0]

        # query_weights 기본값
        if not query_weights:
            query_weights = [1.0] * len(search_queries)

        logger.debug(
            "[4단계] 문서 검색 시작",
            extra={
                "query_count": len(search_queries),
                "multi_query_rrf": "활성화" if len(search_queries) > 1 else "비활성화"
            }
        )

        # Future 객체 해결 (DI Container에서 Future를 전달할 수 있음)
        retrieval_module = self.retrieval_module
        if asyncio.iscoroutine(retrieval_module) or isinstance(retrieval_module, asyncio.Future):
            retrieval_module = await retrieval_module

        if not retrieval_module:
            logger.error("검색 모듈 없음")
            raise RetrievalError(ErrorCode.RETRIEVAL_SEARCH_FAILED)

        cb = self.circuit_breaker_factory.get("document_retrieval")

        async def _search() -> list[SearchResult]:
            """실제 검색 로직 (Circuit Breaker 내부) - Multi-Query RRF"""
            search_options = {
                "limit": options.get("limit", self.retrieval_limit),
                "min_score": options.get("min_score", self.min_score),
                "context": context,
            }

            # Multi-Query 검색: IMultiQueryRetriever Protocol 체크
            # RetrievalOrchestrator 직접 사용 (프로덕션)
            if isinstance(retrieval_module, IMultiQueryRetriever):
                return await retrieval_module._search_and_merge(
                    queries=search_queries,
                    top_k=search_options["limit"],
                    filters=None,  # 필터 미사용 (향후 확장 가능)
                    weights=query_weights,
                    use_rrf=True,  # RRF 활성화
                )
            # 하위 호환성: orchestrator를 속성으로 갖는 경우
            elif hasattr(retrieval_module, "orchestrator"):
                orchestrator = retrieval_module.orchestrator
                if isinstance(orchestrator, IMultiQueryRetriever):
                    # orchestrator._search_and_merge 직접 호출 (RRF 병합)
                    return await orchestrator._search_and_merge(
                        queries=search_queries,
                        top_k=search_options["limit"],
                        filters=None,  # 필터 미사용 (향후 확장 가능)
                        weights=query_weights,
                        use_rrf=True,  # RRF 활성화
                    )

            # Fallback: 단일 쿼리 검색 (기존 방식)
            return cast(
                list[SearchResult], await retrieval_module.search(search_queries[0], search_options)
            )

        try:
            start_time = time.time()
            search_results = await cb.call(_search, fallback=lambda: [])
            latency_ms = (time.time() - start_time) * 1000
            self.performance_metrics.record_latency("retrieve_documents", latency_ms)
            logger.info(
                "[4단계] 검색 완료",
                extra={
                    "document_count": len(search_results),
                    "latency_ms": latency_ms,
                    "multi_query_rrf": "활성화" if len(search_queries) > 1 else "비활성화"
                }
            )
            return RetrievalResults(documents=search_results, count=len(search_results))
        except CircuitBreakerOpenError:
            logger.warning("Circuit Breaker OPEN - 검색 서비스 일시 차단")
            return RetrievalResults(documents=[], count=0)
        except Exception as e:
            logger.error(
                "[4단계] 문서 검색 실패",
                extra={"error": str(e)},
                exc_info=True
            )
            raise RetrievalError(
                ErrorCode.RETRIEVAL_SEARCH_FAILED,
                queries=[q[:50] for q in search_queries],
                error=str(e),
            ) from e

    async def rerank_documents(
        self, search_query: str, search_results: list[Any], options: dict[str, Any]
    ) -> RerankResults:
        """
        4단계: 검색 결과 리랭킹 (선택적)

        - 리랭킹 설정 확인 (config.reranking.enabled)
        - Jina/Cohere/LLM 리랭커 호출
        - 실패 시 원본 반환

        Args:
            search_query: 검색 쿼리
            search_results: 검색 결과 (Document 리스트)
            options: 리랭킹 옵션 (top_n 등)

        Returns:
            RerankResults: 리랭킹된 문서 리스트 (reranked=True/False)
        """
        logger.debug("[5단계] 리랭킹 시작")
        if not search_results:
            logger.debug("검색 결과 없음, 리랭킹 스킵")
            return RerankResults(documents=[], count=0, reranked=False)
        reranking_config = self.config.get("reranking", {})
        retrieval_config = self.config.get("retrieval", {})
        reranking_enabled = reranking_config.get("enabled", False) or retrieval_config.get(
            "enable_reranking", False
        )
        if not reranking_enabled:
            logger.debug("리랭킹 비활성화 - 원본 사용")
            return RerankResults(
                documents=search_results, count=len(search_results), reranked=False
            )
        # Future 객체 해결
        retrieval_module = self.retrieval_module
        if asyncio.iscoroutine(retrieval_module) or isinstance(retrieval_module, asyncio.Future):
            retrieval_module = await retrieval_module

        if not retrieval_module or not hasattr(retrieval_module, "rerank"):
            logger.warning("리랭킹 모듈 없음 - 원본 사용")
            return RerankResults(
                documents=search_results, count=len(search_results), reranked=False
            )
        try:
            logger.debug(
                "리랭킹 실행",
                extra={"document_count": len(search_results)}
            )
            ranked_results = await retrieval_module.rerank(
                query=search_query,
                results=search_results,
                top_n=options.get("top_n", self.rerank_top_n),
            )
            # 리랭킹 후 min_score 필터링
            min_score = reranking_config.get("min_score", 0.05)
            if min_score > 0:
                before_count = len(ranked_results)
                ranked_results = [
                    doc
                    for doc in ranked_results
                    if (hasattr(doc, "score") and doc.score >= min_score)
                    or (hasattr(doc, "metadata") and doc.metadata.get("score", 0) >= min_score)
                ]
                if before_count > len(ranked_results):
                    logger.info(
                        "min_score 필터링",
                        extra={
                            "before_count": before_count,
                            "after_count": len(ranked_results),
                            "threshold": min_score
                        }
                    )
            logger.info(
                "[5단계] 리랭킹 완료",
                extra={"document_count": len(ranked_results)}
            )
            return RerankResults(documents=ranked_results, count=len(ranked_results), reranked=True)
        except Exception as e:
            logger.warning(
                "[5단계] 리랭킹 실패, 원본 사용",
                extra={"error": str(e)},
                exc_info=True
            )
            return RerankResults(
                documents=search_results, count=len(search_results), reranked=False
            )

    @observe(name="Answer Generation (LLM)")
    async def generate_answer(
        self, message: str, ranked_results: list[Any], context: str | None, options: dict[str, Any]
    ) -> GenerationResult:
        """
        5단계: LLM 답변 생성

        - LLM 답변 생성 (Gemini/OpenAI/Claude)
        - Circuit Breaker 보호
        - Fallback 답변 처리 (LLM 실패 시)
        - 비용 추적 (CostTracker)

        Args:
            message: 사용자 질문
            ranked_results: 리랭킹된 문서
            context: 세션 컨텍스트
            options: 생성 옵션

        Returns:
            GenerationResult: 답변 + 토큰 수 + 모델 정보

        Raises:
            GenerationError: 답변 생성 실패 시
        """
        logger.debug("[6단계] 답변 생성 시작")
        if not self.generation_module:
            logger.error("생성 모듈 없음")
            return GenerationResult(
                answer="죄송합니다. 답변을 생성할 수 없습니다.",
                text="죄송합니다. 답변을 생성할 수 없습니다.",
                tokens_used=0,
                model_used="none",
                provider="none",
                generation_time=0.0,
            )
        cb = self.circuit_breaker_factory.get("answer_generation")
        safe_docs = []
        dropped_count = 0
        for doc in ranked_results or []:
            if validate_document(doc):
                safe_docs.append(doc)
            else:
                dropped_count += 1
                logger.warning(
                    "문서 인젝션 패턴 감지 - 차단",
                    extra={"total_dropped": dropped_count}
                )
        if dropped_count > 0:
            logger.info(
                "안전 문서 필터링 완료",
                extra={"safe_count": len(safe_docs), "dropped_count": dropped_count}
            )
        context_documents = safe_docs

        async def _generate() -> GenerationResult:
            """실제 답변 생성 로직 (Circuit Breaker 내부)"""
            # session_context를 options에 포함시켜 전달
            generation_options = {**options, "session_context": context}
            return cast(
                GenerationResult,
                await self.generation_module.generate_answer(
                    query=message, context_documents=context_documents, options=generation_options
                ),
            )

        def _fallback() -> dict[str, Any]:
            """LLM 실패 시 Fallback 답변"""
            if context_documents:
                top_doc = context_documents[0]
                content = getattr(top_doc, "page_content", str(top_doc))[:300]
                return {
                    "answer": f"관련 정보를 찾았습니다:\n\n{content}...\n\n(현재 AI 서비스 일시 장애로 상세 답변이 어렵습니다. 잠시 후 다시 시도해주세요.)",
                    "tokens_used": 0,
                    "model_info": {"provider": "fallback", "model": "document_summary"},
                }
            else:
                return {
                    "answer": "죄송합니다. 관련 정보를 찾을 수 없으며, 현재 AI 서비스도 일시적으로 이용할 수 없습니다. 다른 방식으로 질문해 주시겠어요?",
                    "tokens_used": 0,
                    "model_info": {"provider": "fallback", "model": "none"},
                }

        try:
            start_time = time.time()
            generation_result: GenerationResult | dict[str, Any] = await cb.call(
                _generate, fallback=_fallback
            )
            latency_ms = (time.time() - start_time) * 1000
            self.performance_metrics.record_latency("generate_integrated_answer", latency_ms)

            # 타입 가드: GenerationResult 또는 dict 처리
            # GenerationResult 객체인지 확인 (hasattr로도 체크하여 더 안전하게)
            if isinstance(generation_result, GenerationResult):
                tokens = generation_result.tokens_used
                provider = generation_result.provider
                answer = generation_result.answer
                model_info = generation_result.model_info
            elif isinstance(generation_result, dict):
                # fallback이 dict를 반환한 경우 (Circuit Breaker 내부 fallback)
                tokens = generation_result.get("tokens_used", 0)
                provider = generation_result.get("model_info", {}).get("provider", "google")
                answer = generation_result.get("answer", "답변을 생성할 수 없습니다.")
                model_info = generation_result.get("model_info", {})
            else:
                # 예상치 못한 타입 (안전 장치)
                logger.error(f"⚠️ 예상치 못한 generation_result 타입: {type(generation_result)}")
                tokens = 0
                provider = "unknown"
                answer = "답변 생성 중 오류가 발생했습니다."
                model_info = {"provider": "error", "model": "unknown"}

            if tokens > 0 and provider in ["google", "openai", "anthropic"]:
                self.cost_tracker.track_usage(provider, tokens, is_input=False)

            if contains_output_leakage(answer):
                logger.error(
                    "프롬프트 누출 감지 - 답변 차단",
                    extra={"preview": answer[:100]}
                )
                answer = "보안 정책에 따라 내부 지시사항은 공개되지 않습니다. 문서 기반 답변이 필요한 내용을 다시 질문해주세요."
                self.performance_metrics.record_error("prompt_leakage_blocked")

            logger.info(
                "[6단계] 답변 생성 완료",
                extra={
                    "answer_length": len(answer),
                    "latency_ms": latency_ms,
                    "tokens": tokens
                }
            )
            return GenerationResult(
                answer=answer,
                text=answer,
                tokens_used=tokens,
                model_used=model_info.get("model", "unknown"),
                provider=model_info.get("provider", "unknown"),
                generation_time=latency_ms / 1000,
            )
        except CircuitBreakerOpenError:
            # Circuit Breaker 에러 → 일시적 장애, Fallback 사용
            logger.warning("🚫 Circuit Breaker OPEN - LLM 서비스 일시 차단, Fallback 사용")
            fallback_result = _fallback()
            return GenerationResult(
                answer=fallback_result["answer"],
                text=fallback_result["answer"],
                tokens_used=fallback_result["tokens_used"],
                model_used=fallback_result["model_info"].get("model", "fallback"),
                provider=fallback_result["model_info"].get("provider", "fallback"),
                generation_time=0.0,
            )
        except TimeoutError as e:
            # 타임아웃 에러 → 클라이언트에게 재시도 유도
            logger.error(
                "[6단계] 답변 생성 타임아웃",
                extra={"error": str(e)},
                exc_info=True
            )
            raise GenerationError(
                ErrorCode.GENERATION_TIMEOUT,
                session_id=options.get("session_id", "unknown"),
                timeout_seconds=30,
            ) from e
        except ValueError as e:
            # 입력 검증 에러 → 클라이언트 에러
            logger.error(
                "[6단계] 잘못된 입력",
                extra={"error": str(e)},
                exc_info=True
            )
            raise GenerationError(
                ErrorCode.GENERATION_INVALID_RESPONSE,
                session_id=options.get("session_id", "unknown"),
                error=str(e),
            ) from e
        except Exception as e:
            # 예상치 못한 에러 → 서버 에러
            logger.error(
                "[6단계] 답변 생성 실패",
                extra={"error": str(e)},
                exc_info=True
            )
            raise GenerationError(
                ErrorCode.GENERATION_REQUEST_FAILED,
                session_id=options.get("session_id", "unknown"),
                error=str(e),
            ) from e

    @observe(name="Self-RAG Quality Verification")
    async def self_rag_verify(
        self,
        message: str,
        session_id: str,
        generation_result: GenerationResult,
        documents: list[Any],
        options: dict[str, Any],
    ) -> GenerationResult:
        """
        6단계: Self-RAG 품질 검증 (선택적)

        RAGPipeline이 이미 생성한 답변의 품질을 평가하고, 필요시에만 재생성합니다.
        기존 검색/생성 결과를 재활용하여 중복을 최소화합니다.

        워크플로우:
        1. 복잡도 계산 (낮으면 품질 검증 스킵)
        2. 기존 답변 품질 평가 (재검색/재생성 없이 평가만!)
        3. 품질 >= 0.8 → 기존 답변 그대로 사용 ✅
        4. 품질 < 0.8 → 재검색(15개) + 재생성 + Rollback 판단

        Args:
            message: 사용자 질문
            session_id: 세션 ID
            generation_result: RAGPipeline이 생성한 초기 답변
            documents: RAGPipeline이 검색한 문서 리스트
            options: 추가 옵션

        Returns:
            GenerationResult: 최종 답변 (기존 답변 또는 재생성 답변)
        """
        logger.debug("[6단계] Self-RAG 품질 검증 시작")

        # ⭐ 디버깅 추적 데이터 추출
        debug_trace_data = options.get("_debug_trace_data")

        # Self-RAG 비활성화 확인
        self_rag_config = self.config.get("self_rag", {})
        if not self_rag_config.get("enabled", False):
            logger.debug("Self-RAG 비활성화 - 기존 답변 사용")
            return generation_result

        # Future 객체 해결
        self_rag_module = self.self_rag_module
        if self_rag_module:
            if asyncio.iscoroutine(self_rag_module) or isinstance(self_rag_module, asyncio.Future):
                self_rag_module = await self_rag_module

        # Self-RAG 모듈 없음
        if not self_rag_module:
            logger.debug("Self-RAG 모듈 없음 - 기존 답변 사용")
            return generation_result

        try:
            logger.info("Self-RAG 품질 검증 시작 (기존 답변 재활용 모드)")

            # ✅ 최적화: verify_existing_answer 메서드 사용 (중복 제거)
            # RAGPipeline이 이미 생성한 답변과 문서를 전달
            self_rag_result = await self_rag_module.verify_existing_answer(
                query=message,
                existing_answer=generation_result.answer,  # ✅ 기존 답변 전달
                existing_docs=documents,  # ✅ 기존 문서 전달
                session_id=session_id,
            )

            # Self-RAG가 적용되었는지 확인
            if self_rag_result.used_self_rag:
                logger.info(
                    "Self-RAG 검증 완료",
                    extra={
                        "complexity": self_rag_result.complexity.score,
                        "regenerated": self_rag_result.regenerated
                    }
                )

                # ⭐ Self-RAG 평가 추적
                if debug_trace_data is not None:
                    debug_trace_data["self_rag_evaluation"] = {
                        "initial_quality": self_rag_result.initial_quality.overall if self_rag_result.initial_quality else 0.0,
                        "regenerated": self_rag_result.regenerated,
                        "final_quality": self_rag_result.final_quality.overall if self_rag_result.final_quality else 0.0,
                        "reason": self_rag_result.initial_quality.reasoning if self_rag_result.initial_quality else None,
                    }

                # ⭐ 품질 게이트 적용
                min_quality = self_rag_config.get("min_quality_to_answer", 0.6)
                final_quality_score = (
                    self_rag_result.final_quality.overall
                    if self_rag_result.final_quality
                    else 0.0
                )

                if final_quality_score < min_quality:
                    logger.warning(
                        "저품질 답변 감지 - 답변 거부",
                        extra={
                            "score": final_quality_score,
                            "threshold": min_quality
                        }
                    )

                    # 거부 메시지 반환
                    return GenerationResult(
                        answer="죄송합니다. 확실한 정보를 찾지 못했습니다. 질문을 구체적으로 다시 작성해주시겠어요?",
                        text="죄송합니다. 확실한 정보를 찾지 못했습니다.",
                        tokens_used=generation_result.tokens_used,
                        model_used=generation_result.model_used,
                        provider=generation_result.provider,
                        generation_time=generation_result.generation_time,
                        refusal_reason="quality_too_low",  # ⭐ 신규 필드
                        quality_score=final_quality_score,  # ⭐ 신규 필드
                    )

                # 품질 점수 로깅 및 Langfuse Score 기록
                if self_rag_result.initial_quality:
                    initial_q = self_rag_result.initial_quality.overall
                    logger.info("초기 품질", extra={"score": initial_q})

                    # Langfuse Score 기록: 초기 품질
                    try:
                        langfuse_context.score_current_trace(
                            name="self_rag_initial_quality",
                            value=initial_q,
                            comment=f"Self-RAG 초기 답변 품질 (complexity: {self_rag_result.complexity.score:.2f})",
                        )
                    except Exception as e:
                        logger.debug(f"Langfuse Score 기록 실패 (무시): {e}")

                    if self_rag_result.regenerated and self_rag_result.final_quality:
                        final_q = self_rag_result.final_quality.overall
                        improvement = final_q - initial_q
                        logger.info(
                            "품질 비교",
                            extra={
                                "initial": initial_q,
                                "final": final_q,
                                "improvement": improvement
                            }
                        )

                        # Langfuse Score 기록: 최종 품질 및 개선도
                        try:
                            langfuse_context.score_current_trace(
                                name="self_rag_final_quality",
                                value=final_q,
                                comment=f"Self-RAG 재생성 후 품질 (improvement: {improvement:+.2f})",
                            )
                            langfuse_context.score_current_trace(
                                name="self_rag_improvement",
                                value=improvement,
                                comment="Self-RAG 품질 개선도 (final - initial)",
                            )
                        except Exception as e:
                            logger.debug(f"Langfuse Score 기록 실패 (무시): {e}")

                # Self-RAG 답변 출력 누출 검사
                answer = self_rag_result.answer
                if contains_output_leakage(answer):
                    logger.error(
                        "프롬프트 누출 감지 (Self-RAG) - 답변 차단",
                        extra={"preview": answer[:100]}
                    )
                    answer = "보안 정책에 따라 내부 지시사항은 공개되지 않습니다. 문서 기반 답변이 필요한 내용을 다시 질문해주세요."
                    self.performance_metrics.record_error("prompt_leakage_blocked")

                # Self-RAG 답변으로 교체 (재생성됐든 안 됐든)
                return GenerationResult(
                    answer=answer,
                    text=answer,
                    tokens_used=(
                        self_rag_result.tokens_used
                        if self_rag_result.regenerated
                        else generation_result.tokens_used
                    ),
                    model_used=generation_result.model_used,
                    provider=generation_result.provider,
                    generation_time=generation_result.generation_time,
                    model_config=generation_result.model_config,
                    quality_score=final_quality_score,  # ⭐ 신규 필드
                    _model_info_override={
                        **generation_result.model_info,
                        "self_rag_applied": True,
                        "self_rag_regenerated": self_rag_result.regenerated,
                        "complexity_score": self_rag_result.complexity.score,
                        "initial_quality": (
                            self_rag_result.initial_quality.overall
                            if self_rag_result.initial_quality
                            else None
                        ),
                        "final_quality": (
                            self_rag_result.final_quality.overall
                            if self_rag_result.final_quality
                            else None
                        ),
                    },
                )
            else:
                logger.info(
                    "Self-RAG 미적용 (복잡도 낮음) - 기존 답변 사용",
                    extra={"complexity": self_rag_result.complexity.score}
                )
                # Self-RAG 미적용 시에도 메타데이터 추가 (API 응답 완전성 보장)
                return GenerationResult(
                    answer=generation_result.answer,
                    text=generation_result.text,
                    tokens_used=generation_result.tokens_used,
                    model_used=generation_result.model_used,
                    provider=generation_result.provider,
                    generation_time=generation_result.generation_time,
                    model_config=generation_result.model_config,
                    _model_info_override={
                        **generation_result.model_info,
                        "self_rag_applied": False,
                        "complexity_score": self_rag_result.complexity.score,
                    },
                )

        except Exception as e:
            logger.warning(
                "[6단계] Self-RAG 검증 실패, 기존 답변 사용",
                extra={"error": str(e)},
                exc_info=True
            )
            return generation_result

    def _format_rag_source(self, idx: int, doc: Any) -> dict[str, Any] | None:
        """RAG 검색 결과를 Source 객체로 변환"""
        try:
            metadata = getattr(doc, "metadata", {})
            document_name = (
                metadata.get("source_file")
                or metadata.get("source")
                or f"Document {idx + 1}"
            )

            if self.privacy_masker:
                document_name = self.privacy_masker.mask_filename(document_name)

            content_text = getattr(doc, "content", None) or getattr(doc, "page_content", "")
            if content_text and self.privacy_masker:
                content_text = self.privacy_masker.mask_text(content_text)
            content_preview = content_text[:200] if content_text else ""

            raw_score = getattr(doc, "score", 0.0)
            normalized_score = self.score_normalizer.normalize(raw_score)

            source_data = {
                "id": idx,
                "document": document_name,
                "page": metadata.get("page"),
                "chunk": metadata.get("chunk"),
                "relevance": normalized_score,
                "content_preview": content_preview,
                "source_type": "rag",
            }

            if metadata:
                file_path = metadata.get("file_path")
                if file_path and self.privacy_masker:
                    dir_path = os.path.dirname(file_path)
                    file_name = os.path.basename(file_path)
                    masked_name = self.privacy_masker.mask_filename(file_name)
                    file_path = os.path.join(dir_path, masked_name) if dir_path else masked_name

                source_data.update(
                    {
                        "file_type": metadata.get("file_type"),
                        "file_path": file_path,
                        "file_size": metadata.get("file_size"),
                        "total_chunks": metadata.get("total_chunks"),
                        "sheet_name": metadata.get("sheet_name"),
                    }
                )

            return source_data
        except Exception as e:
            logger.warning(
                "소스 포맷팅 실패",
                extra={"source_idx": idx, "error": str(e)},
                exc_info=True
            )
            return None

    def _format_sql_row(
        self,
        row: dict[str, Any],
        row_idx: int,
        source_id: int,
        sql_query: str | None,
        category: str | None = None,
    ) -> dict[str, Any]:
        """SQL 검색 결과의 한 행을 Source 객체로 변환"""
        shop_name = row.get("shop_name") or row.get("업체명") or f"결과 {row_idx + 1}"
        row_preview = ", ".join(f"{k}: {v}" for k, v in row.items() if v is not None)

        if row_preview and self.privacy_masker:
            row_preview = self.privacy_masker.mask_text(row_preview)

        document_name = f"[{category}] {shop_name}" if category else str(shop_name)

        return {
            "id": source_id,
            "document": document_name,
            "page": None,
            "chunk": None,
            "relevance": 100.0,
            "content_preview": row_preview[:200] if row_preview else "SQL 쿼리 결과",
            "source_type": "sql",
            "sql_query": sql_query,
            "sql_result_summary": row_preview,
        }

    def _add_multi_query_sql_sources(
        self, sources: list[Any], sql_search_result: SQLSearchResult, max_sources: int
    ) -> int:
        """멀티 쿼리 SQL 결과를 sources에 추가"""
        added_count = 0
        for query_result in sql_search_result.query_results:
            if not query_result.success or not query_result.result:
                continue

            sql_result = query_result.result
            sql_query = query_result.query.sql_query
            category = query_result.query.target_category or "전체"

            for row_idx, row in enumerate(sql_result.data):
                if added_count >= max_sources:
                    break

                sql_source_data = self._format_sql_row(
                    row, row_idx, len(sources), sql_query, category
                )
                sources.append(self.Source(**sql_source_data))
                added_count += 1

        logger.info(
            "멀티 SQL 소스 추가",
            extra={
                "row_count": added_count,
                "query_count": len(sql_search_result.query_results)
            }
        )
        return added_count

    def _add_single_query_sql_sources(
        self, sources: list[Any], sql_search_result: SQLSearchResult, max_sources: int
    ) -> int:
        """단일 쿼리 SQL 결과를 sources에 추가"""
        sql_result = sql_search_result.query_result
        sql_gen = sql_search_result.generation_result
        sql_query = sql_gen.sql_query if sql_gen else None
        added_count = 0

        for row_idx, row in enumerate(sql_result.data[:max_sources]):
            sql_source_data = self._format_sql_row(row, row_idx, len(sources), sql_query)
            sources.append(self.Source(**sql_source_data))
            added_count += 1

        logger.info(
            "SQL 소스 추가",
            extra={
                "added_count": added_count,
                "total_rows": sql_result.row_count,
                "query": sql_query[:50] if sql_query else 'N/A'
            }
        )
        return added_count

    def format_sources(
        self,
        ranked_results: list[Any],
        sql_search_result: SQLSearchResult | None = None,
    ) -> FormattedSources:
        """
        6단계: 검색 결과 → Source 객체 변환

        - RAG 문서 → Source 객체 변환 (source_type="rag")
        - SQL 검색 결과 → Source 객체 변환 (source_type="sql")
        - 메타데이터 정규화 (file_type, relevance 등)

        Args:
            ranked_results: 리랭킹된 문서 (RRF 병합 결과)
            sql_search_result: SQL 검색 결과 (선택적)

        Returns:
            FormattedSources: Source 객체 리스트 (RAG + SQL 통합)
        """
        logger.debug("[6단계] 소스 포맷팅 시작")
        sources = []

        try:
            for idx, doc in enumerate(ranked_results):
                source_data = self._format_rag_source(idx, doc)
                if source_data:
                    sources.append(self.Source(**source_data))

            if sql_search_result and sql_search_result.used:
                try:
                    max_sql_sources = 10
                    if sql_search_result.is_multi_query and sql_search_result.query_results:
                        self._add_multi_query_sql_sources(sources, sql_search_result, max_sql_sources)
                    elif sql_search_result.query_result:
                        self._add_single_query_sql_sources(sources, sql_search_result, max_sql_sources)
                except Exception as sql_err:
                    logger.warning(
                        "SQL 소스 포맷팅 실패 (무시)",
                        extra={"error": str(sql_err)},
                        exc_info=True
                    )

            logger.debug(
                "[6단계] 소스 포맷팅 완료",
                extra={"source_count": len(sources), "type": "RAG + SQL"}
            )
            return FormattedSources(sources=sources, count=len(sources))
        except Exception as e:
            logger.error(
                "[6단계] 소스 리스트 포맷팅 실패",
                extra={"error": str(e)},
                exc_info=True
            )
            return FormattedSources(sources=[], count=0)

    def build_result(
        self,
        answer: str,
        sources: list[Any],
        tokens_used: int,
        topic: str,
        processing_time: float,
        search_count: int,
        ranked_count: int,
        model_info: dict[str, Any],
        routing_metadata: dict[str, Any] | None,
        debug_trace: DebugTrace | None = None,  # ⭐ 신규 파라미터
    ) -> RAGResultDict:
        """
        7단계: 최종 응답 딕셔너리 구성

        - 표준 응답 형식 생성
        - 라우팅 메타데이터 포함 (선택적)
        - 디버깅 추적 정보 포함 (선택적)

        Args:
            answer: 생성된 답변
            sources: Source 객체 리스트
            tokens_used: 사용된 토큰 수
            topic: 추출된 토픽
            processing_time: 총 처리 시간 (초)
            search_count: 검색된 문서 수
            ranked_count: 리랭킹된 문서 수
            model_info: 모델 정보
            routing_metadata: 라우팅 메타데이터
            debug_trace: 디버깅 추적 정보 (enable_debug_trace=True 시)

        Returns:
            표준 응답 딕셔너리

        Note:
            이 메서드는 동기 함수 (async 불필요)
        """
        logger.debug("[8단계] 결과 구성 시작")

        # model_info 표준화 (API 응답 일관성 보장)
        if model_info:
            # 필수 필드 보장 + 하위 호환성
            standardized_model_info = {
                "provider": model_info.get("provider", "unknown"),
                "model": model_info.get("model", "unknown"),
                "model_used": model_info.get("model", model_info.get("model_used", "unknown")),
                "self_rag_applied": model_info.get("self_rag_applied", False),
            }

            # 선택적 필드 (존재하는 경우만 추가)
            optional_fields = [
                "complexity_score",
                "initial_quality",
                "final_quality",
                "self_rag_regenerated",
            ]
            for field in optional_fields:
                if field in model_info and model_info[field] is not None:
                    standardized_model_info[field] = model_info[field]
        else:
            # model_info가 없는 경우 안전한 기본값 (방어적 프로그래밍)
            logger.warning("model_info가 None - 기본값 사용")
            standardized_model_info = {
                "provider": "unknown",
                "model": "unknown",
                "model_used": "unknown",
                "self_rag_applied": False,
            }

        # PII 마스킹: 최종 답변에서 개인정보 마스킹 (활성화 시에만)
        masked_answer = answer
        if self.privacy_masker:
            masked_answer = self.privacy_masker.mask_text(answer)

        result = {
            "answer": masked_answer,
            "sources": sources,
            "tokens_used": tokens_used,
            "topic": topic,
            "processing_time": processing_time,
            "search_results": search_count,
            "ranked_results": ranked_count,
            "model_info": standardized_model_info,
        }

        if routing_metadata:
            result["routing_metadata"] = routing_metadata

        # ⭐ 디버깅 추적 정보 추가
        if debug_trace is not None:
            result["debug_trace"] = debug_trace

        logger.debug(
            "[8단계] 결과 구성 완료",
            extra={
                "search_count": search_count,
                "ranked_count": ranked_count
            }
        )
        return cast(RAGResultDict, result)

    async def _execute_sql_search(self, query: str) -> SQLSearchResult | None:
        """
        SQL 검색 실행 (내부 헬퍼 메서드)

        RAG 검색과 병렬로 실행되며, 실패해도 파이프라인은 계속 진행됩니다.
        타임아웃과 에러 핸들링이 적용됩니다.

        Args:
            query: 사용자 질문

        Returns:
            SQLSearchResult | None: SQL 검색 결과 또는 None (실패/비활성화 시)
        """
        if not self.sql_search_service:
            return None

        try:
            # SQL 검색 설정에서 타임아웃 조회
            sql_config = self.config.get("sql_search", {}).get("pipeline", {})
            timeout = sql_config.get("timeout", 8)  # 기본 8초

            # 타임아웃 적용
            result = await asyncio.wait_for(self.sql_search_service.search(query), timeout=timeout)

            return result

        except TimeoutError:
            logger.warning(
                "SQL 검색 타임아웃",
                extra={"timeout_seconds": timeout}
            )
            return SQLSearchResult(
                success=False,
                generation_result=None,
                query_result=None,
                formatted_context="",
                total_time=timeout,
                used=False,
                error="SQL 검색 타임아웃",
            )
        except Exception as e:
            logger.warning(
                "SQL 검색 실패",
                extra={"error": str(e)},
                exc_info=True
            )
            return SQLSearchResult(
                success=False,
                generation_result=None,
                query_result=None,
                formatted_context="",
                total_time=0,
                used=False,
                error=str(e),
            )

    async def _execute_agent_mode(
        self, message: str, session_id: str, start_time: float
    ) -> RAGResultDict:
        """
        Agent 모드 실행 (Agentic RAG)

        AgentOrchestrator를 사용하여 ReAct 패턴 기반 에이전트 루프를 실행합니다.
        기존 7단계 파이프라인 대신 LLM이 도구를 선택하고 실행하는 방식입니다.

        Args:
            message: 사용자 쿼리
            session_id: 세션 ID
            start_time: 파이프라인 시작 시간

        Returns:
            RAGResultDict: Agent 모드 응답 (metadata.mode="agent" 포함)

        Raises:
            GenerationError: Agent 실행 중 오류 발생 시
        """
        # 세션 컨텍스트 조회
        session_context = ""
        if self.session_module:
            try:
                context_string = await self.session_module.get_context_string(session_id)
                if context_string:
                    session_context = context_string
                    logger.debug(
                        "세션 컨텍스트 로드 성공",
                        extra={"context_length": len(context_string)}
                    )
            except Exception as e:
                logger.warning(
                    "세션 컨텍스트 조회 실패",
                    extra={"error": str(e)},
                    exc_info=True
                )

        try:
            # AgentOrchestrator 실행
            agent_result: AgentResult = await self.agent_orchestrator.run(
                query=message,
                session_context=session_context,
            )

            # Agent 결과를 RAGResultDict 형식으로 변환
            processing_time = time.time() - start_time

            # Source 객체 변환 (Agent sources는 dict 형태일 수 있음)
            formatted_sources = []
            for idx, source in enumerate(agent_result.sources or []):
                if isinstance(source, dict):
                    formatted_sources.append(
                        self.Source(
                            id=idx,
                            document=source.get("source", source.get("title", f"Source {idx + 1}")),
                            page=source.get("page"),
                            chunk=source.get("chunk"),
                            relevance=source.get("relevance", source.get("score", 0.0)),
                            content_preview=source.get(
                                "content_preview", source.get("content", "")[:200]
                            ),
                            source_type="agent",
                        )
                    )
                else:
                    # 이미 Source 객체인 경우 그대로 사용
                    formatted_sources.append(source)

            result: RAGResultDict = cast(
                RAGResultDict,
                {
                    "answer": agent_result.answer,
                    "sources": formatted_sources,
                    "tokens_used": 0,  # Agent 모드에서는 개별 추적 어려움
                    "topic": self.extract_topic_func(message),
                    "processing_time": processing_time,
                    "search_results": len(agent_result.sources or []),
                    "ranked_results": len(agent_result.sources or []),
                    "model_info": {
                        "provider": "agent",
                        "model": "agent_orchestrator",
                        "model_used": "agent_orchestrator",
                    },
                    "metadata": {
                        "mode": "agent",
                        "steps_taken": agent_result.steps_taken,
                        "tools_used": agent_result.tools_used,
                        "total_time": agent_result.total_time,
                        "success": agent_result.success,
                    },
                },
            )

            logger.info(
                "Agent 모드 완료",
                extra={
                    "steps_taken": agent_result.steps_taken,
                    "processing_time": processing_time,
                    "tools_count": len(agent_result.tools_used)
                }
            )

            return result

        except Exception as e:
            logger.error(
                "Agent 모드 실행 실패",
                extra={"error": str(e)},
                exc_info=True
            )
            raise GenerationError(
                ErrorCode.GENERATION_REQUEST_FAILED,
                session_id=session_id,
                error=str(e),
            ) from e
