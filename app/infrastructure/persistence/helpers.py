"""
데이터베이스 헬퍼 함수

간단한 타임스탬프 자동 생성 함수를 제공합니다.
Supaplate 패턴에서 차용한 헬퍼 유틸리티입니다.

타임존 정책:
- DB 저장: UTC (서버 위치 독립성, 다국적 서비스 대응)
- 화면 표시: 필요 시 KST 변환 (to_kst 함수 사용)
"""

from datetime import UTC, datetime, timedelta, timezone


def timestamps() -> dict[str, datetime]:
    """
    표준 타임스탬프 필드 생성

    created_at, updated_at을 현재 UTC 시간으로 자동 생성합니다.

    Returns:
        dict: {'created_at': datetime, 'updated_at': datetime}

    사용 예시:
        >>> document = {'name': 'test', **timestamps()}
        >>> document
        {'name': 'test', 'created_at': datetime(...), 'updated_at': datetime(...)}
    """
    now = datetime.now(UTC)
    return {"created_at": now, "updated_at": now}


def to_kst(utc_dt: datetime) -> datetime:
    """
    UTC datetime을 KST(한국 표준시)로 변환

    Args:
        utc_dt (datetime): UTC timezone을 가진 datetime 객체

    Returns:
        datetime: KST로 변환된 datetime 객체 (UTC+9)

    사용 예시:
        >>> from app.infrastructure.persistence.helpers import timestamps, to_kst
        >>> ts = timestamps()
        >>> kst_time = to_kst(ts['created_at'])
        >>> print(kst_time)  # 2025-11-05 19:08:33+09:00
    """
    kst = timezone(timedelta(hours=9))
    return utc_dt.astimezone(kst)
