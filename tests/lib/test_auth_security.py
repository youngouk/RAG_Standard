"""
API Key 인증 보안 테스트 (TDD)

테스트 시나리오:
1. 프로덕션 환경에서 인증 우회 차단
2. 환경 변수 조작 공격 차단
3. 개발 환경에서 인증 스킵 허용
"""

import os
from unittest.mock import AsyncMock

import pytest
from fastapi import Request


class TestProductionAuthBypass:
    """프로덕션 환경 인증 우회 차단 테스트"""

    def setup_method(self) -> None:
        """각 테스트 전에 환경 변수 초기화"""
        for key in ["ENVIRONMENT", "NODE_ENV", "WEAVIATE_URL", "FASTAPI_AUTH_KEY"]:
            os.environ.pop(key, None)

    @pytest.mark.asyncio
    async def test_block_auth_bypass_in_production(self) -> None:
        """프로덕션 환경에서 API Key 없이 접근 시도 차단"""
        from app.lib.auth import APIKeyAuth

        # 프로덕션 지표 설정
        os.environ["WEAVIATE_URL"] = "https://weaviate.example.com"

        # API Key 없이 인증 시스템 초기화 시도
        with pytest.raises(RuntimeError, match="FASTAPI_AUTH_KEY.*필수"):
            APIKeyAuth(api_key=None)

    @pytest.mark.asyncio
    async def test_block_environment_manipulation_in_middleware(self) -> None:
        """미들웨어에서 환경 변수 조작 공격 차단"""
        from app.lib.auth import APIKeyAuth

        # 공격자가 ENVIRONMENT=development로 설정
        os.environ["ENVIRONMENT"] = "development"
        # 하지만 다른 프로덕션 지표가 존재
        os.environ["WEAVIATE_URL"] = "https://weaviate.example.com"

        # 초기화 시 예외 발생 (프로덕션으로 감지됨)
        with pytest.raises(RuntimeError):
            APIKeyAuth(api_key=None)

    @pytest.mark.asyncio
    async def test_allow_auth_skip_in_development(self) -> None:
        """개발 환경에서 인증 스킵 허용"""
        from app.lib.auth import APIKeyAuth

        # 개발 환경 설정
        os.environ["ENVIRONMENT"] = "development"
        os.environ["WEAVIATE_URL"] = "http://localhost:8080"

        # API Key 없이도 초기화 가능 (경고만 출력)
        auth = APIKeyAuth(api_key=None)

        # Mock request
        request = AsyncMock(spec=Request)
        request.url.path = "/api/test"
        request.method = "GET"

        async def mock_call_next(req: Request) -> AsyncMock:
            return AsyncMock(status_code=200)

        # 인증 스킵되어 정상 처리
        response = await auth.authenticate_request(request, mock_call_next)
        assert response.status_code == 200
