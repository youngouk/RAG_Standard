"""
API Key 인증 모듈

FastAPI 애플리케이션을 위한 간단하고 효과적인 API Key 인증 시스템을 제공합니다.

주요 기능:
- 환경 변수 기반 API Key 관리
- 미들웨어를 통한 전역 인증 적용
- Swagger UI 통합 (Authorize 버튼)
- 공개 엔드포인트 제외 기능

사용 예시:
    from app.lib.auth import APIKeyAuth

    auth = APIKeyAuth()

    # 미들웨어로 전역 적용
    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        return await auth.authenticate_request(request, call_next)

    # OpenAPI 스키마 수정
    app.openapi = auth.get_custom_openapi_func(app)
"""

import os
import secrets
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from .logger import get_logger

logger = get_logger(__name__)


class APIKeyAuth:
    """
    API Key 기반 인증 시스템

    Attributes:
        api_key (str): 환경 변수에서 로드한 유효한 API Key
        protected_paths (List[str]): 인증이 필요한 경로 prefix 목록
        public_paths (List[str]): 인증이 불필요한 공개 경로 목록
    """

    def __init__(
        self,
        api_key: str | None = None,
        protected_paths: list[str] | None = None,
        public_paths: list[str] | None = None,
    ):
        """
        API Key 인증 시스템 초기화

        Args:
            api_key: API Key (기본값: 환경 변수 FASTAPI_AUTH_KEY)
            protected_paths: 보호할 경로 prefix (기본값: ["/api/"])
            public_paths: 공개 경로 (기본값: ["/docs", "/redoc", "/openapi.json", "/health", "/"])

        Raises:
            RuntimeError: 프로덕션 환경에서 API Key 미설정 시
        """
        # 다층 환경 감지
        from .environment import is_production_environment

        is_production = is_production_environment()

        # API Key 로드 (환경 변수 우선)
        self.api_key = api_key or os.getenv("FASTAPI_AUTH_KEY")

        # 프로덕션 환경에서 API Key 필수 검증
        if not self.api_key:
            if is_production:
                # 프로덕션: 즉시 중단
                error_msg = (
                    "FASTAPI_AUTH_KEY 환경 변수가 설정되지 않았습니다. "
                    "프로덕션 환경에서는 필수입니다. "
                    ".env 파일에 'FASTAPI_AUTH_KEY=your-secret-key'를 추가하세요."
                )
                suggestion_msg = (
                    "해결 방법:\n"
                    "1. 안전한 API Key 생성: openssl rand -hex 32\n"
                    "2. .env 파일에 추가: FASTAPI_AUTH_KEY=<생성된 키>\n"
                    "3. 또는 APIKeyAuth(api_key='...') 파라미터로 직접 전달\n"
                    "4. 프로덕션 배포 시 환경 변수가 안전하게 주입되는지 확인하세요"
                )
                logger.critical(error_msg)
                logger.critical(suggestion_msg)
                raise RuntimeError(f"{error_msg}\n{suggestion_msg}")
            else:
                # 개발 환경: 경고만 출력
                logger.warning(
                    "FASTAPI_AUTH_KEY가 설정되지 않았습니다. 인증이 비활성화됩니다.",
                    extra={
                        "environment": "개발",
                        "suggestion": (
                            "프로덕션 환경에서는 반드시 FASTAPI_AUTH_KEY를 설정하세요. "
                            "안전한 키 생성: openssl rand -hex 32"
                        ),
                    },
                )
        else:
            # API Key 설정 완료
            logger.info(
                "API Key 인증 활성화",
                extra={"environment": "프로덕션" if is_production else "개발"},
            )

        # 보호할 경로 설정 (기본값: /api/로 시작하는 모든 경로)
        self.protected_paths = protected_paths or ["/api/"]

        # 공개 경로 설정 (인증 불필요)
        # 주의: "/" 는 모든 경로와 매칭되므로 제거하고 is_public_path에서 특별 처리
        self.public_paths = public_paths or [
            "/docs",  # Swagger UI
            "/redoc",  # ReDoc
            "/openapi.json",  # OpenAPI 스키마
            "/health",  # Health check
        ]

        logger.info("🔐 API Key 인증 초기화 완료")
        logger.info(f"   - 보호 경로: {self.protected_paths}")
        logger.info(f"   - 공개 경로: {self.public_paths}")

    def is_public_path(self, path: str) -> bool:
        """
        요청 경로가 공개 경로인지 확인

        Args:
            path: 요청 경로

        Returns:
            공개 경로 여부
        """
        # 루트 경로("/")는 정확히 매칭 (모든 경로가 "/"로 시작하므로 특별 처리 필요)
        if path == "/":
            return True

        # 나머지 공개 경로는 prefix 매칭
        return any(path.startswith(public) for public in self.public_paths)

    def is_protected_path(self, path: str) -> bool:
        """
        요청 경로가 보호 경로인지 확인

        Args:
            path: 요청 경로

        Returns:
            보호 경로 여부
        """
        return any(path.startswith(protected) for protected in self.protected_paths)

    async def authenticate_request(self, request: Request, call_next: Callable[..., Any]) -> Any:
        """
        HTTP 요청 인증 미들웨어

        동작:
        1. 공개 경로는 인증 없이 통과
        2. CORS preflight (OPTIONS) 요청은 인증 제외
        3. 보호 경로는 API Key 검증
        4. API Key가 없거나 틀리면 401 에러

        Args:
            request: FastAPI Request 객체
            call_next: 다음 미들웨어/핸들러

        Returns:
            Response 객체
        """
        path = request.url.path

        # 1. 공개 경로는 인증 불필요
        if self.is_public_path(path):
            return await call_next(request)

        # 2. CORS preflight (OPTIONS) 요청은 인증 제외
        # 브라우저가 실제 요청 전에 보내는 사전 확인 요청이므로 인증 불필요
        if request.method == "OPTIONS":
            return await call_next(request)

        # 2. API Key가 설정되지 않았으면 인증 스킵 (개발 환경만 허용)
        if not self.api_key:
            # ✅ 다층 환경 감지로 우회 차단
            from .environment import is_production_environment

            if is_production_environment():
                # 프로덕션 환경에서는 절대 허용하지 않음
                logger.critical(
                    "프로덕션 환경에서 API Key 누락 감지",
                    extra={
                        "path": path,
                        "suggestion": (
                            "환경 변수 조작 공격이 감지되었습니다. "
                            "프로덕션 지표가 존재하지만 FASTAPI_AUTH_KEY가 설정되지 않았습니다. "
                            "즉시 FASTAPI_AUTH_KEY를 설정하세요."
                        ),
                    },
                )
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": "서버 인증 설정 오류",
                        "message": "프로덕션 환경에서 API 인증이 구성되지 않았습니다",
                        "suggestion": (
                            "시스템 관리자에게 문의하세요. "
                            "관리자: FASTAPI_AUTH_KEY 환경 변수를 설정해야 합니다 "
                            "(안전한 키 생성: openssl rand -hex 32)"
                        ),
                        "docs": "https://github.com/youngouk/RAG_Standard#authentication",
                    },
                )

            # 개발 환경에서만 허용
            logger.warning(
                "FASTAPI_AUTH_KEY 미설정으로 인증 스킵",
                extra={
                    "path": path,
                    "environment": "개발",
                    "suggestion": "개발 환경에서만 허용되는 동작입니다. 프로덕션에서는 차단됩니다.",
                },
            )
            return await call_next(request)

        # 3. 보호 경로는 API Key 검증
        if self.is_protected_path(path):
            # 헤더에서 API Key 추출
            api_key = request.headers.get("X-API-Key")

            # API Key 검증
            if not api_key:
                client_ip = request.client.host if request.client else "unknown"
                logger.warning(
                    "API Key 누락",
                    extra={
                        "path": path,
                        "client_ip": client_ip,
                        "suggestion": (
                            "X-API-Key 헤더에 API Key를 포함하세요. "
                            "Swagger UI에서 테스트 시: 우측 상단 'Authorize' 버튼 클릭 후 키 입력"
                        ),
                    },
                )
                return JSONResponse(
                    status_code=401,
                    content={
                        "detail": {
                            "error": "인증 실패",
                            "message": "API Key가 필요합니다",
                            "suggestion": (
                                "X-API-Key 헤더에 유효한 API Key를 포함하세요. "
                                ".env 파일의 FASTAPI_AUTH_KEY 값을 사용하세요. "
                                "Swagger UI 사용 시: 우측 상단 'Authorize' 버튼 클릭 후 키 입력"
                            ),
                            "docs": "https://github.com/youngouk/RAG_Standard#authentication",
                        },
                    },
                )

            # 타이밍 공격 방지: secrets.compare_digest 사용
            if not secrets.compare_digest(api_key, self.api_key):
                client_ip = request.client.host if request.client else "unknown"
                logger.warning(
                    "잘못된 API Key",
                    extra={
                        "path": path,
                        "client_ip": client_ip,
                        "suggestion": (
                            ".env 파일의 FASTAPI_AUTH_KEY 값과 일치하는지 확인하세요. "
                            "공백이나 줄바꿈 문자가 포함되지 않았는지 확인하세요."
                        ),
                    },
                )
                return JSONResponse(
                    status_code=401,
                    content={
                        "detail": {
                            "error": "인증 실패",
                            "message": "제공된 API Key가 유효하지 않습니다",
                            "suggestion": (
                                ".env 파일의 FASTAPI_AUTH_KEY 값과 일치하는지 확인하세요. "
                                "공백이나 줄바꿈 문자가 포함되지 않았는지 확인하세요. "
                                "키가 없다면 생성하세요: openssl rand -hex 32"
                            ),
                            "docs": "https://github.com/youngouk/RAG_Standard#authentication",
                        },
                    },
                )

            # 인증 성공
            logger.debug(f"✅ API Key 인증 성공: {path}")

        # 4. 요청 처리
        return await call_next(request)

    def get_custom_openapi_func(self, app: FastAPI) -> Callable[[], Any]:
        """
        Swagger UI에 API Key 입력 필드를 추가하는 커스텀 OpenAPI 함수 생성

        사용법:
            app.openapi = auth.get_custom_openapi_func(app)

        Args:
            app: FastAPI 애플리케이션 인스턴스

        Returns:
            커스텀 openapi 함수
        """

        def custom_openapi() -> Any:
            # 이미 생성된 스키마가 있으면 재사용
            if app.openapi_schema:
                return app.openapi_schema

            # OpenAPI 스키마 생성
            openapi_schema = get_openapi(
                title=app.title,
                version=app.version,
                description=app.description,
                routes=app.routes,
            )

            # API Key 인증 스키마 추가
            openapi_schema["components"]["securitySchemes"] = {
                "APIKeyHeader": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key",
                    "description": "FastAPI 인증을 위한 키입니다. 환경 변수 FASTAPI_AUTH_KEY에 설정된 값을 입력하세요.",
                }
            }

            # 보호 경로에만 보안 요구사항 적용
            for path in openapi_schema["paths"]:
                # 보호 경로인지 확인
                if self.is_protected_path(path):
                    for method in openapi_schema["paths"][path]:
                        # HTTP 메서드인지 확인 (parameters, summary 등 제외)
                        if method in ["get", "post", "put", "delete", "patch", "options", "head"]:
                            # security 필드가 없으면 추가
                            if "security" not in openapi_schema["paths"][path][method]:
                                openapi_schema["paths"][path][method]["security"] = []

                            # API Key 요구사항 추가
                            openapi_schema["paths"][path][method]["security"].append(
                                {"APIKeyHeader": []}
                            )

            # 스키마 캐싱
            app.openapi_schema = openapi_schema
            return app.openapi_schema

        return custom_openapi


# 전역 인스턴스 (싱글톤 패턴)
_auth_instance = None


def get_api_key_auth() -> APIKeyAuth:
    """
    전역 APIKeyAuth 인스턴스 반환 (싱글톤)

    Returns:
        APIKeyAuth 인스턴스
    """
    global _auth_instance

    if _auth_instance is None:
        _auth_instance = APIKeyAuth()

    return _auth_instance


def get_api_key(request: Request) -> str:
    """
    FastAPI Depends용 API Key 검증 함수

    헤더에서 X-API-Key를 추출하고 검증합니다.

    Args:
        request: FastAPI Request 객체

    Returns:
        유효한 API Key

    Raises:
        HTTPException: API Key가 없거나 유효하지 않을 때
    """
    # 전역 auth 인스턴스 가져오기
    auth = get_api_key_auth()

    # API Key 추출
    api_key = request.headers.get("X-API-Key")

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "인증 실패",
                "message": "API Key가 필요합니다",
                "suggestion": (
                    "X-API-Key 헤더에 유효한 API Key를 포함하세요. "
                    ".env 파일의 FASTAPI_AUTH_KEY 값을 사용하세요"
                ),
                "docs": "https://github.com/youngouk/RAG_Standard#authentication",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    # API Key가 설정되지 않았으면 (개발 환경) 검증 스킵
    if not auth.api_key:
        return str(api_key)  # 개발 환경용

    # API Key 검증 (타이밍 공격 방지)
    if not secrets.compare_digest(api_key, auth.api_key):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "인증 실패",
                "message": "제공된 API Key가 유효하지 않습니다",
                "suggestion": (
                    ".env 파일의 FASTAPI_AUTH_KEY 값과 일치하는지 확인하세요. "
                    "공백이나 줄바꿈 문자가 포함되지 않았는지 확인하세요"
                ),
                "docs": "https://github.com/youngouk/RAG_Standard#authentication",
            },
        )

    return str(api_key)
