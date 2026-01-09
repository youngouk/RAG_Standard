"""환경 변수 검증 테스트"""

import pytest

from app.lib.config_validator import (
    ConfigValidationError,
    get_env_bool,
    get_env_int,
    get_env_url,
)


class TestConfigValidator:
    """환경 변수 검증기 테스트"""

    def test_get_env_int_valid(self, monkeypatch):
        """정수 파싱 성공"""
        monkeypatch.setenv("TEST_PORT", "8080")
        assert get_env_int("TEST_PORT") == 8080

    def test_get_env_int_with_default(self, monkeypatch):
        """기본값 반환"""
        monkeypatch.delenv("TEST_PORT", raising=False)
        assert get_env_int("TEST_PORT", default=3000) == 3000

    def test_get_env_int_invalid_raises_error(self, monkeypatch):
        """잘못된 형식은 에러"""
        monkeypatch.setenv("TEST_PORT", "invalid")
        with pytest.raises(ConfigValidationError) as exc_info:
            get_env_int("TEST_PORT")
        assert "TEST_PORT" in str(exc_info.value)
        assert "invalid" in str(exc_info.value).lower()

    def test_get_env_bool_true_values(self, monkeypatch):
        """True 값들"""
        for val in ["true", "True", "1", "yes", "YES"]:
            monkeypatch.setenv("TEST_FLAG", val)
            assert get_env_bool("TEST_FLAG") is True

    def test_get_env_bool_false_values(self, monkeypatch):
        """False 값들"""
        for val in ["false", "False", "0", "no", "NO"]:
            monkeypatch.setenv("TEST_FLAG", val)
            assert get_env_bool("TEST_FLAG") is False

    def test_get_env_url_validates_scheme(self, monkeypatch):
        """URL 스킴 검증"""
        monkeypatch.setenv("TEST_URL", "https://example.com")
        assert get_env_url("TEST_URL") == "https://example.com"

        monkeypatch.setenv("TEST_URL", "invalid-url")
        with pytest.raises(ConfigValidationError):
            get_env_url("TEST_URL")

    def test_get_env_int_range_validation(self, monkeypatch):
        """정수 범위 검증"""
        monkeypatch.setenv("TEST_TIMEOUT", "30")
        assert get_env_int("TEST_TIMEOUT", min_value=1, max_value=60) == 30

        monkeypatch.setenv("TEST_TIMEOUT", "100")
        with pytest.raises(ConfigValidationError) as exc_info:
            get_env_int("TEST_TIMEOUT", max_value=60)
        assert "최대값" in str(exc_info.value)

    def test_get_env_url_require_https(self, monkeypatch):
        """HTTPS 필수 검증"""
        monkeypatch.setenv("TEST_SECURE_URL", "http://example.com")
        with pytest.raises(ConfigValidationError) as exc_info:
            get_env_url("TEST_SECURE_URL", require_https=True)
        assert "HTTPS" in str(exc_info.value)
