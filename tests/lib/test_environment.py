"""
환경 감지 모듈 테스트 (TDD)

테스트 시나리오:
1. 프로덕션 지표 개별 감지
2. 복합 프로덕션 지표 감지
3. 환경 변수 조작 공격 차단
4. 개발 환경 허용
"""

import os

import pytest


class TestProductionEnvironmentDetection:
    """프로덕션 환경 감지 테스트"""

    def setup_method(self) -> None:
        """각 테스트 전에 환경 변수 초기화"""
        # 모든 관련 환경 변수 제거
        for key in ["ENVIRONMENT", "NODE_ENV", "WEAVIATE_URL", "FASTAPI_AUTH_KEY"]:
            os.environ.pop(key, None)

    def test_detect_production_by_environment_variable(self) -> None:
        """ENVIRONMENT=production으로 프로덕션 감지"""
        from app.lib.environment import is_production_environment

        os.environ["ENVIRONMENT"] = "production"
        assert is_production_environment() is True

    def test_detect_production_by_node_env(self) -> None:
        """NODE_ENV=production으로 프로덕션 감지"""
        from app.lib.environment import is_production_environment

        os.environ["NODE_ENV"] = "production"
        assert is_production_environment() is True

    def test_detect_production_by_https_weaviate(self) -> None:
        """WEAVIATE_URL이 https://로 시작하면 프로덕션 감지"""
        from app.lib.environment import is_production_environment

        os.environ["WEAVIATE_URL"] = "https://weaviate.example.com"
        assert is_production_environment() is True

    def test_detect_production_by_auth_key(self) -> None:
        """FASTAPI_AUTH_KEY 설정 시 프로덕션 감지"""
        from app.lib.environment import is_production_environment

        os.environ["FASTAPI_AUTH_KEY"] = "secure-key-12345"
        assert is_production_environment() is True

    def test_block_environment_manipulation_attack(self) -> None:
        """환경 변수 조작 공격 차단 - 다른 프로덕션 지표 존재 시"""
        from app.lib.environment import is_production_environment

        # 공격자가 ENVIRONMENT=development로 설정
        os.environ["ENVIRONMENT"] = "development"
        # 하지만 다른 프로덕션 지표가 존재
        os.environ["WEAVIATE_URL"] = "https://weaviate.example.com"

        # 프로덕션으로 감지되어야 함 (하나라도 프로덕션 지표가 있으면 프로덕션)
        assert is_production_environment() is True

    def test_allow_development_environment(self) -> None:
        """개발 환경 정상 허용"""
        from app.lib.environment import is_production_environment

        os.environ["ENVIRONMENT"] = "development"
        os.environ["WEAVIATE_URL"] = "http://localhost:8080"

        assert is_production_environment() is False

    def test_default_to_development_when_no_indicators(self) -> None:
        """지표가 없으면 개발 환경으로 간주"""
        from app.lib.environment import is_production_environment

        # 모든 환경 변수 제거됨 (setup_method)
        assert is_production_environment() is False


class TestRequiredEnvValidation:
    """필수 환경 변수 검증 테스트"""

    def setup_method(self) -> None:
        """각 테스트 전에 환경 변수 초기화"""
        for key in ["ENVIRONMENT", "FASTAPI_AUTH_KEY", "GOOGLE_API_KEY", "WEAVIATE_URL"]:
            os.environ.pop(key, None)

    def test_validate_required_vars_in_production(self) -> None:
        """프로덕션 환경에서 필수 변수 검증"""
        from app.lib.environment import validate_required_env_vars

        os.environ["ENVIRONMENT"] = "production"
        # FASTAPI_AUTH_KEY 없음

        with pytest.raises(RuntimeError, match="필수.*FASTAPI_AUTH_KEY"):
            validate_required_env_vars()

    def test_allow_missing_vars_in_development(self) -> None:
        """개발 환경에서 누락 허용 (경고만)"""
        from app.lib.environment import validate_required_env_vars

        os.environ["ENVIRONMENT"] = "development"
        # 필수 변수 없어도 예외 발생하지 않음
        validate_required_env_vars()  # 경고만 출력
