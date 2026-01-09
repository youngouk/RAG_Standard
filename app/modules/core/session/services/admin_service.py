"""
Admin Service - Admin API용 세션 조회 및 채팅 로그
Phase 4.4: enhanced_session.py에서 추출한 검증된 Admin API 로직
⚠️ 주의: 이 코드는 기존 검증된 로직을 재사용합니다.
"""

import time
from datetime import datetime
from typing import Any

from .....lib.logger import get_logger

logger = get_logger(__name__)


class AdminService:
    """
    Admin API용 세션 및 채팅 로그 조회 서비스

    역할:
    - 전체 세션 목록 조회 (필터링, 페이징)
    - 세션 상세 정보 조회
    - 최근 채팅 로그 조회

    기존 코드 기반: enhanced_session.py의 Admin API 메서드들
    """

    def __init__(self, ttl: int):
        """
        Args:
            ttl: 세션 TTL (초)
        """
        self.ttl = ttl
        logger.info(f"AdminService 초기화: ttl={ttl}s")

    async def get_all_sessions(
        self,
        sessions: dict[str, dict[str, Any]],
        status: str = "all",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        모든 세션 목록 조회
        기존 코드: enhanced_session.py의 get_all_sessions() (L465-538)

        Args:
            sessions: 세션 저장소
            status: 필터 ('all', 'active', 'idle', 'expired')
            limit: 반환할 최대 세션 수
            offset: 건너뛸 세션 수 (페이징)

        Returns:
            {'sessions': list, 'total': int, 'limit': int, 'offset': int}
        """
        current_time = time.time()
        all_sessions = []

        for session_id, session in sessions.items():
            time_since_access = current_time - session["last_accessed"]

            # 상태 결정 (L483-489)
            if time_since_access > self.ttl:
                session_status = "expired"
            elif time_since_access < 300:  # 5분 이내 활동
                session_status = "active"
            else:
                session_status = "idle"

            # 필터링 (L491-493)
            if status != "all" and session_status != status:
                continue

            # 메시지 수 계산 (L495-496)
            message_count = len(session.get("messages_metadata", []))

            # 총 토큰 사용량 계산 (L498-502)
            tokens_used = sum(
                msg.get("tokens_used", 0) for msg in session.get("messages_metadata", [])
            )

            # 총 처리 시간 계산 (L504-508)
            processing_time = sum(
                msg.get("processing_time", 0.0) for msg in session.get("messages_metadata", [])
            )

            session_info = {
                "id": session_id,
                "status": session_status,
                "messageCount": message_count,
                "created": datetime.fromtimestamp(session["created_at"]).isoformat(),
                "lastActivity": datetime.fromtimestamp(session["last_accessed"]).isoformat(),
                "tokensUsed": tokens_used,
                "processingTime": round(processing_time, 2),
                "userAgent": session.get("metadata", {}).get("user_agent"),
                "ipAddress": session.get("metadata", {}).get("ip_address"),
                "userName": session.get("user_name"),
                "topics": session.get("topics", [])[:3],  # 상위 3개 주제만
            }

            all_sessions.append(session_info)

        # 최근 활동 순으로 정렬 (L526-527)
        all_sessions.sort(key=lambda x: x["lastActivity"], reverse=True)

        # 페이징 적용 (L529-531)
        total_count = len(all_sessions)
        paginated_sessions = all_sessions[offset : offset + limit]

        return {
            "sessions": paginated_sessions,
            "total": total_count,
            "limit": limit,
            "offset": offset,
        }

    async def get_session_details(
        self, session_id: str, sessions: dict[str, dict[str, Any]], memories: dict[str, Any]
    ) -> dict[str, Any] | None:
        """
        세션 상세 정보 조회
        기존 코드: enhanced_session.py의 get_session_details() (L540-612)

        Args:
            session_id: 세션 ID
            sessions: 세션 저장소
            memories: 메모리 저장소

        Returns:
            세션 상세 정보 또는 None
        """
        if session_id not in sessions:
            return None

        session = sessions[session_id]
        current_time = time.time()
        time_since_access = current_time - session["last_accessed"]

        # 상태 결정 (L557-563)
        if time_since_access > self.ttl:
            status = "expired"
        elif time_since_access < 300:
            status = "active"
        else:
            status = "idle"

        # 메시지 메타데이터 (L565-567)
        messages_metadata = session.get("messages_metadata", [])
        message_count = len(messages_metadata)

        # 통계 계산 (L569-572)
        total_tokens = sum(msg.get("tokens_used", 0) for msg in messages_metadata)
        total_processing_time = sum(msg.get("processing_time", 0.0) for msg in messages_metadata)
        avg_processing_time = total_processing_time / message_count if message_count > 0 else 0.0

        # 사용된 모델 정보 (L574-580)
        models_used = set()
        for msg in messages_metadata:
            model_info = msg.get("model_info")
            if model_info and isinstance(model_info, dict):
                models_used.add(model_info.get("model_name", "unknown"))

        # 대화 내역 추출 (L581-591)
        chat_history = memories.get(session_id)
        conversation_history = []

        if chat_history:
            for message in chat_history.messages:
                conversation_history.append(
                    {
                        "type": message.type,
                        "content": message.content,
                        "timestamp": None,  # LangChain 메시지에는 타임스탬프가 없음
                    }
                )

        return {
            "id": session_id,
            "status": status,
            "messageCount": message_count,
            "tokensUsed": total_tokens,
            "processingTime": round(total_processing_time, 2),
            "avgProcessingTime": round(avg_processing_time, 2),
            "created": datetime.fromtimestamp(session["created_at"]).isoformat(),
            "lastActivity": datetime.fromtimestamp(session["last_accessed"]).isoformat(),
            "remainingTTL": max(0, self.ttl - time_since_access),
            "userAgent": session.get("metadata", {}).get("user_agent"),
            "ipAddress": session.get("metadata", {}).get("ip_address"),
            "userName": session.get("user_name"),
            "userInfo": session.get("user_info", {}),
            "topics": session.get("topics", []),
            "facts": session.get("facts", {}),
            "modelsUsed": list(models_used),
            "conversationHistory": conversation_history[-10:],  # 최근 10개 메시지만
            "messagesMetadata": messages_metadata[-5:],  # 최근 5개 메시지 메타데이터
        }

    async def get_recent_chats(
        self, sessions: dict[str, dict[str, Any]], limit: int = 20
    ) -> list[dict[str, Any]]:
        """
        최근 채팅 로그 조회
        기존 코드: enhanced_session.py의 get_recent_chats() (L614-668)

        Args:
            sessions: 세션 저장소
            limit: 반환할 최대 채팅 수

        Returns:
            최근 채팅 로그 리스트
        """
        all_chats = []

        # 모든 세션의 메시지 메타데이터 수집 (L626-662)
        for session_id, session in sessions.items():
            messages_metadata = session.get("messages_metadata", [])

            for idx, msg_meta in enumerate(messages_metadata):
                # 고유한 채팅 ID 생성 (L631-632)
                chat_id = f"{session_id}_{idx}"

                # 모델 정보 추출 (L634-639)
                model_info = msg_meta.get("model_info", {})
                if isinstance(model_info, dict):
                    model_name = model_info.get("model_name", "unknown")
                else:
                    model_name = "unknown"

                # 상태 결정 (처리 시간 기반) (L641-648)
                processing_time = msg_meta.get("processing_time", 0.0)
                if processing_time < 1.0:
                    status = "fast"
                elif processing_time < 3.0:
                    status = "normal"
                else:
                    status = "slow"

                chat_log = {
                    "id": chat_id,
                    "chatId": session_id,
                    "message": msg_meta.get("user_message", "")[:100],  # 처음 100자만
                    "timestamp": datetime.fromtimestamp(msg_meta.get("timestamp", 0)).isoformat(),
                    "responseTime": round(processing_time, 2),
                    "source": model_name,
                    "status": status,
                    "keywords": [],  # Phase 2에서 구현
                    "country": None,  # Phase 2에서 구현
                }

                all_chats.append(chat_log)

        # 최근 메시지부터 정렬 (L664-665)
        all_chats.sort(key=lambda x: x["timestamp"], reverse=True)

        # limit만큼 반환 (L667-668)
        return all_chats[:limit]
