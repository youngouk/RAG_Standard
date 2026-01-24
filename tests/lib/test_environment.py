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

    def test_auth_key_not_production_indicator(self) -> None:
        """FASTAPI_AUTH_KEY는 프로덕션 지표로 사용하지 않음 (보안 설정 ≠ 환경 지표)

        개발 환경에서도 보안을 위해 AUTH_KEY를 설정할 수 있어야 함.
        AUTH_KEY를 환경 지표로 사용하면 개발 환경이 프로덕션으로 오인되는 버그 발생.
        """
        from app.lib.environment import is_production_environment

        os.environ["FASTAPI_AUTH_KEY"] = "secure-key-12345"
        # AUTH_KEY만으로는 프로덕션으로 감지되지 않음
        assert is_production_environment() is False

    def test_explicit_environment_variable_takes_priority(self) -> None:
        """명시적 ENVIRONMENT 환경변수가 다른 지표보다 우선순위를 가짐

        ENVIRONMENT=development가 설정되면 다른 프로덕션 지표(HTTPS URL)보다 우선.
        이는 의도적인 설계로, 개발자가 명시적으로 환경을 지정할 수 있게 함.
        """
        from app.lib.environment import is_production_environment

        # ENVIRONMENT=development를 명시적으로 설정
        os.environ["ENVIRONMENT"] = "development"
        # 인프라는 HTTPS를 사용 (프로덕션 인프라에서 개발 테스트하는 경우)
        os.environ["WEAVIATE_URL"] = "https://weaviate.example.com"

        # 명시적 ENVIRONMENT 설정이 우선되어 개발 환경으로 판단
        assert is_production_environment() is False

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
