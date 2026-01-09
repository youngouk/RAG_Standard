"""
Session Module - Service-Based Architecture

Phase 1.5: Enhanced Session 구조 개선
- facade.py: EnhancedSessionModule (Facade Pattern)
- services/: 실제 비즈니스 로직 구현
  - session_service.py: 세션 CRUD + 통계 + DB 연동
  - memory_service.py: LangChain 메모리 관리
  - admin_service.py: Admin API 로직
- schemas/: 데이터 모델 정의

Export:
- EnhancedSessionModule: Facade 인터페이스 (외부에서 사용)
"""

from .facade import CleanupService, EnhancedSessionModule

__all__ = [
    "EnhancedSessionModule",
    "CleanupService",
]
