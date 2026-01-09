"""
Error Logging Middleware for FastAPI

모든 HTTP 요청에서 발생하는 에러를 자동으로 캡처하고 구조화된 로그 생성:
- RAGException: 에러 코드와 컨텍스트를 포함한 구조화된 로깅
- 일반 Exception: 트레이스백 자동 캡처 및 상세 로깅
- HTTP 경로, 메서드, 처리 시간 자동 추가
- 미들웨어 자체 에러로 인한 서비스 중단 방지 (Safe Mode)

설계 원칙:
- 최소 침습: 기존 에러 핸들러와 충돌하지 않음
- 안전성 우선: 미들웨어 에러가 서비스에 영향을 주지 않음
- 로깅 강화: 모든 raise된 에러에 대해 트레이스백 자동 캡처
"""

import traceback
from time import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.lib.errors import RAGException
from app.lib.logger import get_logger

logger = get_logger(__name__)


class ErrorLoggingMiddleware(BaseHTTPMiddleware):
    """
    에러 로깅 미들웨어

    모든 HTTP 요청에서 발생하는 에러를 일관된 형식으로 로깅하고,
    에러를 상위(FastAPI 에러 핸들러)로 전파합니다.

    Features:
    - RAGException: 구조화된 에러 정보 전체 로깅
    - 일반 Exception: 트레이스백 자동 캡처
    - 요청 메타데이터: 경로, 메서드, 처리 시간
    - 안전장치: 로깅 실패해도 요청 처리는 정상 진행

    Safe Mode:
    - 미들웨어 내부 에러는 로깅만 하고 무시
    - 원본 에러는 항상 상위로 전파
    - 서비스 중단 방지 보장
    """

    async def dispatch(self, request: Request, call_next):
        """
        요청 인터셉션 및 에러 로깅

        Args:
            request: FastAPI Request 객체
            call_next: 다음 미들웨어 또는 라우트 핸들러

        Returns:
            Response: FastAPI Response 객체

        Raises:
            Exception: 원본 예외를 그대로 상위로 전파
        """
        start_time = time()

        try:
            # 정상 요청 처리
            response = await call_next(request)
            return response

        except RAGException as e:
            # RAGException: 구조화된 정보 모두 로깅
            try:
                duration = time() - start_time

                logger.error(
                    "rag_error_caught",
                    error_code=e.error_code.value,
                    message=e.message,
                    context=e.context,
                    path=request.url.path,
                    method=request.method,
                    duration_ms=f"{duration * 1000:.2f}",
                )
            except Exception as logging_error:
                # 로깅 실패해도 원본 에러는 전파
                try:
                    logger.warning(
                        "error_logging_failed",
                        logging_error=str(logging_error),
                        original_error=str(e),
                    )
                except Exception:
                    # 로깅 완전 실패 - 무시하고 계속
                    pass

            # 원본 에러를 다시 raise하여 FastAPI 에러 핸들러가 처리하도록
            raise

        except Exception as e:
            # 일반 Exception: 트레이스백 자동 캡처
            try:
                duration = time() - start_time

                logger.error(
                    "unhandled_exception_caught",
                    error=str(e),
                    error_type=type(e).__name__,
                    traceback=traceback.format_exc(),
                    path=request.url.path,
                    method=request.method,
                    duration_ms=f"{duration * 1000:.2f}",
                )
            except Exception as logging_error:
                # 로깅 실패해도 원본 에러는 전파
                try:
                    logger.warning(
                        "error_logging_failed",
                        logging_error=str(logging_error),
                        original_error=str(e),
                    )
                except Exception:
                    # 로깅 완전 실패 - 무시하고 계속
                    pass

            # 원본 에러를 다시 raise
            raise
