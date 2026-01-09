# SEC-001: 프로덕션 환경 인증 우회 취약점 수정

## 개요

**취약점**: `ENVIRONMENT=development` 환경 변수를 조작하여 프로덕션 환경에서 인증을 우회할 수 있는 CVSS 9.1 (Critical) 취약점

**현재 상태**:
- `app/lib/auth.py` Line 167-182에서 `ENVIRONMENT` 환경 변수만으로 환경 판단
- 단일 환경 변수 조작으로 프로덕션 환경에서 인증 완전 우회 가능

**목표**: 다층 환경 감지 로직을 구현하여 단일 환경 변수 조작으로 인증을 우회할 수 없도록 수정

## TDD 구현 계획 (14단계)

### Phase 1: 환경 감지 모듈 생성 (Step 1-4)

#### Step 1: 환경 감지 테스트 작성
**파일**: `tests/lib/test_environment.py`
**목적**: 다층 환경 감지 로직 검증

```python
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

    def setup_method(self):
        """각 테스트 전에 환경 변수 초기화"""
        # 모든 관련 환경 변수 제거
        for key in ["ENVIRONMENT", "NODE_ENV", "WEAVIATE_URL", "FASTAPI_AUTH_KEY"]:
            os.environ.pop(key, None)

    def test_detect_production_by_environment_variable(self):
        """ENVIRONMENT=production으로 프로덕션 감지"""
        from app.lib.environment import is_production_environment

        os.environ["ENVIRONMENT"] = "production"
        assert is_production_environment() is True

    def test_detect_production_by_node_env(self):
        """NODE_ENV=production으로 프로덕션 감지"""
        from app.lib.environment import is_production_environment

        os.environ["NODE_ENV"] = "production"
        assert is_production_environment() is True

    def test_detect_production_by_https_weaviate(self):
        """WEAVIATE_URL이 https://로 시작하면 프로덕션 감지"""
        from app.lib.environment import is_production_environment

        os.environ["WEAVIATE_URL"] = "https://weaviate.example.com"
        assert is_production_environment() is True

    def test_detect_production_by_auth_key(self):
        """FASTAPI_AUTH_KEY 설정 시 프로덕션 감지"""
        from app.lib.environment import is_production_environment

        os.environ["FASTAPI_AUTH_KEY"] = "secure-key-12345"
        assert is_production_environment() is True

    def test_block_environment_manipulation_attack(self):
        """환경 변수 조작 공격 차단 - 다른 프로덕션 지표 존재 시"""
        from app.lib.environment import is_production_environment

        # 공격자가 ENVIRONMENT=development로 설정
        os.environ["ENVIRONMENT"] = "development"
        # 하지만 다른 프로덕션 지표가 존재
        os.environ["WEAVIATE_URL"] = "https://weaviate.example.com"

        # 프로덕션으로 감지되어야 함 (하나라도 프로덕션 지표가 있으면 프로덕션)
        assert is_production_environment() is True

    def test_allow_development_environment(self):
        """개발 환경 정상 허용"""
        from app.lib.environment import is_production_environment

        os.environ["ENVIRONMENT"] = "development"
        os.environ["WEAVIATE_URL"] = "http://localhost:8080"

        assert is_production_environment() is False

    def test_default_to_development_when_no_indicators(self):
        """지표가 없으면 개발 환경으로 간주"""
        from app.lib.environment import is_production_environment

        # 모든 환경 변수 제거됨 (setup_method)
        assert is_production_environment() is False


class TestRequiredEnvValidation:
    """필수 환경 변수 검증 테스트"""

    def setup_method(self):
        """각 테스트 전에 환경 변수 초기화"""
        for key in ["ENVIRONMENT", "FASTAPI_AUTH_KEY", "GOOGLE_API_KEY", "WEAVIATE_URL"]:
            os.environ.pop(key, None)

    def test_validate_required_vars_in_production(self):
        """프로덕션 환경에서 필수 변수 검증"""
        from app.lib.environment import validate_required_env_vars

        os.environ["ENVIRONMENT"] = "production"
        # FASTAPI_AUTH_KEY 없음

        with pytest.raises(RuntimeError, match="FASTAPI_AUTH_KEY.*required in production"):
            validate_required_env_vars()

    def test_allow_missing_vars_in_development(self):
        """개발 환경에서 누락 허용 (경고만)"""
        from app.lib.environment import validate_required_env_vars

        os.environ["ENVIRONMENT"] = "development"
        # 필수 변수 없어도 예외 발생하지 않음
        validate_required_env_vars()  # 경고만 출력
```

#### Step 2: 테스트 실패 확인
```bash
# 예상 결과: ModuleNotFoundError (app/lib/environment.py 미존재)
pytest tests/lib/test_environment.py -v
```

#### Step 3: 환경 감지 모듈 구현
**파일**: `app/lib/environment.py`

```python
"""
환경 감지 및 검증 모듈

다층 환경 감지 로직:
- 여러 지표를 종합적으로 판단하여 프로덕션 환경 감지
- 단일 환경 변수 조작으로 우회 불가능
- 하나라도 프로덕션 지표가 있으면 프로덕션으로 간주

프로덕션 지표:
1. ENVIRONMENT=production 또는 prod
2. NODE_ENV=production 또는 prod
3. WEAVIATE_URL이 https://로 시작
4. FASTAPI_AUTH_KEY 설정 존재
"""

import os
from typing import List

from .logger import get_logger

logger = get_logger(__name__)


def is_production_environment() -> bool:
    """
    다층 환경 감지 로직으로 프로덕션 환경 여부 판단

    프로덕션 지표:
    - ENVIRONMENT=production 또는 prod
    - NODE_ENV=production 또는 prod
    - WEAVIATE_URL이 https://로 시작
    - FASTAPI_AUTH_KEY 설정 존재

    중요: 하나라도 프로덕션 지표가 있으면 프로덕션으로 간주
    → 환경 변수 조작 공격 차단

    Returns:
        프로덕션 환경 여부
    """
    production_indicators: List[bool] = []

    # 1. ENVIRONMENT 환경 변수 체크
    environment = os.getenv("ENVIRONMENT", "").lower()
    production_indicators.append(environment in ["production", "prod"])

    # 2. NODE_ENV 환경 변수 체크
    node_env = os.getenv("NODE_ENV", "").lower()
    production_indicators.append(node_env in ["production", "prod"])

    # 3. WEAVIATE_URL이 https://로 시작하는지 체크
    weaviate_url = os.getenv("WEAVIATE_URL", "")
    production_indicators.append(weaviate_url.startswith("https://"))

    # 4. FASTAPI_AUTH_KEY 설정 여부 체크
    auth_key = os.getenv("FASTAPI_AUTH_KEY")
    production_indicators.append(bool(auth_key))

    # 하나라도 True이면 프로덕션으로 간주
    is_production = any(production_indicators)

    if is_production:
        logger.info("🔒 프로덕션 환경 감지됨")
        logger.info(f"   - ENVIRONMENT: {environment or '(미설정)'}")
        logger.info(f"   - NODE_ENV: {node_env or '(미설정)'}")
        logger.info(f"   - WEAVIATE_URL: {weaviate_url[:20]}... (https 여부: {weaviate_url.startswith('https://')})")
        logger.info(f"   - FASTAPI_AUTH_KEY: {'설정됨' if auth_key else '미설정'}")
    else:
        logger.info("🔓 개발 환경으로 판단됨")

    return is_production


def validate_required_env_vars() -> None:
    """
    필수 환경 변수 검증

    프로덕션 환경:
    - FASTAPI_AUTH_KEY 필수
    - GOOGLE_API_KEY, OPENROUTER_API_KEY, WEAVIATE_URL, WEAVIATE_API_KEY, MONGODB_URI 권장

    개발 환경:
    - 경고만 출력

    Raises:
        RuntimeError: 프로덕션 환경에서 필수 변수 누락 시
    """
    is_production = is_production_environment()

    # 프로덕션 필수 변수
    required_vars = ["FASTAPI_AUTH_KEY"]

    # 권장 변수 (프로덕션/개발 모두)
    recommended_vars = [
        "GOOGLE_API_KEY",
        "OPENROUTER_API_KEY",
        "WEAVIATE_URL",
        "WEAVIATE_API_KEY",
        "MONGODB_URI",
    ]

    # 필수 변수 검증
    missing_required = [var for var in required_vars if not os.getenv(var)]

    if missing_required:
        error_msg = (
            f"🚨 CRITICAL: 필수 환경 변수 누락: {', '.join(missing_required)}\n"
            "   프로덕션 환경에서는 반드시 설정해야 합니다."
        )

        if is_production:
            logger.critical(error_msg)
            raise RuntimeError(error_msg)
        else:
            logger.warning(f"⚠️ {error_msg}")
            logger.warning("   개발 환경이므로 경고만 출력합니다.")

    # 권장 변수 검증 (경고만)
    missing_recommended = [var for var in recommended_vars if not os.getenv(var)]

    if missing_recommended:
        logger.warning(f"⚠️ 권장 환경 변수 누락: {', '.join(missing_recommended)}")
        logger.warning("   일부 기능이 제한될 수 있습니다.")
```

#### Step 4: 테스트 통과 확인
```bash
# 예상 결과: 9개 테스트 모두 통과
pytest tests/lib/test_environment.py -v
```

---

### Phase 2: 인증 미들웨어 수정 (Step 5-8)

#### Step 5: 인증 우회 차단 테스트 작성
**파일**: `tests/lib/test_auth_security.py`

```python
"""
API Key 인증 보안 테스트 (TDD)

테스트 시나리오:
1. 프로덕션 환경에서 인증 우회 차단
2. 환경 변수 조작 공격 차단
3. 개발 환경에서 인증 스킵 허용
"""

import os
import pytest
from unittest.mock import AsyncMock
from fastapi import Request, HTTPException


class TestProductionAuthBypass:
    """프로덕션 환경 인증 우회 차단 테스트"""

    def setup_method(self):
        """각 테스트 전에 환경 변수 초기화"""
        for key in ["ENVIRONMENT", "NODE_ENV", "WEAVIATE_URL", "FASTAPI_AUTH_KEY"]:
            os.environ.pop(key, None)

    @pytest.mark.asyncio
    async def test_block_auth_bypass_in_production(self):
        """프로덕션 환경에서 API Key 없이 접근 시도 차단"""
        from app.lib.auth import APIKeyAuth

        # 프로덕션 지표 설정
        os.environ["WEAVIATE_URL"] = "https://weaviate.example.com"

        # API Key 없이 인증 시스템 초기화 시도
        with pytest.raises(RuntimeError, match="FASTAPI_AUTH_KEY must be set in production"):
            APIKeyAuth(api_key=None)

    @pytest.mark.asyncio
    async def test_block_environment_manipulation_in_middleware(self):
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
    async def test_allow_auth_skip_in_development(self):
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

        async def mock_call_next(req):
            return AsyncMock(status_code=200)

        # 인증 스킵되어 정상 처리
        response = await auth.authenticate_request(request, mock_call_next)
        assert response.status_code == 200
```

#### Step 6: 테스트 실패 확인
```bash
# 예상 결과: 3개 테스트 모두 실패 (auth.py 미수정)
pytest tests/lib/test_auth_security.py -v
```

#### Step 7: 인증 미들웨어 수정
**파일**: `app/lib/auth.py`
**수정 위치**: Line 167-182

```python
# 기존 코드 (Line 167-182):
        # 2. API Key가 설정되지 않았으면 인증 스킵 (개발 환경만 허용)
        if not self.api_key:
            # ✅ 런타임 환경 재검증 (이중 안전장치)
            environment = os.getenv("ENVIRONMENT", "development").lower()
            if environment in ["production", "prod"]:
                # 🚨 프로덕션 환경에서는 절대 허용하지 않음
                logger.critical("🚨 CRITICAL: API Key missing in production environment!")
                raise HTTPException(
                    status_code=500,
                    detail="Server configuration error: API authentication not configured",
                )

            # ⚠️ 개발 환경에서만 허용
            logger.warning(f"⚠️ FASTAPI_AUTH_KEY 미설정으로 인증 스킵: {path}")
            logger.warning("   이 동작은 개발 환경에서만 허용됩니다.")
            return await call_next(request)

# 수정 후 코드:
        # 2. API Key가 설정되지 않았으면 인증 스킵 (개발 환경만 허용)
        if not self.api_key:
            # ✅ 다층 환경 감지로 우회 차단
            from .environment import is_production_environment

            if is_production_environment():
                # 🚨 프로덕션 환경에서는 절대 허용하지 않음
                logger.critical("🚨 CRITICAL: API Key missing in production environment!")
                logger.critical("   환경 변수 조작 공격 감지: 프로덕션 지표가 존재합니다.")
                raise HTTPException(
                    status_code=500,
                    detail="Server configuration error: API authentication not configured",
                )

            # ⚠️ 개발 환경에서만 허용
            logger.warning(f"⚠️ FASTAPI_AUTH_KEY 미설정으로 인증 스킵: {path}")
            logger.warning("   이 동작은 개발 환경에서만 허용됩니다.")
            return await call_next(request)
```

**또한 Line 66-92도 함께 수정 필요** (`__init__` 메서드):

```python
# 기존 코드 (Line 66-92):
        # 환경 확인 (기본값: development)
        environment = os.getenv("ENVIRONMENT", "development").lower()
        is_production = environment in ["production", "prod"]

        # API Key 로드 (환경 변수 우선)
        self.api_key = api_key or os.getenv("FASTAPI_AUTH_KEY")

        # 프로덕션 환경에서 API Key 필수 검증
        if not self.api_key:
            if is_production:
                # 🚨 프로덕션: 즉시 중단
                error_msg = (
                    "🚨 CRITICAL: FASTAPI_AUTH_KEY must be set in production!\n"
                    "   Set environment variable: FASTAPI_AUTH_KEY=your-secret-key\n"
                    "   Or pass api_key parameter to APIKeyAuth(api_key='...')"
                )
                logger.critical(error_msg)
                raise RuntimeError(error_msg)
            else:
                # ⚠️ 개발 환경: 경고만 출력
                logger.warning("⚠️ FASTAPI_AUTH_KEY가 설정되지 않았습니다. 인증이 비활성화됩니다.")
                logger.warning("⚠️ 프로덕션 환경에서는 반드시 FASTAPI_AUTH_KEY를 설정하세요!")
                logger.warning(f"   현재 환경: {environment} (개발 모드)")
        else:
            # API Key 설정 완료
            logger.info(f"✅ API Key 인증 활성화 (환경: {environment})")

# 수정 후 코드:
        # 다층 환경 감지
        from .environment import is_production_environment

        is_production = is_production_environment()

        # API Key 로드 (환경 변수 우선)
        self.api_key = api_key or os.getenv("FASTAPI_AUTH_KEY")

        # 프로덕션 환경에서 API Key 필수 검증
        if not self.api_key:
            if is_production:
                # 🚨 프로덕션: 즉시 중단
                error_msg = (
                    "🚨 CRITICAL: FASTAPI_AUTH_KEY must be set in production!\n"
                    "   Set environment variable: FASTAPI_AUTH_KEY=your-secret-key\n"
                    "   Or pass api_key parameter to APIKeyAuth(api_key='...')"
                )
                logger.critical(error_msg)
                raise RuntimeError(error_msg)
            else:
                # ⚠️ 개발 환경: 경고만 출력
                logger.warning("⚠️ FASTAPI_AUTH_KEY가 설정되지 않았습니다. 인증이 비활성화됩니다.")
                logger.warning("⚠️ 프로덕션 환경에서는 반드시 FASTAPI_AUTH_KEY를 설정하세요!")
                logger.warning("   현재 환경: 개발 모드")
        else:
            # API Key 설정 완료
            logger.info(f"✅ API Key 인증 활성화 (환경: {'프로덕션' if is_production else '개발'})")
```

#### Step 8: 테스트 통과 확인
```bash
# 예상 결과: 3개 테스트 모두 통과
pytest tests/lib/test_auth_security.py -v
```

---

### Phase 3: Startup 검증 추가 (Step 9-11)

#### Step 9: main.py 수정
**파일**: `main.py`
**수정 위치**: `lifespan` 함수 (Line 209-243)

```python
# Line 209-243에 추가 (환경 변수 검증 후)

        # 환경 변수 검증 (CRITICAL: 필수 환경 변수 확인)
        logger.info("🔍 환경 변수 검증 시작...")
        validation_result = validate_all_env(strict=False)

        if not validation_result.is_valid:
            missing_vars = validation_result.missing_vars
            help_message = EnvValidator.get_missing_env_help(missing_vars)
            logger.error(f"❌ 필수 환경 변수 누락:\n{help_message}")

            # 필수 환경 변수 없으면 서비스 시작 중단
            if missing_vars:
                raise RuntimeError(
                    f"필수 환경 변수 누락: {', '.join(missing_vars)}\n"
                    "서비스를 시작할 수 없습니다. 환경 변수를 설정해주세요."
                )

        if validation_result.warnings:
            for warning in validation_result.warnings:
                logger.warning(f"⚠️ {warning}")

        logger.info("✅ 환경 변수 검증 완료")

        # 🚨 보안 강화: 프로덕션 환경에서 필수 환경 변수 추가 검증
        from app.lib.environment import is_production_environment, validate_required_env_vars

        if is_production_environment():
            logger.info("🔒 프로덕션 환경 감지 - 필수 환경 변수 검증...")
            validate_required_env_vars()  # FASTAPI_AUTH_KEY 등 필수 검증
            logger.info("✅ 프로덕션 필수 환경 변수 검증 완료")
```

#### Step 10: Startup 검증 테스트 작성
**파일**: `tests/test_main_startup.py`

```python
"""
main.py Startup 검증 테스트 (TDD)

테스트 시나리오:
1. 프로덕션 환경에서 FASTAPI_AUTH_KEY 없이 시작 불가
2. 개발 환경에서 정상 시작
"""

import os
import pytest
from unittest.mock import patch, AsyncMock


class TestMainStartupValidation:
    """main.py Startup 환경 변수 검증 테스트"""

    def setup_method(self):
        """각 테스트 전에 환경 변수 초기화"""
        for key in ["ENVIRONMENT", "NODE_ENV", "WEAVIATE_URL", "FASTAPI_AUTH_KEY"]:
            os.environ.pop(key, None)

    @pytest.mark.asyncio
    async def test_startup_fails_without_auth_key_in_production(self):
        """프로덕션 환경에서 FASTAPI_AUTH_KEY 없이 시작 불가"""
        # 프로덕션 지표 설정
        os.environ["WEAVIATE_URL"] = "https://weaviate.example.com"

        # lifespan 함수 import 및 실행 시도
        with pytest.raises(RuntimeError, match="FASTAPI_AUTH_KEY.*required in production"):
            from app.lib.environment import validate_required_env_vars

            validate_required_env_vars()

    @pytest.mark.asyncio
    async def test_startup_succeeds_in_development(self):
        """개발 환경에서 FASTAPI_AUTH_KEY 없어도 시작 가능"""
        # 개발 환경 설정
        os.environ["ENVIRONMENT"] = "development"
        os.environ["WEAVIATE_URL"] = "http://localhost:8080"

        # 경고만 출력하고 정상 시작
        from app.lib.environment import validate_required_env_vars

        validate_required_env_vars()  # 예외 발생하지 않음
```

#### Step 11: 테스트 통과 확인
```bash
# 예상 결과: 2개 테스트 모두 통과
pytest tests/test_main_startup.py -v
```

---

### Phase 4: 최종 검증 및 문서화 (Step 12-14)

#### Step 12: 전체 테스트 실행
```bash
# 신규 테스트만 실행 (12개)
pytest tests/lib/test_environment.py tests/lib/test_auth_security.py tests/test_main_startup.py -v

# 전체 테스트 실행 (기존 테스트 영향 확인)
pytest tests/ -v
```

**예상 결과**:
- 신규 테스트 12개 모두 통과
- 기존 테스트 모두 통과 (1082개)

#### Step 13: CHANGELOG.md 업데이트

```markdown
# Changelog

## [Unreleased]

### Security
- **[CRITICAL]** SEC-001: 프로덕션 환경 인증 우회 취약점 수정 (CVSS 9.1)
  - 다층 환경 감지 로직 구현 (`app/lib/environment.py`)
  - 단일 환경 변수 조작으로 인증 우회 불가능
  - 프로덕션 지표: ENVIRONMENT, NODE_ENV, WEAVIATE_URL, FASTAPI_AUTH_KEY
  - `app/lib/auth.py` 인증 미들웨어 보안 강화
  - `main.py` 시작 시 프로덕션 환경 필수 변수 검증 추가
  - 12개 보안 테스트 추가 (환경 감지 9개, 인증 3개)
```

#### Step 14: Git 커밋

```bash
# Stage 변경 파일
git add app/lib/environment.py
git add app/lib/auth.py
git add main.py
git add tests/lib/test_environment.py
git add tests/lib/test_auth_security.py
git add tests/test_main_startup.py
git add CHANGELOG.md

# 커밋
git commit -m "security: SEC-001 프로덕션 환경 인증 우회 취약점 수정

🚨 CRITICAL: CVSS 9.1 보안 취약점 완전 차단

문제:
- 단일 환경 변수(ENVIRONMENT) 조작으로 프로덕션 인증 우회 가능
- app/lib/auth.py에서 ENVIRONMENT만으로 환경 판단
- 공격자가 ENVIRONMENT=development 설정 시 인증 완전 우회

해결:
- 다층 환경 감지 로직 구현 (app/lib/environment.py)
  * 4개 프로덕션 지표 종합 판단
  * ENVIRONMENT, NODE_ENV, WEAVIATE_URL(https://), FASTAPI_AUTH_KEY
  * 하나라도 프로덕션 지표 존재 시 프로덕션으로 간주
- 인증 미들웨어 보안 강화 (app/lib/auth.py)
  * is_production_environment() 함수로 환경 검증
  * 환경 변수 조작 공격 차단
- Startup 검증 추가 (main.py)
  * 프로덕션 환경에서 FASTAPI_AUTH_KEY 필수화
  * 서비스 시작 시 환경 변수 검증

테스트:
- 12개 보안 테스트 추가 (100% 통과)
  * 환경 감지: 9개 (프로덕션 지표 개별/복합 감지, 조작 공격 차단)
  * 인증: 3개 (프로덕션 우회 차단, 환경 조작 차단, 개발 허용)
- 기존 테스트 1082개 모두 통과

영향:
- 프로덕션 환경: FASTAPI_AUTH_KEY 필수 (없으면 시작 불가)
- 개발 환경: 기존과 동일 (경고만 출력)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## 검증 체크리스트

구현 완료 후 다음을 확인하세요:

- [ ] 12개 테스트 모두 통과 (환경 감지 9개, 인증 3개)
- [ ] 기존 테스트 1082개 모두 통과
- [ ] 환경 변수 조작 공격이 차단되는지 확인
  ```bash
  # 테스트 방법:
  ENVIRONMENT=development WEAVIATE_URL=https://prod.example.com pytest tests/lib/test_auth_security.py::TestProductionAuthBypass::test_block_environment_manipulation_in_middleware -v
  ```
- [ ] 프로덕션 환경에서 FASTAPI_AUTH_KEY 없이 실행 시 오류 발생
  ```bash
  WEAVIATE_URL=https://prod.example.com python -c "from app.lib.environment import validate_required_env_vars; validate_required_env_vars()"
  ```
- [ ] 개발 환경에서 정상 동작
  ```bash
  ENVIRONMENT=development WEAVIATE_URL=http://localhost:8080 python -c "from app.lib.environment import is_production_environment; print(is_production_environment())"
  ```
- [ ] CHANGELOG.md 업데이트 완료
- [ ] Git 커밋 메시지가 명확하고 상세함

---

## 참고 자료

- CVSS 9.1 평가 근거: 인증 우회 (AC:L/PR:N/UI:N) + 완전한 시스템 제어 (C:H/I:H/A:H)
- OWASP Top 10 2021: A07:2021 – Identification and Authentication Failures
- CWE-287: Improper Authentication

---

**작성일**: 2026-01-08
**작성자**: Security Team
**검토자**: Development Team
**승인자**: CTO
