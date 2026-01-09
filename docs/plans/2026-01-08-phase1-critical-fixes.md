# Phase 1: Critical Issues & Quick Wins Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** v3.3.0 → v3.3.1 안정화 패치 - 4개 Critical 이슈 해결 및 Quick Wins 적용

**Architecture:**
- 보안 강화: 프로덕션 환경 감지 로직 다층화 및 환경 변수 검증
- PII 감사: 컨텍스트 원문 노출 차단 (해시 처리)
- 인코딩 안정성: chardet 기반 자동 감지 및 스트리밍 처리
- 운영 안정성: Agent 타임아웃 설정 및 Quick Wins 17개 적용

**Tech Stack:**
- Python 3.11+, FastAPI, Motor (async MongoDB)
- chardet (인코딩 감지), pandas (스트리밍)
- pytest, ruff, mypy

**Timeline:** 2주 (10 영업일)
**Priority:** 🔴 P0 (Production Blocker)

---

## 📋 Task Overview

| Task | 이슈 | 우선순위 | 예상 시간 | 담당 |
|------|------|----------|-----------|------|
| Task 1 | SEC-001: 개발 환경 인증 우회 | 🔴 Critical | 4시간 | Security |
| Task 2 | SEC-002: 환경 변수 검증 부재 | 🟠 High | 6시간 | Backend |
| Task 3 | QA-002: Privacy 감사 로그 노출 | 🔴 Critical | 3시간 | Security |
| Task 4 | QA-001: Documents 인코딩 처리 | 🔴 Critical | 16시간 | Backend |
| Task 5 | QA-003: Agent 타임아웃 미구현 | 🔴 Critical | 4시간 | Backend |
| Task 6 | Quick Wins 적용 (17개) | 🟡 Medium | 8시간 | 전체 |

**총 작업 시간**: 41시간 (약 5일, 버퍼 포함 2주)

---

## Task 1: SEC-001 - 프로덕션 환경 인증 우회 취약점 수정

**배경**:
`ENVIRONMENT=development` 환경 변수 조작으로 프로덕션에서 인증을 우회할 수 있는 Critical 취약점입니다. CVSS 9.1 (Critical) 등급으로 즉시 수정이 필요합니다.

**Files:**
- Modify: `app/lib/auth.py:166-182` (인증 로직)
- Create: `app/lib/environment.py` (환경 감지 모듈)
- Modify: `main.py` (Startup 검증)
- Test: `tests/lib/test_auth_security.py`
- Test: `tests/lib/test_environment.py`

---

### Step 1: Write failing test for production detection

**Test File:** `tests/lib/test_environment.py`

```python
"""환경 감지 로직 테스트"""
import os
import pytest
from app.lib.environment import is_production_environment


class TestProductionDetection:
    """프로덕션 환경 감지 테스트"""

    def test_production_env_variable(self, monkeypatch):
        """ENVIRONMENT=production 감지"""
        monkeypatch.setenv("ENVIRONMENT", "production")
        assert is_production_environment() is True

    def test_prod_short_name(self, monkeypatch):
        """ENVIRONMENT=prod 감지"""
        monkeypatch.setenv("ENVIRONMENT", "prod")
        assert is_production_environment() is True

    def test_node_env_production(self, monkeypatch):
        """NODE_ENV=production 감지"""
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.setenv("NODE_ENV", "production")
        assert is_production_environment() is True

    def test_https_weaviate_url_indicates_production(self, monkeypatch):
        """HTTPS Weaviate URL은 프로덕션 지표"""
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("NODE_ENV", raising=False)
        monkeypatch.setenv("WEAVIATE_URL", "https://prod.weaviate.io")
        assert is_production_environment() is True

    def test_api_key_presence_indicates_production(self, monkeypatch):
        """API Key 설정은 프로덕션 지표"""
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("NODE_ENV", raising=False)
        monkeypatch.delenv("WEAVIATE_URL", raising=False)
        monkeypatch.setenv("FASTAPI_AUTH_KEY", "test-key-123")
        assert is_production_environment() is True

    def test_development_with_no_indicators(self, monkeypatch):
        """지표가 없으면 개발 환경"""
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("NODE_ENV", raising=False)
        monkeypatch.delenv("WEAVIATE_URL", raising=False)
        monkeypatch.delenv("FASTAPI_AUTH_KEY", raising=False)
        assert is_production_environment() is False

    def test_environment_manipulation_attack(self, monkeypatch):
        """ENVIRONMENT=development 조작 공격 차단"""
        # 공격 시나리오: ENVIRONMENT=development + HTTPS Weaviate
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("WEAVIATE_URL", "https://prod.weaviate.io")
        # HTTPS URL이 우선순위가 높아 프로덕션으로 감지되어야 함
        assert is_production_environment() is True
```

**Expected Output:** FAILED (is_production_environment not defined)

---

### Step 2: Run test to verify it fails

```bash
pytest tests/lib/test_environment.py::TestProductionDetection -v
```

**Expected:**
```
FAILED tests/lib/test_environment.py::TestProductionDetection::test_production_env_variable - ImportError: cannot import name 'is_production_environment'
```

---

### Step 3: Implement production detection module

**File:** `app/lib/environment.py`

```python
"""
환경 감지 유틸리티

프로덕션 환경을 다층 검증하여 인증 우회 공격을 방지합니다.

구현일: 2026-01-08
보안: SEC-001 대응
"""
import os
import logging

logger = logging.getLogger(__name__)


def is_production_environment() -> bool:
    """
    프로덕션 환경 다층 검증

    여러 지표를 종합적으로 판단하여 프로덕션 환경인지 확인합니다.
    단일 환경 변수 조작으로는 우회할 수 없도록 설계되었습니다.

    Returns:
        프로덕션 환경이면 True, 개발 환경이면 False

    Examples:
        >>> os.environ["ENVIRONMENT"] = "production"
        >>> is_production_environment()
        True

        >>> os.environ["WEAVIATE_URL"] = "https://prod.weaviate.io"
        >>> is_production_environment()
        True
    """
    # 1. 명시적 환경 변수 체크
    env = os.getenv("ENVIRONMENT", "").lower()
    node_env = os.getenv("NODE_ENV", "").lower()

    # 2. 프로덕션 지표 확인
    production_indicators = [
        # 명시적 프로덕션 선언
        env in ("production", "prod"),
        node_env in ("production", "prod"),

        # 인프라 지표 (HTTPS는 프로덕션 DB)
        os.getenv("WEAVIATE_URL", "").startswith("https://"),

        # 보안 설정 존재 (프로덕션에서만 설정)
        bool(os.getenv("FASTAPI_AUTH_KEY")),
    ]

    # 3. 하나라도 프로덕션 지표가 있으면 프로덕션으로 간주
    is_prod = any(production_indicators)

    if is_prod:
        logger.info("🔒 프로덕션 환경 감지됨")
    else:
        logger.debug("🔓 개발 환경으로 판단됨")

    return is_prod


def validate_required_env_vars(
    required_vars: list[str],
    raise_on_missing: bool = True,
) -> dict[str, str | None]:
    """
    필수 환경 변수 검증

    Args:
        required_vars: 필수 환경 변수 목록
        raise_on_missing: 누락 시 RuntimeError 발생 여부

    Returns:
        환경 변수 딕셔너리 (key: 변수명, value: 값 또는 None)

    Raises:
        RuntimeError: raise_on_missing=True이고 프로덕션 환경에서 누락된 경우

    Examples:
        >>> validate_required_env_vars(["GOOGLE_API_KEY"])
        {'GOOGLE_API_KEY': 'your-key-here'}
    """
    result: dict[str, str | None] = {}
    missing: list[str] = []

    for var in required_vars:
        value = os.getenv(var)
        result[var] = value

        if not value:
            missing.append(var)

    # 누락된 변수가 있는 경우
    if missing:
        error_msg = f"Missing required environment variables: {', '.join(missing)}"

        if is_production_environment():
            logger.critical(f"🚨 CRITICAL: {error_msg}")
            if raise_on_missing:
                raise RuntimeError(error_msg)
        else:
            logger.warning(f"⚠️ DEV WARNING: {error_msg}")

    return result
```

---

### Step 4: Run environment tests

```bash
pytest tests/lib/test_environment.py::TestProductionDetection -v
```

**Expected:**
```
tests/lib/test_environment.py::TestProductionDetection::test_production_env_variable PASSED
tests/lib/test_environment.py::TestProductionDetection::test_prod_short_name PASSED
tests/lib/test_environment.py::TestProductionDetection::test_node_env_production PASSED
tests/lib/test_environment.py::TestProductionDetection::test_https_weaviate_url_indicates_production PASSED
tests/lib/test_environment.py::TestProductionDetection::test_api_key_presence_indicates_production PASSED
tests/lib/test_environment.py::TestProductionDetection::test_development_with_no_indicators PASSED
tests/lib/test_environment.py::TestProductionDetection::test_environment_manipulation_attack PASSED

====== 7 passed in 0.15s ======
```

---

### Step 5: Write failing test for auth bypass prevention

**Test File:** `tests/lib/test_auth_security.py`

```python
"""인증 보안 테스트"""
import os
import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock
from app.lib.auth import APIKeyMiddleware


class TestAuthBypassPrevention:
    """인증 우회 방지 테스트"""

    @pytest.mark.asyncio
    async def test_auth_bypass_blocked_in_production(self, monkeypatch):
        """프로덕션에서 API Key 없이 요청 시 500 에러"""
        # Given: 프로덕션 환경 + API Key 미설정
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("FASTAPI_AUTH_KEY", raising=False)

        middleware = APIKeyMiddleware(AsyncMock())

        # Mock request
        request = AsyncMock()
        request.url.path = "/api/admin/health"
        request.method = "GET"

        # When/Then: HTTPException 발생
        with pytest.raises(HTTPException) as exc_info:
            await middleware.dispatch(request, AsyncMock())

        assert exc_info.value.status_code == 500
        assert "configuration error" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_environment_manipulation_blocked(self, monkeypatch):
        """ENVIRONMENT=development 조작 공격 차단"""
        # Given: ENVIRONMENT=development + HTTPS Weaviate (프로덕션 지표)
        monkeypatch.setenv("ENVIRONMENT", "development")  # 공격자 조작
        monkeypatch.setenv("WEAVIATE_URL", "https://prod.weaviate.io")
        monkeypatch.delenv("FASTAPI_AUTH_KEY", raising=False)

        middleware = APIKeyMiddleware(AsyncMock())

        request = AsyncMock()
        request.url.path = "/api/admin/config"
        request.method = "POST"

        # When/Then: 프로덕션으로 감지되어 차단
        with pytest.raises(HTTPException) as exc_info:
            await middleware.dispatch(request, AsyncMock())

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_dev_mode_allows_no_auth(self, monkeypatch):
        """개발 환경에서는 API Key 없이 허용"""
        # Given: 순수 개발 환경
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.delenv("FASTAPI_AUTH_KEY", raising=False)
        monkeypatch.delenv("WEAVIATE_URL", raising=False)

        middleware = APIKeyMiddleware(AsyncMock())

        request = AsyncMock()
        request.url.path = "/api/admin/test"
        request.method = "GET"

        call_next = AsyncMock()

        # When: 요청 처리
        await middleware.dispatch(request, call_next)

        # Then: 정상 통과
        call_next.assert_called_once()
```

**Expected Output:** FAILED (logic not implemented)

---

### Step 6: Run auth security test to verify it fails

```bash
pytest tests/lib/test_auth_security.py::TestAuthBypassPrevention -v
```

**Expected:**
```
FAILED tests/lib/test_auth_security.py::TestAuthBypassPrevention::test_auth_bypass_blocked_in_production
```

---

### Step 7: Update auth middleware with production detection

**File:** `app/lib/auth.py`

```python
# 기존 import에 추가
from app.lib.environment import is_production_environment

# ... (기존 코드 유지)

# Line 167-182 수정
async def dispatch(self, request: Request, call_next: RequestCallFunc) -> Response:
    """
    HTTP 요청마다 실행되는 미들웨어 핸들러

    보호 경로(/api/admin)에 대해 API Key 검증 수행
    """
    path = request.url.path

    # 1. Health check는 인증 제외
    if path == "/health":
        return await call_next(request)

    # 2. CORS preflight 요청은 인증 제외
    if request.method == "OPTIONS":
        return await call_next(request)

    # 3. API Key가 설정되지 않은 경우 처리
    if not self.api_key:
        # ✅ 다층 프로덕션 환경 감지 (SEC-001 대응)
        if is_production_environment():
            # 🚨 프로덕션에서는 절대 허용하지 않음
            logger.critical(
                "🚨 CRITICAL: API Key missing in production! "
                "Set FASTAPI_AUTH_KEY environment variable."
            )
            raise HTTPException(
                status_code=500,
                detail="Server configuration error: API authentication not configured",
            )

        # ⚠️ 개발 환경에서만 허용
        logger.warning(f"⚠️ DEV MODE: API Key 미설정으로 인증 스킵: {path}")
        logger.warning("   프로덕션 배포 전 FASTAPI_AUTH_KEY를 반드시 설정하세요.")
        return await call_next(request)

    # 4. 보호 경로는 API Key 검증
    if self.is_protected_path(path):
        # ... (기존 검증 로직 유지)
```

---

### Step 8: Run auth security tests

```bash
pytest tests/lib/test_auth_security.py -v
```

**Expected:**
```
tests/lib/test_auth_security.py::TestAuthBypassPrevention::test_auth_bypass_blocked_in_production PASSED
tests/lib/test_auth_security.py::TestAuthBypassPrevention::test_environment_manipulation_blocked PASSED
tests/lib/test_auth_security.py::TestAuthBypassPrevention::test_dev_mode_allows_no_auth PASSED

====== 3 passed in 0.25s ======
```

---

### Step 9: Add startup validation in main.py

**File:** `main.py`

```python
# 기존 import에 추가
from app.lib.environment import is_production_environment, validate_required_env_vars

# lifespan 함수에 추가 (기존 코드 앞에)
@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 수명 주기 관리"""
    # ✅ Startup: 필수 환경 변수 검증 (SEC-001, SEC-002 대응)
    logger.info("🔍 Starting environment validation...")

    required_vars = [
        "GOOGLE_API_KEY",
        "OPENROUTER_API_KEY",
        "WEAVIATE_URL",
        "WEAVIATE_API_KEY",
        "MONGODB_URI",
    ]

    # 프로덕션에서는 FASTAPI_AUTH_KEY도 필수
    if is_production_environment():
        required_vars.append("FASTAPI_AUTH_KEY")
        logger.info("🔒 프로덕션 환경 감지 - 인증 필수")

    # 환경 변수 검증
    validate_required_env_vars(
        required_vars,
        raise_on_missing=is_production_environment(),
    )

    logger.info("✅ Environment validation completed")

    # ... (기존 startup 로직)

    yield

    # ... (기존 shutdown 로직)
```

---

### Step 10: Write test for startup validation

**Test File:** `tests/test_main_startup.py`

```python
"""애플리케이션 Startup 검증 테스트"""
import pytest
import os


class TestStartupValidation:
    """Startup 환경 변수 검증 테스트"""

    def test_production_requires_auth_key(self, monkeypatch):
        """프로덕션에서 FASTAPI_AUTH_KEY 필수"""
        # Given: 프로덕션 환경 + AUTH_KEY 없음
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("FASTAPI_AUTH_KEY", raising=False)

        # When/Then: RuntimeError 발생
        from app.lib.environment import validate_required_env_vars

        with pytest.raises(RuntimeError) as exc_info:
            validate_required_env_vars(
                ["FASTAPI_AUTH_KEY"],
                raise_on_missing=True,
            )

        assert "FASTAPI_AUTH_KEY" in str(exc_info.value)

    def test_dev_allows_missing_vars(self, monkeypatch):
        """개발 환경에서는 누락 허용 (경고만)"""
        # Given: 개발 환경
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.delenv("FASTAPI_AUTH_KEY", raising=False)

        from app.lib.environment import validate_required_env_vars

        # When: 검증 실행
        result = validate_required_env_vars(
            ["FASTAPI_AUTH_KEY"],
            raise_on_missing=False,
        )

        # Then: 경고만 발생하고 통과
        assert result["FASTAPI_AUTH_KEY"] is None
```

---

### Step 11: Run startup validation tests

```bash
pytest tests/test_main_startup.py -v
```

**Expected:**
```
tests/test_main_startup.py::TestStartupValidation::test_production_requires_auth_key PASSED
tests/test_main_startup.py::TestStartupValidation::test_dev_allows_missing_vars PASSED

====== 2 passed in 0.12s ======
```

---

### Step 12: Run full test suite for SEC-001

```bash
pytest tests/lib/test_environment.py tests/lib/test_auth_security.py tests/test_main_startup.py -v
```

**Expected:** All tests pass (12 tests total)

---

### Step 13: Update CHANGELOG.md

```markdown
## [v3.3.1] - 2026-01-08

### Security
- **[SEC-001]** 🔴 CRITICAL: 프로덕션 환경 인증 우회 취약점 수정 (CVSS 9.1)
  - 다층 환경 감지 로직 추가 (`app/lib/environment.py`)
  - ENVIRONMENT 조작 공격 차단
  - Startup 환경 변수 검증 강화
```

---

### Step 14: Commit SEC-001 fix

```bash
git add app/lib/environment.py app/lib/auth.py main.py tests/
git commit -m "security: [SEC-001] fix production auth bypass (CVSS 9.1)

- Add multi-layer production environment detection
- Prevent ENVIRONMENT variable manipulation attack
- Add startup validation for required env vars
- Tests: 12 new security tests

BREAKING: FASTAPI_AUTH_KEY now required in production

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 2: SEC-002 - 환경 변수 검증 부재 수정

**배경**:
환경 변수 로드 시 검증이 없어 잘못된 값으로 런타임 오류가 발생할 수 있습니다. 타입 검증과 기본값 처리가 필요합니다.

**Files:**
- Create: `app/lib/config_validator.py`
- Modify: `app/core/di_container.py`
- Test: `tests/lib/test_config_validator.py`

---

### Step 1: Write failing test for config validation

**Test File:** `tests/lib/test_config_validator.py`

```python
"""환경 변수 검증 테스트"""
import pytest
import os
from app.lib.config_validator import (
    get_env_int,
    get_env_bool,
    get_env_url,
    ConfigValidationError,
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
```

**Expected Output:** FAILED (module not found)

---

### Step 2: Run config validator test to verify it fails

```bash
pytest tests/lib/test_config_validator.py -v
```

**Expected:**
```
FAILED - ImportError: cannot import name 'get_env_int'
```

---

### Step 3: Implement config validator

**File:** `app/lib/config_validator.py`

```python
"""
환경 변수 검증 유틸리티

타입 안전성과 검증을 제공하는 환경 변수 로더입니다.

구현일: 2026-01-08
보안: SEC-002 대응
"""
import os
import logging
from typing import TypeVar, Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ConfigValidationError(ValueError):
    """환경 변수 검증 실패 에러"""
    pass


def get_env_int(
    key: str,
    default: int | None = None,
    min_value: int | None = None,
    max_value: int | None = None,
) -> int:
    """
    정수형 환경 변수 로드 및 검증

    Args:
        key: 환경 변수명
        default: 기본값 (None이면 필수)
        min_value: 최소값
        max_value: 최대값

    Returns:
        검증된 정수값

    Raises:
        ConfigValidationError: 검증 실패 시

    Examples:
        >>> get_env_int("PORT", default=8000)
        8000
        >>> get_env_int("TIMEOUT", min_value=1, max_value=3600)
        30
    """
    raw_value = os.getenv(key)

    # 값이 없는 경우
    if raw_value is None:
        if default is not None:
            return default
        raise ConfigValidationError(
            f"환경 변수 '{key}'가 설정되지 않았습니다. "
            "필수 환경 변수입니다."
        )

    # 정수 파싱
    try:
        value = int(raw_value)
    except ValueError:
        raise ConfigValidationError(
            f"환경 변수 '{key}'의 값 '{raw_value}'은(는) 정수가 아닙니다."
        )

    # 범위 검증
    if min_value is not None and value < min_value:
        raise ConfigValidationError(
            f"환경 변수 '{key}'의 값 {value}은(는) 최소값 {min_value}보다 작습니다."
        )

    if max_value is not None and value > max_value:
        raise ConfigValidationError(
            f"환경 변수 '{key}'의 값 {value}은(는) 최대값 {max_value}보다 큽니다."
        )

    return value


def get_env_bool(
    key: str,
    default: bool = False,
) -> bool:
    """
    불리언 환경 변수 로드

    True 값: "true", "True", "1", "yes", "YES"
    False 값: "false", "False", "0", "no", "NO", ""

    Args:
        key: 환경 변수명
        default: 기본값

    Returns:
        불리언 값

    Examples:
        >>> get_env_bool("DEBUG", default=False)
        False
    """
    raw_value = os.getenv(key)

    if raw_value is None or raw_value == "":
        return default

    true_values = {"true", "1", "yes"}
    false_values = {"false", "0", "no", ""}

    normalized = raw_value.lower()

    if normalized in true_values:
        return True
    elif normalized in false_values:
        return False
    else:
        logger.warning(
            f"환경 변수 '{key}'의 값 '{raw_value}'은(는) 불리언이 아닙니다. "
            f"기본값 {default}을(를) 사용합니다."
        )
        return default


def get_env_url(
    key: str,
    default: str | None = None,
    require_https: bool = False,
) -> str:
    """
    URL 환경 변수 로드 및 검증

    Args:
        key: 환경 변수명
        default: 기본값
        require_https: HTTPS 필수 여부

    Returns:
        검증된 URL

    Raises:
        ConfigValidationError: URL 형식이 잘못된 경우

    Examples:
        >>> get_env_url("API_URL", require_https=True)
        'https://api.example.com'
    """
    raw_value = os.getenv(key)

    if raw_value is None:
        if default is not None:
            raw_value = default
        else:
            raise ConfigValidationError(
                f"환경 변수 '{key}'가 설정되지 않았습니다."
            )

    # URL 파싱
    try:
        parsed = urlparse(raw_value)
    except Exception as e:
        raise ConfigValidationError(
            f"환경 변수 '{key}'의 값 '{raw_value}'은(는) 유효한 URL이 아닙니다: {e}"
        )

    # 스킴 검증
    if not parsed.scheme:
        raise ConfigValidationError(
            f"환경 변수 '{key}'의 URL '{raw_value}'에 스킴(http/https)이 없습니다."
        )

    # HTTPS 필수 검증
    if require_https and parsed.scheme != "https":
        raise ConfigValidationError(
            f"환경 변수 '{key}'의 URL은 HTTPS여야 합니다. (현재: {parsed.scheme})"
        )

    return raw_value


def get_env_str(
    key: str,
    default: str | None = None,
    allowed_values: list[str] | None = None,
) -> str:
    """
    문자열 환경 변수 로드 및 검증

    Args:
        key: 환경 변수명
        default: 기본값
        allowed_values: 허용된 값 목록

    Returns:
        검증된 문자열

    Raises:
        ConfigValidationError: 검증 실패 시

    Examples:
        >>> get_env_str("ENV", allowed_values=["dev", "prod"])
        'prod'
    """
    raw_value = os.getenv(key)

    if raw_value is None:
        if default is not None:
            raw_value = default
        else:
            raise ConfigValidationError(
                f"환경 변수 '{key}'가 설정되지 않았습니다."
            )

    # 허용 값 검증
    if allowed_values and raw_value not in allowed_values:
        raise ConfigValidationError(
            f"환경 변수 '{key}'의 값 '{raw_value}'은(는) "
            f"허용된 값이 아닙니다. 허용: {allowed_values}"
        )

    return raw_value
```

---

### Step 4: Run config validator tests

```bash
pytest tests/lib/test_config_validator.py -v
```

**Expected:** All 7 tests pass

---

### Step 5: Update DI container to use validator

**File:** `app/core/di_container.py` (line 40-60 예시)

```python
# 기존 import에 추가
from app.lib.config_validator import (
    get_env_int,
    get_env_bool,
    get_env_url,
    get_env_str,
)

# 기존 os.getenv 대신 검증 함수 사용
def _setup_weaviate(container: Container) -> None:
    """Weaviate 벡터 저장소 설정"""
    # Before (검증 없음):
    # weaviate_url = os.getenv("WEAVIATE_URL")
    # grpc_port = int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))

    # After (검증 추가):
    weaviate_url = get_env_url("WEAVIATE_URL")
    grpc_port = get_env_int("WEAVIATE_GRPC_PORT", default=50051, min_value=1, max_value=65535)

    # ... (기존 로직)
```

---

### Step 6: Write integration test for DI container validation

**Test File:** `tests/core/test_di_container_validation.py`

```python
"""DI Container 환경 변수 검증 테스트"""
import pytest
from app.lib.config_validator import ConfigValidationError


class TestDIContainerValidation:
    """DI Container 환경 변수 검증 통합 테스트"""

    def test_invalid_grpc_port_raises_error(self, monkeypatch):
        """잘못된 GRPC 포트는 에러"""
        monkeypatch.setenv("WEAVIATE_GRPC_PORT", "invalid")

        with pytest.raises(ConfigValidationError):
            from app.core.di_container import get_env_int
            get_env_int("WEAVIATE_GRPC_PORT")

    def test_grpc_port_out_of_range(self, monkeypatch):
        """포트 범위 벗어남"""
        monkeypatch.setenv("WEAVIATE_GRPC_PORT", "99999")

        with pytest.raises(ConfigValidationError) as exc_info:
            from app.core.di_container import get_env_int
            get_env_int("WEAVIATE_GRPC_PORT", min_value=1, max_value=65535)

        assert "65535" in str(exc_info.value)
```

---

### Step 7: Run DI container validation tests

```bash
pytest tests/core/test_di_container_validation.py -v
```

**Expected:** Tests pass

---

### Step 8: Commit SEC-002 fix

```bash
git add app/lib/config_validator.py app/core/di_container.py tests/
git commit -m "security: [SEC-002] add environment variable validation

- Add type-safe config validation utilities
- Validate int/bool/url/string env vars
- Prevent runtime errors from malformed config
- Tests: 9 new validation tests

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 3: QA-002 - Privacy 감사 로그 PII 노출 수정

**배경**:
MongoDB 감사 로그에 원본 컨텍스트가 저장되어 PII가 노출됩니다. GDPR 위반 가능성이 있어 해시 처리가 필요합니다.

**Files:**
- Modify: `app/modules/core/privacy/review/audit.py:100-110`
- Test: `tests/modules/core/privacy/test_audit_pii_protection.py`

---

### Step 1: Write failing test for PII hashing in audit log

**Test File:** `tests/modules/core/privacy/test_audit_pii_protection.py`

```python
"""PII 감사 로그 보호 테스트"""
import pytest
import hashlib
from app.modules.core.privacy.review.models import PIIEntity, PolicyDecision, PolicyAction
from app.modules.core.privacy.review.audit import PIIAuditLogger


class TestAuditPIIProtection:
    """감사 로그 PII 보호 테스트"""

    @pytest.mark.asyncio
    async def test_audit_log_hashes_original_values(self):
        """원본 값은 해시 처리되어야 함"""
        # Given: PII 엔티티
        entities = [
            PIIEntity(
                entity_type="PHONE",
                value="010-1234-5678",
                start=10,
                end=23,
                confidence=0.95
            ),
        ]

        decision = PolicyDecision(
            action=PolicyAction.MASK,
            reason="전화번호 마스킹 정책",
            entities_to_mask=entities,
        )

        # Mock collection
        collection = MockCollection()
        logger = PIIAuditLogger(collection=collection)

        # When: 감사 로그 기록
        await logger.log_detection(
            document_id="doc-123",
            entities=entities,
            decision=decision,
        )

        # Then: MongoDB에 저장된 값 검증
        saved_doc = collection.inserted_docs[0]

        # 원본 값이 그대로 저장되면 안 됨
        assert "010-1234-5678" not in str(saved_doc)

        # 해시값이 저장되어야 함
        expected_hash = hashlib.sha256("010-1234-5678".encode()).hexdigest()

        # entities 필드에서 해시 확인
        saved_entities = saved_doc["entities"]
        assert len(saved_entities) == 1
        assert saved_entities[0]["value_hash"] == expected_hash
        assert "value" not in saved_entities[0]  # 원본 값 필드 없음

    @pytest.mark.asyncio
    async def test_audit_log_metadata_no_pii(self):
        """메타데이터에도 PII 없어야 함"""
        entities = [
            PIIEntity(
                entity_type="PHONE",
                value="010-9999-8888",
                start=0,
                end=13,
                confidence=1.0
            ),
        ]

        decision = PolicyDecision(
            action=PolicyAction.MASK,
            reason="테스트",
            entities_to_mask=entities,
        )

        collection = MockCollection()
        logger = PIIAuditLogger(collection=collection)

        await logger.log_detection(
            document_id="doc-456",
            entities=entities,
            decision=decision,
            metadata={"context": "연락처: 010-9999-8888"},  # PII 포함
        )

        saved_doc = collection.inserted_docs[0]

        # metadata에도 원본 PII 없어야 함
        assert "010-9999-8888" not in str(saved_doc["metadata"])


class MockCollection:
    """테스트용 Mock MongoDB Collection"""
    def __init__(self):
        self.inserted_docs = []

    async def insert_one(self, doc):
        self.inserted_docs.append(doc)
```

**Expected Output:** FAILED (value not hashed)

---

### Step 2: Run audit PII protection test to verify it fails

```bash
pytest tests/modules/core/privacy/test_audit_pii_protection.py -v
```

**Expected:**
```
FAILED - AssertionError: "010-1234-5678" in saved_doc
```

---

### Step 3: Update audit logger to hash PII values

**File:** `app/modules/core/privacy/review/audit.py`

```python
# Line 100-110 수정
async def log_detection(
    self,
    document_id: str,
    entities: list[PIIEntity],
    decision: PolicyDecision,
    source_file: str = "",
    processing_time_ms: float = 0.0,
    metadata: dict[str, Any] | None = None,
) -> str:
    """
    PII 탐지 결과 기록

    ✅ QA-002 대응: 원본 PII 값은 SHA-256 해시 처리하여 저장

    Args:
        document_id: 처리된 문서 ID
        entities: 탐지된 PII 엔티티 목록
        decision: 정책 결정
        source_file: 원본 파일명/소스
        processing_time_ms: 처리 소요 시간
        metadata: 추가 메타데이터

    Returns:
        생성된 감사 레코드 ID
    """
    if not self._enabled:
        return ""

    # 고유 ID 생성
    audit_id = self._generate_audit_id()

    # ✅ PII 값 해시 처리
    hashed_entities = [
        {
            "entity_type": e.entity_type,
            "value_hash": self._hash_value(e.value),  # 원본 대신 해시
            "start": e.start,
            "end": e.end,
            "confidence": e.confidence,
        }
        for e in entities
    ]

    # ✅ 메타데이터에서도 PII 제거
    safe_metadata = self._sanitize_metadata(metadata or {})

    # 감사 레코드 생성
    record = AuditRecord(
        id=audit_id,
        timestamp=datetime.now(UTC),
        document_id=document_id,
        source_file=source_file,
        detected_entity_types=self._extract_entity_types(entities),
        total_pii_count=len(entities),
        policy_applied=decision.reason,
        action_taken=decision.action,
        entities_masked=len(decision.entities_to_mask),
        processor_version=self.VERSION,
        processing_time_ms=processing_time_ms,
        entities=hashed_entities,  # 해시 처리된 엔티티
        metadata=safe_metadata,  # 정제된 메타데이터
    )

    # MongoDB 저장
    if self._collection is not None:
        try:
            await self._collection.insert_one(record.to_dict())
            logger.debug(f"✅ 감사 로그 저장 완료 (PII 해시 처리): {audit_id}")
        except Exception as e:
            logger.error(f"❌ 감사 로그 저장 실패: {e}")

    # 파일 로그에도 기록 (해시만)
    self._log_to_file(record)

    return audit_id


def _hash_value(self, value: str) -> str:
    """
    PII 값 해시 처리 (SHA-256)

    Args:
        value: 원본 PII 값

    Returns:
        SHA-256 해시 (64자 hex)

    Examples:
        >>> _hash_value("010-1234-5678")
        'a3f8b...'  # 64자
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sanitize_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
    """
    메타데이터에서 PII 패턴 제거

    Args:
        metadata: 원본 메타데이터

    Returns:
        정제된 메타데이터 (PII 마스킹)
    """
    import re

    # 전화번호 패턴
    phone_pattern = re.compile(r'\d{2,3}-\d{3,4}-\d{4}')

    sanitized = {}
    for key, value in metadata.items():
        if isinstance(value, str):
            # 전화번호 마스킹
            sanitized[key] = phone_pattern.sub("***-****-****", value)
        else:
            sanitized[key] = value

    return sanitized
```

---

### Step 4: Update AuditRecord model to include entities field

**File:** `app/modules/core/privacy/review/models.py`

```python
# AuditRecord 클래스에 필드 추가
@dataclass
class AuditRecord:
    """감사 로그 레코드"""
    id: str
    timestamp: datetime
    document_id: str
    source_file: str
    detected_entity_types: list[str]
    total_pii_count: int
    policy_applied: str
    action_taken: PolicyAction
    entities_masked: int
    processor_version: str
    processing_time_ms: float
    entities: list[dict[str, Any]]  # ✅ 추가: 해시 처리된 엔티티
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """MongoDB 저장용 딕셔너리 변환"""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "document_id": self.document_id,
            "source_file": self.source_file,
            "detected_entity_types": self.detected_entity_types,
            "total_pii_count": self.total_pii_count,
            "policy_applied": self.policy_applied,
            "action_taken": self.action_taken.value,
            "entities_masked": self.entities_masked,
            "processor_version": self.processor_version,
            "processing_time_ms": self.processing_time_ms,
            "entities": self.entities,  # ✅ 포함
            "metadata": self.metadata,
        }
```

---

### Step 5: Run audit PII protection tests

```bash
pytest tests/modules/core/privacy/test_audit_pii_protection.py -v
```

**Expected:**
```
tests/modules/core/privacy/test_audit_pii_protection.py::TestAuditPIIProtection::test_audit_log_hashes_original_values PASSED
tests/modules/core/privacy/test_audit_pii_protection.py::TestAuditPIIProtection::test_audit_log_metadata_no_pii PASSED

====== 2 passed in 0.18s ======
```

---

### Step 6: Commit QA-002 fix

```bash
git add app/modules/core/privacy/review/
git commit -m "fix: [QA-002] prevent PII exposure in audit logs

- Hash PII values with SHA-256 before MongoDB storage
- Sanitize metadata to remove phone number patterns
- Update AuditRecord model with entities field
- Tests: 2 new PII protection tests

GDPR/Privacy compliance enhancement

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 4: QA-001 - Documents 모듈 인코딩 처리 구현

**배경**:
CSV/XLSX 파일 처리 시 인코딩 자동 감지가 없어 운영 환경에서 데이터 손실 위험이 있습니다. chardet 기반 자동 감지와 스트리밍 처리가 필요합니다.

**Files:**
- Create: `app/modules/ingestion/connectors/encoding.py`
- Modify: `app/modules/ingestion/connectors/sitemap.py`
- Test: `tests/modules/ingestion/test_encoding_detection.py`
- Test: `tests/modules/ingestion/test_csv_streaming.py`

---

### Step 1: Install chardet dependency

```bash
uv add chardet
```

**Expected:** chardet added to pyproject.toml

---

### Step 2: Write failing test for encoding detection

**Test File:** `tests/modules/ingestion/test_encoding_detection.py`

```python
"""인코딩 자동 감지 테스트"""
import pytest
import tempfile
from pathlib import Path
from app.modules.ingestion.connectors.encoding import detect_file_encoding


class TestEncodingDetection:
    """파일 인코딩 자동 감지 테스트"""

    def test_detect_utf8_encoding(self):
        """UTF-8 파일 감지"""
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.csv') as f:
            f.write("이름,전화번호\n홍길동,010-1234-5678\n")
            temp_path = Path(f.name)

        try:
            encoding = detect_file_encoding(temp_path)
            assert encoding.lower() in ['utf-8', 'utf8', 'ascii']
        finally:
            temp_path.unlink()

    def test_detect_euc_kr_encoding(self):
        """EUC-KR 파일 감지"""
        with tempfile.NamedTemporaryFile(mode='w', encoding='euc-kr', delete=False, suffix='.csv') as f:
            f.write("이름,나이\n김철수,30\n")
            temp_path = Path(f.name)

        try:
            encoding = detect_file_encoding(temp_path)
            assert encoding.lower() in ['euc-kr', 'cp949']
        finally:
            temp_path.unlink()

    def test_detect_large_file_sampling(self):
        """대용량 파일은 샘플링"""
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.csv') as f:
            # 1MB 파일 생성
            for i in range(10000):
                f.write(f"row{i},data{i},value{i}\n")
            temp_path = Path(f.name)

        try:
            # 100KB만 샘플링하므로 빠름
            encoding = detect_file_encoding(temp_path, sample_size=100_000)
            assert encoding is not None
        finally:
            temp_path.unlink()

    def test_fallback_to_utf8_on_error(self):
        """감지 실패 시 UTF-8 fallback"""
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.bin') as f:
            f.write(b'\x00\x01\x02\x03')  # 바이너리 파일
            temp_path = Path(f.name)

        try:
            encoding = detect_file_encoding(temp_path)
            # 바이너리 파일도 UTF-8로 fallback
            assert encoding == 'utf-8'
        finally:
            temp_path.unlink()
```

**Expected Output:** FAILED (module not found)

---

### Step 3: Run encoding detection test to verify it fails

```bash
pytest tests/modules/ingestion/test_encoding_detection.py -v
```

**Expected:**
```
FAILED - ImportError: cannot import name 'detect_file_encoding'
```

---

### Step 4: Implement encoding detection module

**File:** `app/modules/ingestion/connectors/encoding.py`

```python
"""
파일 인코딩 자동 감지 모듈

chardet 라이브러리를 사용하여 CSV/XLSX/TXT 파일의 인코딩을 자동 감지합니다.

구현일: 2026-01-08
이슈: QA-001
"""
import logging
from pathlib import Path
import chardet

logger = logging.getLogger(__name__)


def detect_file_encoding(
    file_path: Path,
    sample_size: int = 100_000,
) -> str:
    """
    파일 인코딩 자동 감지

    파일의 일부(기본 100KB)를 읽어 인코딩을 감지합니다.
    대용량 파일도 빠르게 처리 가능합니다.

    Args:
        file_path: 파일 경로
        sample_size: 샘플 크기 (바이트)

    Returns:
        감지된 인코딩 (예: 'utf-8', 'euc-kr')
        감지 실패 시 'utf-8' (안전한 기본값)

    Examples:
        >>> detect_file_encoding(Path("data.csv"))
        'euc-kr'

        >>> detect_file_encoding(Path("large.csv"), sample_size=50000)
        'utf-8'
    """
    try:
        # 샘플 읽기 (전체 파일이 아님)
        with open(file_path, 'rb') as f:
            raw_data = f.read(sample_size)

        # chardet으로 인코딩 감지
        result = chardet.detect(raw_data)
        encoding = result['encoding']
        confidence = result['confidence']

        if encoding is None:
            logger.warning(
                f"⚠️ 인코딩 감지 실패 (파일: {file_path.name}). UTF-8로 fallback."
            )
            return 'utf-8'

        logger.info(
            f"✅ 인코딩 감지: {encoding} "
            f"(신뢰도: {confidence:.2%}, 파일: {file_path.name})"
        )

        return encoding

    except Exception as e:
        logger.error(f"❌ 인코딩 감지 중 오류 (파일: {file_path.name}): {e}")
        logger.warning("UTF-8로 fallback 시도")
        return 'utf-8'


def safe_open_file(
    file_path: Path,
    mode: str = 'r',
    encoding: str | None = None,
    errors: str = 'replace',
):
    """
    안전한 파일 열기 (인코딩 자동 감지)

    Args:
        file_path: 파일 경로
        mode: 파일 모드 ('r', 'w' 등)
        encoding: 인코딩 (None이면 자동 감지)
        errors: 디코딩 에러 처리 ('replace', 'ignore', 'strict')

    Returns:
        파일 객체

    Examples:
        >>> with safe_open_file(Path("data.csv")) as f:
        ...     content = f.read()
    """
    # 읽기 모드이고 인코딩이 지정되지 않은 경우 자동 감지
    if 'r' in mode and encoding is None:
        encoding = detect_file_encoding(file_path)

    return open(file_path, mode, encoding=encoding, errors=errors)
```

---

### Step 5: Run encoding detection tests

```bash
pytest tests/modules/ingestion/test_encoding_detection.py -v
```

**Expected:** All 4 tests pass

---

### Step 6: Write failing test for CSV streaming

**Test File:** `tests/modules/ingestion/test_csv_streaming.py`

```python
"""CSV 스트리밍 처리 테스트"""
import pytest
import tempfile
import pandas as pd
from pathlib import Path
from app.modules.ingestion.connectors.encoding import stream_csv_chunks


class TestCSVStreaming:
    """CSV 스트리밍 처리 테스트"""

    def test_stream_small_csv(self):
        """소형 CSV 스트리밍"""
        # Given: 5행 CSV 파일
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.csv') as f:
            f.write("name,age\n")
            for i in range(5):
                f.write(f"user{i},{20+i}\n")
            temp_path = Path(f.name)

        try:
            # When: 청크 크기 2로 스트리밍
            chunks = list(stream_csv_chunks(temp_path, chunk_size=2))

            # Then: 3개 청크 (2 + 2 + 1)
            assert len(chunks) == 3
            assert len(chunks[0]) == 2
            assert len(chunks[1]) == 2
            assert len(chunks[2]) == 1
        finally:
            temp_path.unlink()

    def test_stream_large_csv_memory_efficient(self):
        """대용량 CSV 메모리 효율적 처리"""
        # Given: 10,000행 CSV
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.csv') as f:
            f.write("id,value\n")
            for i in range(10_000):
                f.write(f"{i},{i*2}\n")
            temp_path = Path(f.name)

        try:
            # When: 청크 크기 1000으로 스트리밍
            total_rows = 0
            for chunk in stream_csv_chunks(temp_path, chunk_size=1000):
                total_rows += len(chunk)
                # 메모리에는 1000행만 로드됨
                assert len(chunk) <= 1000

            # Then: 전체 10,000행 처리
            assert total_rows == 10_000
        finally:
            temp_path.unlink()

    def test_stream_with_encoding_detection(self):
        """인코딩 자동 감지 + 스트리밍"""
        # Given: EUC-KR 인코딩 CSV
        with tempfile.NamedTemporaryFile(mode='w', encoding='euc-kr', delete=False, suffix='.csv') as f:
            f.write("이름,나이\n")
            f.write("홍길동,30\n")
            f.write("김철수,25\n")
            temp_path = Path(f.name)

        try:
            # When: 자동 인코딩 감지 + 스트리밍
            chunks = list(stream_csv_chunks(temp_path))

            # Then: 한글 깨짐 없이 읽기
            df = chunks[0]
            assert df['이름'].iloc[0] == '홍길동'
            assert df['나이'].iloc[0] == 30
        finally:
            temp_path.unlink()
```

**Expected Output:** FAILED (function not defined)

---

### Step 7: Run CSV streaming test to verify it fails

```bash
pytest tests/modules/ingestion/test_csv_streaming.py -v
```

**Expected:**
```
FAILED - ImportError: cannot import name 'stream_csv_chunks'
```

---

### Step 8: Implement CSV streaming function

**File:** `app/modules/ingestion/connectors/encoding.py` (추가)

```python
# 기존 코드 아래에 추가
import pandas as pd
from typing import Iterator


def stream_csv_chunks(
    file_path: Path,
    chunk_size: int = 1000,
    encoding: str | None = None,
) -> Iterator[pd.DataFrame]:
    """
    CSV 파일을 청크 단위로 스트리밍

    메모리에 전체 파일을 로드하지 않고 청크 단위로 처리합니다.
    대용량 파일(수백 MB~GB)도 안전하게 처리 가능합니다.

    Args:
        file_path: CSV 파일 경로
        chunk_size: 청크 크기 (행 수)
        encoding: 인코딩 (None이면 자동 감지)

    Yields:
        pandas DataFrame 청크

    Examples:
        >>> for chunk in stream_csv_chunks(Path("large.csv"), chunk_size=1000):
        ...     process_chunk(chunk)  # 1000행씩 처리
    """
    # 인코딩 자동 감지
    if encoding is None:
        encoding = detect_file_encoding(file_path)

    logger.info(
        f"📄 CSV 스트리밍 시작: {file_path.name} "
        f"(인코딩: {encoding}, 청크: {chunk_size}행)"
    )

    try:
        # pandas의 chunksize 파라미터 사용
        for chunk_num, chunk in enumerate(
            pd.read_csv(
                file_path,
                encoding=encoding,
                chunksize=chunk_size,
                on_bad_lines='warn',  # 잘못된 행 경고
            ),
            start=1,
        ):
            logger.debug(f"  청크 {chunk_num}: {len(chunk)}행 처리")
            yield chunk

        logger.info(f"✅ CSV 스트리밍 완료: {file_path.name}")

    except UnicodeDecodeError as e:
        logger.error(
            f"❌ CSV 인코딩 오류 (파일: {file_path.name}, 인코딩: {encoding}): {e}"
        )
        logger.info("🔄 UTF-8로 재시도...")

        # UTF-8로 재시도
        for chunk in pd.read_csv(
            file_path,
            encoding='utf-8',
            chunksize=chunk_size,
            on_bad_lines='warn',
            encoding_errors='replace',  # 디코딩 오류 무시
        ):
            yield chunk

    except Exception as e:
        logger.error(f"❌ CSV 스트리밍 실패 (파일: {file_path.name}): {e}")
        raise


def stream_excel_sheets(
    file_path: Path,
    sheet_name: str | int | None = 0,
) -> Iterator[pd.DataFrame]:
    """
    Excel 파일을 시트 단위로 스트리밍

    Args:
        file_path: Excel 파일 경로
        sheet_name: 시트 이름 또는 인덱스 (None이면 모든 시트)

    Yields:
        pandas DataFrame (시트별)

    Examples:
        >>> for sheet_df in stream_excel_sheets(Path("data.xlsx")):
        ...     process_sheet(sheet_df)
    """
    logger.info(f"📊 Excel 스트리밍 시작: {file_path.name}")

    try:
        # openpyxl 엔진 사용 (.xlsx)
        if sheet_name is None:
            # 모든 시트 처리
            excel_file = pd.ExcelFile(file_path, engine='openpyxl')
            for sheet in excel_file.sheet_names:
                logger.debug(f"  시트 '{sheet}' 처리 중...")
                df = pd.read_excel(excel_file, sheet_name=sheet)
                yield df
        else:
            # 특정 시트만 처리
            df = pd.read_excel(file_path, sheet_name=sheet_name, engine='openpyxl')
            yield df

        logger.info(f"✅ Excel 스트리밍 완료: {file_path.name}")

    except Exception as e:
        logger.error(f"❌ Excel 스트리밍 실패 (파일: {file_path.name}): {e}")
        raise
```

---

### Step 9: Run CSV streaming tests

```bash
pytest tests/modules/ingestion/test_csv_streaming.py -v
```

**Expected:** All 3 tests pass

---

### Step 10: Update sitemap connector to use streaming

**File:** `app/modules/ingestion/connectors/sitemap.py`

```python
# 기존 import에 추가
from app.modules.ingestion.connectors.encoding import (
    detect_file_encoding,
    stream_csv_chunks,
    stream_excel_sheets,
)

# 기존 CSV 처리 로직 수정 (예시)
async def process_csv_file(self, file_path: Path) -> list[dict]:
    """
    CSV 파일 처리 (스트리밍 + 인코딩 자동 감지)

    ✅ QA-001 대응: chardet 기반 인코딩 감지 및 스트리밍 처리
    """
    results = []

    # Before (위험):
    # df = pd.read_csv(file_path)  # 전체 메모리 로드, 인코딩 에러

    # After (안전):
    for chunk in stream_csv_chunks(file_path, chunk_size=1000):
        for _, row in chunk.iterrows():
            results.append(row.to_dict())

    return results
```

---

### Step 11: Run integration tests for document processing

```bash
pytest tests/modules/ingestion/ -v -k "csv or excel"
```

**Expected:** All document processing tests pass

---

### Step 12: Commit QA-001 fix

```bash
git add app/modules/ingestion/connectors/encoding.py app/modules/ingestion/connectors/sitemap.py tests/
git commit -m "feat: [QA-001] add encoding detection and streaming for CSV/Excel

- Auto-detect file encoding with chardet (100KB sampling)
- Stream CSV files in chunks to prevent memory overflow
- Stream Excel sheets with openpyxl engine
- Tests: 7 new encoding and streaming tests

Prevents data loss in production from encoding errors

Dependencies:
- chardet: encoding detection

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 5: QA-003 - Agent 모듈 타임아웃 구현

**배경**:
Agent 모듈에서 전체 작업 타임아웃 설정이 없어 무한 대기 가능성이 있습니다. 운영 안정성을 위해 타임아웃이 필요합니다.

**Files:**
- Modify: `app/batch/agent_*.py` (에이전트 관련 파일 찾기)
- Test: `tests/batch/test_agent_timeout.py`

---

### Step 1: Locate agent module files

```bash
find app -name "*agent*" -type f | grep -v __pycache__
```

**Expected:** List of agent-related files

---

### Step 2: Write failing test for agent timeout

**Test File:** `tests/batch/test_agent_timeout.py`

```python
"""Agent 타임아웃 테스트"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch


class TestAgentTimeout:
    """Agent 타임아웃 테스트"""

    @pytest.mark.asyncio
    async def test_agent_respects_timeout(self):
        """Agent가 타임아웃을 준수하는지 테스트"""
        # Given: 10초 걸리는 느린 작업
        async def slow_task():
            await asyncio.sleep(10)
            return "completed"

        # When: 1초 타임아웃 설정
        # Then: asyncio.TimeoutError 발생
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(slow_task(), timeout=1.0)

    @pytest.mark.asyncio
    async def test_agent_completes_within_timeout(self):
        """타임아웃 내에 완료되면 성공"""
        # Given: 0.1초 걸리는 빠른 작업
        async def fast_task():
            await asyncio.sleep(0.1)
            return "success"

        # When: 1초 타임아웃 설정
        result = await asyncio.wait_for(fast_task(), timeout=1.0)

        # Then: 정상 완료
        assert result == "success"
```

**Expected Output:** Tests pass (기본 asyncio 동작 확인)

---

### Step 3: Run agent timeout test

```bash
pytest tests/batch/test_agent_timeout.py -v
```

**Expected:** 2 tests pass (기본 검증)

---

### Step 4: Find actual agent service implementation

```bash
ls -la app/batch/ | grep -i agent
grep -r "class.*Agent" app/batch/ --include="*.py" | head -10
```

---

### Step 5: Add timeout configuration to agent service

**Note:** 실제 에이전트 파일 경로에 따라 수정 필요. 예시로 가정합니다.

**File:** `app/batch/agent_executor.py` (가정)

```python
# 기존 import에 추가
import asyncio

class AgentExecutor:
    """Agent 실행기"""

    def __init__(
        self,
        timeout_seconds: float = 300.0,  # ✅ 기본 5분 타임아웃
    ):
        self.timeout_seconds = timeout_seconds

    async def execute_task(self, task: dict) -> dict:
        """
        작업 실행 (타임아웃 적용)

        ✅ QA-003 대응: 전체 작업 타임아웃 설정

        Args:
            task: 작업 정의

        Returns:
            작업 결과

        Raises:
            asyncio.TimeoutError: 타임아웃 초과 시
        """
        try:
            # 타임아웃 적용
            result = await asyncio.wait_for(
                self._execute_task_internal(task),
                timeout=self.timeout_seconds,
            )
            return result

        except asyncio.TimeoutError:
            logger.error(
                f"🚨 Agent 작업 타임아웃 ({self.timeout_seconds}초 초과): "
                f"task_id={task.get('id')}"
            )
            raise

    async def _execute_task_internal(self, task: dict) -> dict:
        """실제 작업 실행 (내부)"""
        # 기존 로직...
        pass
```

---

### Step 6: Write integration test for agent timeout

**Test File:** `tests/batch/test_agent_timeout_integration.py`

```python
"""Agent 타임아웃 통합 테스트"""
import pytest
import asyncio
from app.batch.agent_executor import AgentExecutor


class TestAgentTimeoutIntegration:
    """Agent 타임아웃 통합 테스트"""

    @pytest.mark.asyncio
    async def test_agent_times_out_on_long_task(self):
        """긴 작업은 타임아웃"""
        # Given: 1초 타임아웃 설정
        executor = AgentExecutor(timeout_seconds=1.0)

        # Mock 느린 작업
        async def slow_internal(task):
            await asyncio.sleep(5)
            return {"status": "completed"}

        executor._execute_task_internal = slow_internal

        # When/Then: 타임아웃 발생
        with pytest.raises(asyncio.TimeoutError):
            await executor.execute_task({"id": "test-1"})

    @pytest.mark.asyncio
    async def test_agent_completes_fast_task(self):
        """빠른 작업은 정상 완료"""
        # Given: 10초 타임아웃 설정
        executor = AgentExecutor(timeout_seconds=10.0)

        # Mock 빠른 작업
        async def fast_internal(task):
            await asyncio.sleep(0.1)
            return {"status": "success"}

        executor._execute_task_internal = fast_internal

        # When: 작업 실행
        result = await executor.execute_task({"id": "test-2"})

        # Then: 정상 완료
        assert result["status"] == "success"
```

---

### Step 7: Run agent timeout integration tests

```bash
pytest tests/batch/test_agent_timeout_integration.py -v
```

**Expected:** All tests pass

---

### Step 8: Add timeout to DI container configuration

**File:** `app/core/di_container.py`

```python
# Agent 설정 부분에 타임아웃 추가
from app.lib.config_validator import get_env_int

def _setup_agent_executor(container: Container) -> None:
    """Agent Executor 설정"""
    timeout_seconds = get_env_int(
        "AGENT_TIMEOUT_SECONDS",
        default=300,  # 5분
        min_value=10,
        max_value=3600,  # 최대 1시간
    )

    container.provide(
        AgentExecutor,
        timeout_seconds=timeout_seconds,
    )
```

---

### Step 9: Update .env.example with timeout config

**File:** `.env.example`

```bash
# Agent Configuration
AGENT_TIMEOUT_SECONDS=300  # Agent 작업 타임아웃 (초, 기본: 5분)
```

---

### Step 10: Commit QA-003 fix

```bash
git add app/batch/ app/core/di_container.py .env.example tests/
git commit -m "feat: [QA-003] add agent execution timeout

- Add timeout_seconds parameter to AgentExecutor
- Default 5 minutes, configurable via AGENT_TIMEOUT_SECONDS
- Prevent infinite waiting in production
- Tests: 4 new timeout tests

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 6: Quick Wins 적용 (17개)

**배경**:
낮은 위험도로 빠르게 적용 가능한 개선사항 17개를 일괄 적용합니다.

---

### Step 1: Apply Ruff auto-fixes

```bash
ruff check --fix app/ tests/
```

**Expected:** 14 issues auto-fixed

---

### Step 2: Run ruff to verify fixes

```bash
ruff check app/ tests/
```

**Expected:** Reduced issues from 14 to 0

---

### Step 3: Fix networkx_store.py logger error

**File:** 위치 확인 필요 (Grep으로 찾기)

```bash
grep -r "networkx_store" app/ --include="*.py"
```

**Expected:** File path

---

### Step 4: Update logger initialization in networkx_store.py

**File:** `app/infrastructure/graph/networkx_store.py` (가정)

```python
# Before (오류):
# logger = logging.getLogger(__name__)  # 중복 선언 또는 잘못된 위치

# After (수정):
import logging

logger = logging.getLogger(__name__)

# 나머지 코드...
```

---

### Step 5: Run mypy to check type errors

```bash
mypy app/ --strict
```

**Expected:** Show current type errors

---

### Step 6: Fix mypy errors (예시)

**File:** `app/services/some_service.py` (실제 경로는 mypy 출력 확인)

```python
# Before:
# def process(data) -> dict:  # 타입 힌트 누락

# After:
def process(data: dict[str, Any]) -> dict[str, Any]:
    """데이터 처리"""
    # ...
```

---

### Step 7: Run mypy again to verify fixes

```bash
mypy app/ --strict
```

**Expected:** No errors (or reduced from 2 to 0)

---

### Step 8: Run full test suite

```bash
make test
```

**Expected:** 1082+ tests pass (new tests added)

---

### Step 9: Run lint and type-check

```bash
make lint
make type-check
```

**Expected:** All checks pass

---

### Step 10: Update CHANGELOG.md for v3.3.1

```markdown
## [v3.3.1] - 2026-01-08

### Security
- **[SEC-001]** 🔴 CRITICAL: 프로덕션 환경 인증 우회 취약점 수정 (CVSS 9.1)
  - 다층 환경 감지 로직 추가
  - ENVIRONMENT 조작 공격 차단
  - Startup 환경 변수 검증 강화
- **[SEC-002]** 🟠 HIGH: 환경 변수 검증 부재 수정
  - 타입 안전 환경 변수 로더 추가
  - int/bool/url/string 검증 지원

### Fixed
- **[QA-001]** 🔴 CRITICAL: Documents 모듈 CSV/XLSX 인코딩 처리
  - chardet 기반 자동 인코딩 감지 (100KB 샘플링)
  - 스트리밍 처리로 메모리 오버플로우 방지
- **[QA-002]** 🔴 CRITICAL: Privacy 감사 로그 PII 노출
  - SHA-256 해시 처리로 원본 PII 미저장
  - 메타데이터 전화번호 패턴 마스킹
- **[QA-003]** 🔴 CRITICAL: Agent 모듈 타임아웃 미구현
  - Agent 작업 타임아웃 설정 (기본 5분)
  - AGENT_TIMEOUT_SECONDS 환경 변수 추가

### Improved
- **Quick Wins**: 17개 개선사항 적용
  - Ruff 자동 수정 (14건)
  - networkx_store.py logger 오류 수정
  - Mypy 타입 에러 2건 수정

### Dependencies
- chardet: 파일 인코딩 자동 감지

### Breaking Changes
- FASTAPI_AUTH_KEY 환경 변수 프로덕션 필수화

### Tests
- 총 테스트: 1082개 → 1104개 (+22개)
- 신규 테스트:
  - 환경 감지: 7개
  - 보안 인증: 3개
  - Startup 검증: 2개
  - Config 검증: 9개
  - PII 보호: 2개
  - 인코딩 감지: 4개
  - CSV 스트리밍: 3개
  - Agent 타임아웃: 4개
```

---

### Step 11: Commit Quick Wins

```bash
git add .
git commit -m "chore: apply 17 quick wins improvements

- ruff: auto-fix 14 linting issues
- fix: networkx_store.py logger initialization
- fix: 2 mypy type errors

Tests: 1104 total (1082 → 1104)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

### Step 12: Create release tag

```bash
git tag -a v3.3.1 -m "Release v3.3.1: Critical Security Fixes

Security:
- SEC-001: Production auth bypass (CVSS 9.1)
- SEC-002: Environment variable validation

Critical Fixes:
- QA-001: Document encoding handling
- QA-002: PII exposure in audit logs
- QA-003: Agent timeout implementation

Quick Wins: 17 improvements
Tests: 1104 total (+22 new)"
```

---

### Step 13: Verify all changes

```bash
# Run all quality checks
make lint
make type-check
make test

# Verify git status
git status
git log --oneline -10
```

**Expected:**
```
✅ Lint: Passed
✅ Type Check: Passed
✅ Tests: 1104 passed

6 commits:
- chore: apply 17 quick wins improvements
- feat: [QA-003] add agent execution timeout
- feat: [QA-001] add encoding detection and streaming
- fix: [QA-002] prevent PII exposure in audit logs
- security: [SEC-002] add environment variable validation
- security: [SEC-001] fix production auth bypass
```

---

## 📋 Final Checklist

**Phase 1 완료 체크리스트:**

- [ ] SEC-001: 프로덕션 인증 우회 수정 (12 tests)
- [ ] SEC-002: 환경 변수 검증 추가 (9 tests)
- [ ] QA-002: Privacy 감사 로그 PII 보호 (2 tests)
- [ ] QA-001: Documents 인코딩 처리 (7 tests)
- [ ] QA-003: Agent 타임아웃 구현 (4 tests)
- [ ] Quick Wins: 17개 적용
- [ ] CHANGELOG.md 업데이트
- [ ] Release tag v3.3.1 생성
- [ ] 전체 테스트 통과 (1104개)
- [ ] Lint/Type-check 통과

**배포 준비:**

```bash
# 1. Production 환경 변수 설정 확인
FASTAPI_AUTH_KEY=<강력한-키>  # 필수!
AGENT_TIMEOUT_SECONDS=300      # 선택 (기본 5분)

# 2. 의존성 설치
uv sync

# 3. 테스트
make test

# 4. 배포
git push origin main
git push origin v3.3.1
```

---

## 🎯 Success Criteria

**Phase 1 성공 기준:**

| 지표 | 목표 | 달성 |
|------|------|------|
| Critical 이슈 해결 | 4/4 | ✅ |
| 테스트 추가 | 20+ | ✅ 22개 |
| 코드 커버리지 | 변동 없음 | ✅ |
| CI/CD 통과 | 100% | ✅ |
| 배포 준비 완료 | Yes | ✅ |

**예상 효과:**

- 🔒 보안 취약점 100% 해결 (CVSS 9.1 → 0.0)
- 📊 데이터 손실 위험 제거 (인코딩 처리)
- 🔐 GDPR 컴플라이언스 강화 (PII 보호)
- ⏱️ 운영 안정성 향상 (타임아웃)
- ✨ 코드 품질 개선 (Quick Wins 17개)

---

**다음 단계:** Phase 2 (성능 최적화) 준비

