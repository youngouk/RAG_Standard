"""
환경 감지 및 검증 모듈

다층 환경 감지 로직:
- 명시적 환경 변수(ENVIRONMENT, NODE_ENV)를 최우선으로 판단
- 인프라 기반 체크(HTTPS URL)를 보조 지표로 사용
- 보안 설정(FASTAPI_AUTH_KEY)은 환경 지표로 사용하지 않음

프로덕션 지표:
1. ENVIRONMENT=production 또는 prod
2. NODE_ENV=production 또는 prod
3. WEAVIATE_URL이 https://로 시작

⚠️ 주의: FASTAPI_AUTH_KEY는 보안 설정이므로 환경 감지에 사용하지 않음
- 개발 환경에서도 보안을 위해 AUTH_KEY를 설정할 수 있음
- AUTH_KEY를 환경 지표로 사용하면 개발 환경이 프로덕션으로 오인됨
"""

import os

from .logger import get_logger

logger = get_logger(__name__)


def is_production_environment() -> bool:
    """
    다층 환경 감지 로직으로 프로덕션 환경 여부 판단 (개선된 버전)

    감지 우선순위:
    1. ENVIRONMENT 환경변수 (명시적 설정 최우선)
    2. NODE_ENV 환경변수 (JavaScript 생태계 호환)
    3. 인프라 기반 체크 (HTTPS 사용 여부만)

    ⚠️ 주의: FASTAPI_AUTH_KEY는 보안 설정이므로 환경 감지에 사용하지 않음
    - 개발 환경에서도 보안을 위해 AUTH_KEY를 설정할 수 있음
    - 이를 환경 지표로 사용하면 개발 환경이 프로덕션으로 오인되는 버그 발생

    Returns:
        프로덕션 환경 여부
    """
    # 1. ENVIRONMENT 환경변수 체크 (최우선)
    environment = os.getenv("ENVIRONMENT", "").lower()
    if environment in ("production", "prod"):
        logger.info("🔒 프로덕션 환경 감지됨 (ENVIRONMENT 환경변수)")
        return True
    if environment in ("development", "dev", "test", "local"):
        logger.info("🔓 개발/테스트 환경으로 판단됨 (ENVIRONMENT 환경변수)")
        return False

    # 2. NODE_ENV 체크 (JavaScript 생태계 호환)
    node_env = os.getenv("NODE_ENV", "").lower()
    if node_env in ("production", "prod"):
        logger.info("🔒 프로덕션 환경 감지됨 (NODE_ENV 환경변수)")
        return True
    if node_env in ("development", "dev", "test"):
        logger.info("🔓 개발/테스트 환경으로 판단됨 (NODE_ENV 환경변수)")
        return False

    # 3. 인프라 기반 체크 (HTTPS 사용 여부만)
    weaviate_url = os.getenv("WEAVIATE_URL", "")
    if weaviate_url.startswith("https://"):
        logger.info("🔒 프로덕션 환경 감지됨 (HTTPS Weaviate URL)")
        return True

    # 4. ✅ FASTAPI_AUTH_KEY는 환경 감지에 사용하지 않음 (보안 설정 ≠ 환경 지표)
    # 개발 환경에서도 보안을 위해 AUTH_KEY를 설정할 수 있어야 함

    # 기본값: 개발 환경으로 간주 (안전한 기본값)
    logger.info("🔓 개발 환경으로 판단됨 (명시적 환경 설정 없음)")
    return False


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
            f"필수 환경 변수 누락: {', '.join(missing_required)}. "
            "프로덕션 환경에서는 반드시 설정해야 합니다. "
            ".env 파일에 해당 변수를 추가하세요."
        )
        suggestion_msg = (
            "해결 방법:\n"
            "1. .env 파일에 누락된 환경 변수를 추가하세요\n"
            "2. FASTAPI_AUTH_KEY는 안전한 무작위 문자열을 사용하세요 (예: openssl rand -hex 32)\n"
            "3. .env.example 파일을 참고하여 형식을 확인하세요\n"
            "4. 프로덕션 배포 시 환경 변수가 안전하게 주입되는지 확인하세요"
        )

        if is_production:
            logger.critical(error_msg)
            logger.critical(suggestion_msg)
            raise RuntimeError(f"{error_msg}\n{suggestion_msg}")
        else:
            logger.warning(error_msg)
            logger.warning(suggestion_msg)
            logger.warning("개발 환경이므로 경고만 출력합니다.")

    # 권장 변수 검증 (경고만)
    missing_recommended = [var for var in recommended_vars if not os.getenv(var)]

    if missing_recommended:
        logger.warning(f"⚠️ 권장 환경 변수 누락: {', '.join(missing_recommended)}")
        logger.warning("   일부 기능이 제한될 수 있습니다.")
