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
    production_indicators: list[bool] = []

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
        logger.info(
            f"   - WEAVIATE_URL: {weaviate_url[:20]}... (https 여부: {weaviate_url.startswith('https://')})"
        )
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
