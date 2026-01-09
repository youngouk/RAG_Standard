"""
API Routers - FastAPI 라우팅 레이어

Phase 3.3: chat.py에서 추출한 검증된 라우터 모듈
"""

from .admin_router import router as admin_eval_router
from .admin_router import set_config as set_admin_config
from .admin_router import set_session_module  # ✅ Task 5: 세션 모듈 주입
from .chat_router import router as chat_router
from .chat_router import set_chat_service

__all__ = [
    "chat_router",
    "set_chat_service",
    "admin_eval_router",
    "set_admin_config",
    "set_session_module",  # ✅ Task 5
]
