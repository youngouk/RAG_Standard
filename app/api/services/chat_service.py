"""
Chat Service - 비즈니스 로직 레이어

Phase 3.2: chat.py에서 추출한 검증된 비즈니스 로직
기존 코드 기반: app/api/chat.py의 핵심 함수들

⚠️ 주의: 이 코드는 기존 검증된 로직을 재사용합니다.

## Service Layer의 역할
- 비즈니스 로직만 담당 (HTTP 요청/응답과 분리)
- 모듈 의존성 주입을 통한 테스트 가능성 확보
- RAG 파이프라인, 세션 처리, 통계 관리 등 핵심 기능 제공
"""

from datetime import datetime
from typing import Any

from ...lib.cost_tracker import CostTracker
from ...lib.errors import ErrorCode, SessionError
from ...lib.logger import get_logger
from ...lib.metrics import PerformanceMetrics
from ...lib.types import RAGResultDict, SessionInfoDict, SessionResult, StatsDict
from .rag_pipeline import RAGPipeline

# LangSmith 트레이싱 import
try:
    from langsmith import traceable

    LANGSMITH_AVAILABLE = True
except ImportError:
    LANGSMITH_AVAILABLE = False

    def traceable(*args, **kwargs):  # type: ignore[no-redef]
        def decorator(func):
            return func

        return decorator


logger = get_logger(__name__)


class ChatService:
    """
    채팅 비즈니스 로직 서비스

    역할:
    - RAG 파이프라인 실행
    - 세션 관리
    - 통계 수집
    - 컨텍스트 처리

    기존 코드 기반: app/api/chat.py의 함수들을 클래스로 재구성
    """

    def __init__(self, modules: dict[str, Any], config: dict[str, Any]):
        """
        Args:
            modules: 애플리케이션 모듈 딕셔너리 (DI)
            config: 설정 딕셔너리
        """
        self.modules = modules
        self.config = config

        # 통계 정보
        self.stats = {
            "total_chats": 0,
            "total_tokens": 0,
            "average_latency": 0.0,
            "error_rate": 0.0,
            "errors": 0,
        }

        # RAGPipeline 인스턴스 생성 (의존성 주입)
        self.rag_pipeline = RAGPipeline(
            config=config,
            query_router=modules.get("query_router"),
            query_expansion=modules.get("query_expansion"),
            retrieval_module=modules.get("retrieval"),
            generation_module=modules.get("generation"),
            session_module=modules.get("session"),
            self_rag_module=modules.get("self_rag"),  # ✅ Self-RAG 모듈 주입
            extract_topic_func=self.extract_topic,
            circuit_breaker_factory=modules.get(
                "circuit_breaker_factory"
            ),  # ✅ Circuit Breaker Factory 주입
            cost_tracker=modules.get("cost_tracker") or CostTracker(),  # ✅ 비용 추적기 주입
            performance_metrics=modules.get("performance_metrics")
            or PerformanceMetrics(),  # ✅ 성능 메트릭 주입
            sql_search_service=modules.get(
                "sql_search_service"
            ),  # ✅ SQL Search Service 주입 (Phase 3)
        )

        logger.info("ChatService 초기화 완료 (RAGPipeline + Self-RAG + SQL Search 포함)")

    async def handle_session(
        self, session_id: str | None, context: dict[str, Any]
    ) -> SessionResult:
        """
        세션 처리 - 기존 세션 검증 또는 새 세션 생성

        기존 코드: chat.py의 handle_session() 함수 (L235-298)

        Args:
            session_id: 요청된 세션 ID (None이면 새로 생성)
            context: 요청 컨텍스트 (IP, User-Agent 등)

        Returns:
            세션 처리 결과 딕셔너리
        """
        try:
            session_module = self.modules.get("session")
            if not session_module:
                return {"success": False, "message": "Session module not available"}

            logger.debug(f"🔍 세션 요청 - 요청받은 session_id: {session_id}")

            if session_id:
                # 기존 세션 조회
                logger.debug(f"기존 세션 조회 시도: {session_id}")
                session_result = await session_module.get_session(session_id, context)

                if session_result.get("is_valid"):
                    logger.debug(f"✅ 세션 유효함 - session_id: {session_id}")
                    return {
                        "success": True,
                        "session_id": session_id,
                        "is_new": False,
                        "validation_result": session_result,
                    }
                else:
                    logger.warning(
                        f"세션 만료/없음: {session_id}, "
                        f"이유: {session_result.get('reason', 'unknown')}"
                    )

            # 새 세션 생성
            logger.debug(f"새 세션 생성 중... (기존 세션: {session_id})")
            new_session = await session_module.create_session(
                {"metadata": context}, session_id=session_id
            )
            new_session_id = new_session["session_id"]

            logger.debug(f"✅ 새 세션 생성 완료 - session_id: {new_session_id}")

            return {
                "success": True,
                "session_id": new_session_id,
                "is_new": True,
                "message": "새 대화 세션이 시작되었습니다.",
            }

        except KeyError as e:
            # 세션 모듈 초기화 안 됨 또는 필수 키 누락
            logger.error(f"Session handling error - missing key: {e}", exc_info=True)
            raise SessionError(
                message="세션 모듈이 초기화되지 않았습니다. 서버 관리자에게 문의하세요.",
                error_code=ErrorCode.SESSION_MODULE_NOT_AVAILABLE,
                context={"missing_key": str(e)},
                original_error=e,
            ) from e
        except Exception as e:
            # 예상치 못한 세션 처리 에러
            logger.error(f"Session handling error: {e}", exc_info=True)
            raise SessionError(
                message="세션 처리 중 오류가 발생했습니다.",
                error_code=ErrorCode.SESSION_CREATE_FAILED,
                context={"session_id": session_id, "context": context},
                original_error=e,
            ) from e

    def extract_topic(self, message: str) -> str:
        """
        토픽 추출 (간단한 키워드 기반)

        기존 코드: chat.py의 extract_topic() 함수 (L301-329)
        """
        # 안전한 메시지 처리
        if isinstance(message, list):
            message = " ".join(str(item) for item in message)
        elif not isinstance(message, str):
            message = str(message)

        if not message:
            return "general"

        keywords = {
            "search": ["검색", "찾기", "찾아", "검색해"],
            "document": ["문서", "파일", "자료", "데이터"],
            "help": ["도움", "도와", "설명", "알려"],
            "technical": ["기술", "개발", "코드", "프로그래밍"],
            "general": ["일반", "기본", "소개", "개요"],
        }

        try:
            lower_message = message.lower()

            for topic, words in keywords.items():
                if any(word in lower_message for word in words):
                    return topic

            return "general"
        except Exception:
            return "general"

    @traceable(
        name="RAGPipeline",
        tags=["chat", "rag", "pipeline"],
        metadata={"module": "chat_service", "version": "3.0.0"},
    )
    async def execute_rag_pipeline(
        self, message: str, session_id: str, options: dict[str, Any] | None = None
    ) -> RAGResultDict:
        """
        RAG 파이프라인 실행

        Phase 2 개선: 150줄 블랙박스 → RAGPipeline.execute() 단일 호출
        - 8개 독립 단계로 분해된 파이프라인 사용
        - 단계별 성능 추적 (PipelineTracker)
        - Circuit Breaker, Graceful Degradation 패턴 적용

        Args:
            message: 사용자 메시지
            session_id: 세션 ID
            options: 추가 옵션 (limit, min_score, top_n 등)

        Returns:
            RAG 파이프라인 실행 결과:
            {
                "answer": str,
                "sources": List[Source],
                "tokens_used": int,
                "topic": str,
                "processing_time": float,
                "search_results": int,
                "ranked_results": int,
                "model_info": Dict[str, Any],
                "routing_metadata": Optional[Dict[str, Any]],
                "performance_metrics": Dict[str, Any]  # NEW: PipelineTracker 메트릭
            }
        """
        logger.debug(
            "RAG Pipeline Starting (Phase 2 Refactored)",
            message_preview=message[:50],
            session_id=session_id,
        )

        # RAGPipeline.execute() 단일 호출 (8단계 오케스트레이션)
        return await self.rag_pipeline.execute(
            message=message, session_id=session_id, options=options
        )

    async def add_conversation_to_session(
        self, session_id: str, user_message: str, assistant_answer: str, metadata: dict[str, Any]
    ) -> None:
        """
        세션에 대화 기록 추가

        Args:
            session_id: 세션 ID
            user_message: 사용자 메시지
            assistant_answer: 어시스턴트 응답
            metadata: 추가 메타데이터
        """
        session_module = self.modules.get("session")
        if session_module:
            logger.debug(f"대화 추가: session_id={session_id}")
            await session_module.add_conversation(
                session_id, user_message, assistant_answer, metadata
            )

    def update_stats(self, data: dict[str, Any]) -> None:
        """
        통계 업데이트

        기존 코드: chat.py의 update_stats() 함수 (L161-179)
        """
        self.stats["total_chats"] += 1

        if data.get("success"):
            if data.get("tokens_used"):
                self.stats["total_tokens"] += data["tokens_used"]

            if data.get("latency"):
                current_avg = self.stats["average_latency"]
                chat_count = self.stats["total_chats"]
                self.stats["average_latency"] = (
                    current_avg * (chat_count - 1) + data["latency"]
                ) / chat_count
        else:
            self.stats["errors"] += 1
            self.stats["error_rate"] = (self.stats["errors"] / self.stats["total_chats"]) * 100

    def get_stats(self) -> StatsDict:
        """현재 통계 반환"""
        return self.stats.copy()  # type: ignore[return-value]

    async def get_session_info(self, session_id: str) -> SessionInfoDict:
        """
        세션 상세 정보 조회

        Returns:
            세션 정보 딕셔너리 (message_count, tokens_used, processing_time 등)
        """
        session_module = self.modules.get("session")
        if not session_module:
            raise Exception("Session module not available")

        # 세션 존재 확인
        session_result = await session_module.get_session(session_id, {})
        if not session_result.get("is_valid"):
            raise Exception("Session not found")

        # 채팅 히스토리에서 통계 추출
        history = await session_module.get_chat_history(session_id)
        messages = history.get("messages", [])

        # 통계 계산
        message_count = len(messages)
        total_tokens = 0
        total_processing_time = 0
        latest_model_info = None

        for message in messages:
            if message.get("type") == "assistant":
                if "tokens_used" in message:
                    total_tokens += message["tokens_used"]
                if "processing_time" in message:
                    total_processing_time += message["processing_time"]
                if "model_info" in message:
                    latest_model_info = message["model_info"]

        return {
            "session_id": session_id,
            "message_count": message_count,
            "tokens_used": total_tokens,
            "processing_time": total_processing_time,
            "model_info": latest_model_info,
            "timestamp": datetime.now().isoformat(),
        }
