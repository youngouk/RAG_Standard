"""
main.py Startup 검증 테스트 (TDD)

테스트 시나리오:
1. 프로덕션 환경에서 FASTAPI_AUTH_KEY 없이 시작 불가
2. 개발 환경에서 정상 시작
"""

import os

import pytest


class TestMainStartupValidation:
    """main.py Startup 환경 변수 검증 테스트"""

    def setup_method(self) -> None:
        """각 테스트 전에 환경 변수 초기화"""
        for key in ["ENVIRONMENT", "NODE_ENV", "WEAVIATE_URL", "FASTAPI_AUTH_KEY"]:
            os.environ.pop(key, None)

    @pytest.mark.asyncio
    async def test_startup_fails_without_auth_key_in_production(self) -> None:
        """프로덕션 환경에서 FASTAPI_AUTH_KEY 없이 시작 불가"""
        # 프로덕션 지표 설정
        os.environ["WEAVIATE_URL"] = "https://weaviate.example.com"

        # lifespan 함수 import 및 실행 시도
        with pytest.raises(RuntimeError, match="필수.*FASTAPI_AUTH_KEY"):
            from app.lib.environment import validate_required_env_vars

            validate_required_env_vars()

    @pytest.mark.asyncio
    async def test_startup_succeeds_in_development(self) -> None:
        """개발 환경에서 FASTAPI_AUTH_KEY 없어도 시작 가능"""
        # 개발 환경 설정
        os.environ["ENVIRONMENT"] = "development"
        os.environ["WEAVIATE_URL"] = "http://localhost:8080"

        # 경고만 출력하고 정상 시작
        from app.lib.environment import validate_required_env_vars

        validate_required_env_vars()  # 예외 발생하지 않음
