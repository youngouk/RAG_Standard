"""
Chat API - 리팩토링된 Three-Layer Architecture

Phase 3: 기존 1,574줄 모놀리식 파일을 3개 레이어로 분리
- Schemas: Pydantic 데이터 검증 모델 (schemas/chat_schemas.py)
- Services: 비즈니스 로직 (services/chat_service.py)
- Routers: FastAPI 라우팅 (routers/chat_router.py)

⚠️ 주의: 기존 검증된 코드를 재구성했습니다. 로직 변경 없음.

## 아키텍처 개선 효과
1. **테스트 가능성**: Service 레이어를 독립적으로 단위 테스트 가능
2. **재사용성**: ChatService를 다른 API에서도 사용 가능
3. **유지보수성**: 관심사 분리로 코드 이해 및 수정 용이
4. **확장성**: 새로운 엔드포인트 추가 시 Router만 수정

## 기존 코드 호환성
- 모든 엔드포인트 경로 동일 (/chat, /chat/session 등)
- Request/Response 스키마 동일
- Rate limiting, 에러 핸들링 동일
- main.py에서 set_dependencies() 호출 방식만 변경 필요
"""

from typing import Any

from .routers import set_chat_service

# 새로운 구조로 re-export
from .routers.chat_router import limiter, router
from .services import ChatService


# 하위 호환성을 위한 set_dependencies() 함수 유지
def set_dependencies(app_modules: dict[str, Any], app_config: dict[str, Any]):
    """
    의존성 주입 (하위 호환성 유지)

    Phase 3: ChatService 인스턴스 생성 및 Router에 주입

    Args:
        app_modules: 애플리케이션 모듈 딕셔너리
        app_config: 설정 딕셔너리
    """
    # ChatService 인스턴스 생성
    chat_service = ChatService(app_modules, app_config)

    # Router에 주입
    set_chat_service(chat_service)


# 기존 import 방식 호환성 유지
__all__ = ["router", "limiter", "set_dependencies"]
