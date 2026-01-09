"""
Memory Service - LangChain 메모리 관리 및 대화 컨텍스트
Phase 4.3: enhanced_session.py에서 추출한 검증된 메모리 관리 로직
⚠️ 주의: 이 코드는 기존 검증된 로직을 재사용합니다.
"""

import asyncio
import re
from collections import defaultdict
from datetime import UTC
from typing import Any

from cachetools import TTLCache
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import AIMessage, HumanMessage

from .....lib.logger import get_logger
from .....lib.mongodb_client import MongoDBClient

logger = get_logger(__name__)


class MemoryService:
    """
    LangChain 메모리 및 대화 컨텍스트 관리 서비스

    역할:
    - LangChain InMemoryChatMessageHistory 관리
    - 대화 추가 및 컨텍스트 문자열 생성
    - Window 로직 (max_exchanges 유지)
    - 사용자 정보 추출

    기존 코드 기반: enhanced_session.py의 메모리 및 대화 관리 메서드들
    """

    def __init__(
        self,
        max_exchanges: int | None = None,
        config: dict[str, Any] | None = None,
        mongodb_client: MongoDBClient | None = None,
    ):
        """
        Args:
            max_exchanges: 최대 교환 수 (1교환 = 사용자 메시지 + AI 메시지)
                           None일 경우 기본값 10 사용
            config: 전체 설정 딕셔너리 (요약 기능 설정 포함)
            mongodb_client: MongoDB 클라이언트 (DI)
        """
        self.max_exchanges = max_exchanges if max_exchanges is not None else 10
        self.config = config or {}
        self.mongodb_client = mongodb_client

        # LangChain 메모리 저장소 (enhanced_session.py L35)
        self.memories: dict[str, InMemoryChatMessageHistory] = {}

        # 🔒 세션별 Lock 딕셔너리 (Race Condition 방지)
        # 각 세션은 독립적인 Lock을 가지므로 다른 세션끼리는 병렬 처리 가능
        self.session_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # 요약 설정 로드
        session_config = self.config.get("session", {})
        summary_config = session_config.get("conversation_summary", {})

        self.summary_enabled = summary_config.get("enabled", False)
        self.summary_trigger_count = summary_config.get("trigger_count", 10)
        self.summary_llm_provider = summary_config.get("llm_provider", "google")
        self.summary_llm_model = summary_config.get("llm_model", "gemini-2.0-flash-lite")

        # 요약 캐시 (TTLCache: 최대 100개 세션, TTL 1시간)
        cache_ttl = summary_config.get("cache_ttl", 3600)
        self.summary_cache: TTLCache = TTLCache(maxsize=100, ttl=cache_ttl)

        logger.info(
            f"MemoryService 초기화: max_exchanges={max_exchanges}, "
            f"LangChain 0.3+ InMemoryChatMessageHistory 사용, "
            f"Session-level locks 활성화 (Race Condition 보호), "
            f"대화 요약 기능={'활성화' if self.summary_enabled else '비활성화'} "
            f"(trigger={self.summary_trigger_count}개)"
        )

    def create_memory(self, session_id: str) -> InMemoryChatMessageHistory:
        """
        새 메모리 생성
        기존 코드: enhanced_session.py의 create_session() 내 메모리 생성 (L102)

        Args:
            session_id: 세션 ID

        Returns:
            InMemoryChatMessageHistory 인스턴스
        """
        chat_history = InMemoryChatMessageHistory()
        self.memories[session_id] = chat_history
        logger.debug(f"메모리 생성: {session_id}")
        return chat_history

    def get_memory(self, session_id: str) -> InMemoryChatMessageHistory | None:
        """
        메모리 조회

        Args:
            session_id: 세션 ID

        Returns:
            InMemoryChatMessageHistory 또는 None
        """
        return self.memories.get(session_id)

    def delete_memory(self, session_id: str):
        """
        메모리 삭제

        Args:
            session_id: 세션 ID
        """
        if session_id in self.memories:
            del self.memories[session_id]
            logger.debug(f"메모리 삭제: {session_id}")

    async def add_conversation(
        self, session_id: str, session: dict[str, Any], user_message: str, assistant_response: str
    ):
        """
        대화 추가 with Window trimming + Race Condition 보호 + MongoDB 영구 저장

        기존 코드: enhanced_session.py의 add_conversation() 일부 (L200-213)
        개선 사항:
        - Session-level Lock으로 동시 메시지 추가 시 Race Condition 방지
        - MongoDB에 대화 내용 영구 저장 (Feature Flag 제어)

        ⚠️ Race Condition 시나리오:
        - 같은 세션에서 사용자가 빠르게 두 번 메시지 전송
        - 두 요청이 동시에 chat_history.messages 리스트를 수정
        - 결과: 메시지 순서 꼬임, 메시지 누락, 윈도우 트리밍 오류

        ✅ Lock 전략:
        - 세션별 Lock (다른 세션은 병렬 처리 가능)
        - Lock은 빠른 작업만 보호 (0.001초 미만)
        - LLM 호출(3초+)은 Lock 밖에서 완료됨
        - MongoDB 저장(0.01~0.02초)도 Lock 밖에서 비동기 실행

        Args:
            session_id: 세션 ID
            session: 세션 데이터 (사용자 정보 업데이트용)
            user_message: 사용자 메시지
            assistant_response: AI 응답
        """
        chat_history = self.memories.get(session_id)

        if not chat_history:
            raise ValueError(f"Chat history not found for session: {session_id}")

        # 사용자 정보 추출 (L198) - Lock 밖 (빠른 작업)
        await self._extract_user_info(session, user_message)

        # 🔒 메시지 추가, 윈도우 트리밍, MongoDB 저장 (Lock으로 보호)
        # 같은 세션의 동시 요청은 여기서 순차 처리됨
        # MongoDB 저장도 Lock 안에서 수행하여 메모리-DB 불일치 방지
        async with self.session_locks[session_id]:
            # LangChain 0.3+ 방식: 메시지 추가 (L200-202)
            chat_history.add_user_message(user_message)
            chat_history.add_ai_message(assistant_response)

            # Window 로직: 최대 교환 수 유지 (L204-213)
            max_messages = self.max_exchanges * 2
            current_messages = chat_history.messages

            if len(current_messages) > max_messages:
                messages_to_remove = len(current_messages) - max_messages
                chat_history.messages = current_messages[messages_to_remove:]
                logger.debug(
                    f"Window trimming: {messages_to_remove}개 오래된 메시지 제거, "
                    f"현재 {len(chat_history.messages)}개 유지"
                )

            # 💾 MongoDB 영구 저장 (Lock 안에서 트랜잭션처럼 실행)
            # 메시지 메타데이터는 session의 messages_metadata 배열에 저장됨
            try:
                await self._save_message_to_mongodb(
                    session_id=session_id,
                    user_message=user_message,
                    assistant_response=assistant_response,
                    metadata=(
                        session.get("messages_metadata", [])[-1]
                        if session.get("messages_metadata")
                        else {}
                    ),
                )
            except Exception as e:
                # MongoDB 저장 실패 시 메모리도 롤백
                logger.error(f"MongoDB 저장 실패, 메모리 롤백: {e}", exc_info=True)
                # 마지막 2개 메시지(user + assistant) 제거
                if len(chat_history.messages) >= 2:
                    chat_history.messages = chat_history.messages[:-2]
                raise  # 에러를 상위로 전파하여 클라이언트에게 실패 알림

    async def get_context_string(self, session_id: str, session: dict[str, Any]) -> str:
        """
        세션 컨텍스트 문자열 반환 (요약 기능 포함)
        기존 코드: enhanced_session.py의 get_context_string() (L244-287)
        신규: 대화가 많을 경우 오래된 대화를 요약하여 토큰 효율 개선

        Args:
            session_id: 세션 ID
            session: 세션 데이터

        Returns:
            컨텍스트 문자열
        """
        chat_history = self.memories.get(session_id)

        if not chat_history:
            return ""

        context_parts = []

        # 사용자 정보 추가 (L258-264)
        if session.get("user_name"):
            context_parts.append(f"사용자 이름: {session['user_name']}")

        if session.get("user_info"):
            for key, value in session["user_info"].items():
                context_parts.append(f"사용자 {key}: {value}")

        # 대화 주제들 (L266-268)
        if session.get("topics"):
            context_parts.append(f"대화 주제: {', '.join(session['topics'])}")

        # 메시지 가져오기 (L270-279)
        messages = chat_history.messages
        message_count = len(messages) // 2  # 교환 수 (사용자 + AI = 1교환)

        # 🆕 요약 로직 (옵션B 구현)
        if self.summary_enabled and message_count > self.summary_trigger_count:
            logger.debug(
                f"요약 모드 활성화: session_id={session_id}, "
                f"대화 수={message_count}, trigger={self.summary_trigger_count}"
            )

            # 캐시 키: session_id + 대화 개수
            cache_key = f"{session_id}_{message_count}"

            # 캐시 확인
            summary = self.summary_cache.get(cache_key)

            if summary:
                logger.debug(f"요약 캐시 히트: {cache_key}")
            else:
                logger.debug(f"요약 캐시 미스, LLM 요약 생성 중: {cache_key}")

                # 최근 5개 제외한 나머지를 요약
                max_recent = self.max_exchanges  # 기본 5개
                old_messages = messages[: -max_recent * 2] if len(messages) > max_recent * 2 else []

                if old_messages:
                    try:
                        summary = await self._summarize_conversations(old_messages)
                        self.summary_cache[cache_key] = summary
                        logger.info(f"✅ 요약 생성 완료: {summary[:100]}...")
                    except Exception as e:
                        logger.error(f"요약 생성 실패, 폴백: {e}")
                        summary = None

            # 요약 추가
            if summary:
                context_parts.append(f"\n[이전 대화 요약]\n{summary}")

            # 최근 대화만 추가
            recent_messages = (
                messages[-max_recent * 2 :] if len(messages) > max_recent * 2 else messages
            )
            if recent_messages:
                context_parts.append("\n[최근 대화 내역]")
                for message in recent_messages:
                    if isinstance(message, HumanMessage):
                        context_parts.append(f"사용자: {message.content}")
                    elif isinstance(message, AIMessage):
                        context_parts.append(f"AI: {message.content}")
        else:
            # 기존 방식: 모든 대화 표시
            if messages:
                context_parts.append("\n최근 대화 내역:")
                for message in messages:
                    if isinstance(message, HumanMessage):
                        context_parts.append(f"사용자: {message.content}")
                    elif isinstance(message, AIMessage):
                        context_parts.append(f"AI: {message.content}")

        # 중요 사실들 (L281-285)
        if session.get("facts"):
            context_parts.append("\n기억된 정보:")
            for key, value in session["facts"].items():
                context_parts.append(f"- {key}: {value}")

        return "\n".join(context_parts)

    async def get_chat_history(self, session_id: str, session: dict[str, Any]) -> dict[str, Any]:
        """
        채팅 히스토리 반환 (메타데이터 포함)
        기존 코드: enhanced_session.py의 get_chat_history() (L289-350)

        Args:
            session_id: 세션 ID
            session: 세션 데이터

        Returns:
            {'messages': list, 'message_count': int}
        """
        chat_history = self.memories.get(session_id)

        if not chat_history:
            return {"messages": [], "message_count": 0}

        messages = []
        chat_messages = chat_history.messages
        messages_metadata = session.get("messages_metadata", [])

        # LangChain 메시지와 메타데이터 매칭 (L312-345)
        message_index = 0
        for i in range(0, len(chat_messages), 2):
            # 사용자 메시지
            if i < len(chat_messages):
                user_msg = chat_messages[i]
                if isinstance(user_msg, HumanMessage):
                    from datetime import datetime

                    messages.append(
                        {
                            "type": "user",
                            "content": user_msg.content,
                            "timestamp": (
                                datetime.fromtimestamp(
                                    messages_metadata[message_index]["timestamp"]
                                ).isoformat()
                                if message_index < len(messages_metadata)
                                else datetime.now().isoformat()
                            ),
                        }
                    )

            # 어시스턴트 메시지
            if i + 1 < len(chat_messages):
                ai_msg = chat_messages[i + 1]
                if isinstance(ai_msg, AIMessage):
                    from datetime import datetime

                    msg_data = {
                        "type": "assistant",
                        "content": ai_msg.content,
                        "timestamp": (
                            datetime.fromtimestamp(
                                messages_metadata[message_index]["timestamp"]
                            ).isoformat()
                            if message_index < len(messages_metadata)
                            else datetime.now().isoformat()
                        ),
                    }

                    # 메타데이터 추가
                    if message_index < len(messages_metadata):
                        metadata = messages_metadata[message_index]
                        msg_data.update(
                            {
                                "tokens_used": metadata.get("tokens_used", 0),
                                "processing_time": metadata.get("processing_time", 0.0),
                                "model_info": metadata.get("model_info"),
                            }
                        )

                    messages.append(msg_data)
                    message_index += 1

        return {"messages": messages, "message_count": len(messages)}

    async def _extract_user_info(self, session: dict[str, Any], message: str):
        """
        메시지에서 사용자 정보 추출
        기존 코드: enhanced_session.py의 _extract_user_info() (L411-459)

        Args:
            session: 세션 데이터
            message: 사용자 메시지
        """
        # 이름 추출 패턴 (L414-423)
        name_patterns = [
            "내 이름은 ",
            "저는 ",
            "제 이름은 ",
            "나는 ",
            "이름이 ",
            " 입니다",
            "이라고 합니다",
            "라고 불러주세요",
        ]

        # 정규식 방식 (L429-436)
        name_match = re.search(r"저는\s+([가-힣]+)\s*입니다", message)
        if name_match:
            name_candidate = name_match.group(1).strip()
            if name_candidate and 1 < len(name_candidate) < 10:
                session["user_name"] = name_candidate
                session["facts"]["이름"] = name_candidate
                logger.info(f"이름 추출 (정규식): {name_candidate}")
                return

        # 기존 패턴 방식 (L438-448)
        for pattern in name_patterns:
            if pattern in message:
                parts = message.split(pattern)
                if len(parts) > 1:
                    name_candidate = parts[1].split()[0].rstrip("이야입니다요.").strip()
                    if name_candidate and 1 < len(name_candidate) < 10:
                        session["user_name"] = name_candidate
                        session["facts"]["이름"] = name_candidate
                        logger.info(f"이름 추출 (패턴 매칭): {name_candidate}")
                        break

        # 나이 추출 (L450-459)
        if "살" in message and any(char.isdigit() for char in message):
            age_match = re.search(r"(\d+)\s*살", message)
            if age_match:
                age = int(age_match.group(1))
                if 1 < age < 120:  # 합리적인 나이 범위
                    session["user_info"]["나이"] = age
                    session["facts"]["나이"] = f"{age}살"

    async def _save_message_to_mongodb(
        self, session_id: str, user_message: str, assistant_response: str, metadata: dict
    ):
        """
        MongoDB에 대화 내용 영구 저장 (Feature Flag 제어)

        실패해도 기존 기능에 영향 없음 (Fail-Safe 설계)

        Args:
            session_id: 세션 ID
            user_message: 사용자 메시지
            assistant_response: AI 응답
            metadata: 메시지 메타데이터 (tokens_used, processing_time, sources 등)
        """
        try:
            # Feature Flag 확인 (app/config/features/session.yaml)
            from app.lib.config_loader import load_config

            config = load_config()
            session_config = config.get("session", {})

            if not session_config.get("save_chat_to_mongodb", False):
                # Feature Flag OFF: 저장하지 않음
                return

            # MongoDB 클라이언트 확인 (DI)
            if not self.mongodb_client:
                logger.warning("MongoDB client not available (not injected via DI)")
                return

            from datetime import datetime

            collection = self.mongodb_client.get_chat_history_collection()

            if not collection:
                logger.warning("MongoDB chat_history collection not available")
                return

            # 문서 구조 생성
            message_doc = {
                "session_id": session_id,
                "message_id": metadata.get("message_id", f"msg_{datetime.now().timestamp()}"),
                "timestamp": datetime.now(UTC),
                # 대화 내용
                "user_message": user_message,
                "ai_response": assistant_response,
                # 메타데이터
                "metadata": {
                    "tokens_used": metadata.get("tokens_used", 0),
                    "processing_time": metadata.get("processing_time", 0.0),
                    "sources": metadata.get("sources", []),
                    "topic": metadata.get("topic", "general"),
                    "model_info": metadata.get("model_info", {}),
                    "can_evaluate": metadata.get("can_evaluate", False),
                    "has_temp_document": metadata.get("has_temp_document", False),
                    "temp_doc_filename": metadata.get("temp_doc_filename"),
                },
                # 추가 타임스탬프
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            }

            # 재시도 로직
            retry_count = session_config.get("mongodb_save_retry", 3)
            timeout = session_config.get("mongodb_save_timeout", 1.0)

            for attempt in range(retry_count):
                try:
                    # MongoDB 저장 (타임아웃 적용)
                    import asyncio

                    await asyncio.wait_for(
                        asyncio.to_thread(collection.insert_one, message_doc), timeout=timeout
                    )

                    logger.debug(
                        f"💾 채팅 히스토리 MongoDB 저장 성공: "
                        f"session_id={session_id}, "
                        f"message_id={message_doc['message_id']}"
                    )
                    return

                except TimeoutError:
                    if attempt < retry_count - 1:
                        logger.warning(
                            f"MongoDB 저장 타임아웃 (재시도 {attempt + 1}/{retry_count}): "
                            f"session_id={session_id}"
                        )
                        await asyncio.sleep(0.1 * (attempt + 1))  # 지수 백오프
                    else:
                        logger.error(f"MongoDB 저장 최종 실패 (타임아웃): session_id={session_id}")

                except Exception as e:
                    # 중복 키 에러는 무시 (이미 저장됨)
                    if "duplicate key" in str(e).lower():
                        logger.debug(
                            f"MongoDB 중복 메시지 (이미 저장됨): "
                            f"message_id={message_doc['message_id']}"
                        )
                        return

                    if attempt < retry_count - 1:
                        logger.warning(
                            f"MongoDB 저장 오류 (재시도 {attempt + 1}/{retry_count}): {e}"
                        )
                        await asyncio.sleep(0.1 * (attempt + 1))
                    else:
                        raise

        except Exception as e:
            # DB 저장 실패해도 채팅은 계속 작동 (Fail-Safe)
            logger.error(f"MongoDB 채팅 히스토리 저장 실패: {e}", exc_info=True)
            # ❌ raise 하지 않음 → 채팅 중단 없음

    async def _summarize_conversations(self, messages: list) -> str:
        """
        대화 목록을 LLM으로 요약

        Args:
            messages: LangChain 메시지 리스트 (HumanMessage, AIMessage)

        Returns:
            요약 문자열 (2-3문장)

        예시:
            Input: [
                HumanMessage("포인트는 어떻게 받아요?"),
                AIMessage("걷기, 광고 시청..."),
                HumanMessage("광고는 하루에 몇 번?"),
                AIMessage("최대 20개까지...")
            ]
            Output: "사용자가 포인트 적립 방법과 광고 시청 횟수를 문의했습니다."
        """
        try:
            # 메시지를 텍스트로 변환
            conversation_text = []
            for msg in messages:
                if isinstance(msg, HumanMessage):
                    conversation_text.append(f"사용자: {msg.content}")
                elif isinstance(msg, AIMessage):
                    conversation_text.append(f"AI: {msg.content}")

            full_text = "\n".join(conversation_text)

            # 요약 프롬프트
            prompt = f"""아래 대화 내용을 2-3문장으로 간결하게 요약해주세요.
핵심 주제와 사용자가 궁금해했던 내용을 중심으로 요약합니다.

대화 내용:
{full_text}

요약:"""

            # LLM 호출 (Gemini)
            import google.generativeai as genai

            model = genai.GenerativeModel(self.summary_llm_model)
            response = await asyncio.to_thread(
                model.generate_content,
                prompt,
                generation_config={
                    "temperature": 0.3,  # 안정적인 요약
                    "max_output_tokens": 200,  # 짧게
                },
            )

            summary = response.text.strip()
            logger.debug(f"대화 요약 생성 성공: {summary[:100]}...")
            return summary

        except Exception as e:
            logger.error(f"대화 요약 생성 실패: {e}", exc_info=True)
            # 폴백: 첫 사용자 메시지만 반환
            for msg in messages:
                if isinstance(msg, HumanMessage):
                    return f"사용자가 '{msg.content[:50]}...'에 대해 문의했습니다."
            return "이전 대화 내용"
