#!/usr/bin/env python3
"""
배치 시스템 PostgreSQL 테이블 생성 스크립트

주요 기능:
- 배치 시스템 테이블 3개 생성 (batch_runs, batch_source_logs, parsing_rules)
- 인덱스 8개 생성
- 초기 파싱 규칙 데이터 삽입 (6개 소스)

실행 방법:
    python scripts/setup_batch_tables.py

환경변수:
    DATABASE_URL: PostgreSQL 연결 문자열
"""

import os
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# .env 파일 로드 (DATABASE_URL 등 환경변수)
from dotenv import load_dotenv

load_dotenv(project_root / ".env")

from sqlalchemy import create_engine, text

from app.lib.logger import get_logger

logger = get_logger(__name__)


def get_database_url() -> str:
    """
    DATABASE_URL 환경변수 가져오기

    Returns:
        str: PostgreSQL 연결 문자열

    Raises:
        ValueError: DATABASE_URL 환경변수가 설정되지 않은 경우
    """
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError(
            "❌ DATABASE_URL 환경변수가 설정되지 않았습니다.\n"
            "   export DATABASE_URL='postgresql://user:password@host:port/database'"
        )

    # Railway 환경의 postgres:// → postgresql:// 변환
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
        logger.info("🔄 DATABASE_URL 형식 변환: postgres:// → postgresql://")

    return database_url


def execute_sql_file(engine, file_path: Path) -> bool:
    """
    SQL 파일 실행

    Args:
        engine: SQLAlchemy 엔진
        file_path: SQL 파일 경로

    Returns:
        bool: 실행 성공 여부
    """
    if not file_path.exists():
        logger.error(f"❌ SQL 파일 없음: {file_path}")
        return False

    logger.info(f"📄 실행 중: {file_path.name}")

    try:
        # SQL 파일 읽기
        with open(file_path, encoding="utf-8") as f:
            sql_content = f.read()

        # 트랜잭션으로 실행
        with engine.connect() as conn:
            trans = conn.begin()
            try:
                # text()로 감싸서 SQLAlchemy에 SQL 문자열임을 명시
                conn.execute(text(sql_content))
                trans.commit()
                logger.info(f"✅ 완료: {file_path.name}")
                return True

            except Exception as e:
                trans.rollback()
                logger.error(f"❌ 실패: {file_path.name} - {e}")
                raise

    except Exception:
        logger.error(f"❌ SQL 파일 실행 실패: {file_path.name}", exc_info=True)
        return False


def verify_tables(engine) -> bool:
    """
    테이블 생성 검증

    Args:
        engine: SQLAlchemy 엔진

    Returns:
        bool: 검증 성공 여부
    """
    logger.info("🔍 테이블 생성 검증 중...")

    try:
        with engine.connect() as conn:
            # 테이블 존재 확인
            tables_query = text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name IN ('batch_runs', 'batch_source_logs', 'parsing_rules')
                ORDER BY table_name;
            """
            )

            result = conn.execute(tables_query)
            tables = [row[0] for row in result]

            logger.info(f"✅ 생성된 테이블: {', '.join(tables)}")

            # 파싱 규칙 개수 확인
            parsing_rules_query = text("SELECT COUNT(*) FROM parsing_rules;")
            result = conn.execute(parsing_rules_query)
            rule_count = result.scalar()

            logger.info(f"✅ 초기 파싱 규칙: {rule_count}개 소스")

            # 인덱스 확인
            indexes_query = text(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE tablename IN ('batch_runs', 'batch_source_logs', 'parsing_rules')
                AND schemaname = 'public'
                ORDER BY indexname;
            """
            )

            result = conn.execute(indexes_query)
            indexes = [row[0] for row in result]

            logger.info(f"✅ 생성된 인덱스: {len(indexes)}개")

            return len(tables) == 3 and rule_count == 6

    except Exception as e:
        logger.error(f"❌ 검증 실패: {e}", exc_info=True)
        return False


def main():
    """메인 실행 함수"""
    logger.info("=" * 70)
    logger.info("🚀 배치 시스템 PostgreSQL 테이블 생성 시작")
    logger.info("=" * 70)

    try:
        # 1. DATABASE_URL 가져오기
        database_url = get_database_url()
        logger.info("✅ DATABASE_URL 확인 완료")

        # 2. SQLAlchemy 엔진 생성
        engine = create_engine(database_url, echo=False)
        logger.info("✅ PostgreSQL 연결 성공")

        # 3. 마이그레이션 파일 경로
        migrations_dir = project_root / "scripts" / "migrations"

        sql_files = [
            "002_create_batch_tables.sql",
            "003_insert_initial_parsing_rules.sql",
        ]

        # 4. 각 SQL 파일 실행
        logger.info("")
        logger.info("📊 마이그레이션 실행 중...")
        logger.info("")

        for sql_file in sql_files:
            file_path = migrations_dir / sql_file
            success = execute_sql_file(engine, file_path)

            if not success:
                logger.error(f"❌ 마이그레이션 중단: {sql_file}")
                sys.exit(1)

        # 5. 테이블 생성 검증
        logger.info("")
        logger.info("📊 검증 중...")
        logger.info("")

        verify_success = verify_tables(engine)

        if verify_success:
            logger.info("")
            logger.info("=" * 70)
            logger.info("✅ 배치 시스템 테이블 생성 완료!")
            logger.info("=" * 70)
            logger.info("")
            logger.info("📊 생성된 테이블:")
            logger.info("   1. batch_runs (배치 실행 이력)")
            logger.info("   2. batch_source_logs (소스별 크롤링 로그)")
            logger.info("   3. parsing_rules (파싱 규칙 저장소)")
            logger.info("")
            logger.info("📊 초기 데이터:")
            logger.info("   - 샘플 데이터 소스 파싱 규칙")
            logger.info("")
            logger.info("⚠️ 다음 작업:")
            logger.info("   1. parsing_rules 테이블의 실제 크롤링 URL 수정")
            logger.info("   2. content_selector 검증 및 조정")
            logger.info("   3. validation_config 최적화")
            logger.info("")

        else:
            logger.error("❌ 테이블 생성 검증 실패")
            sys.exit(1)

    except Exception as e:
        logger.error(f"❌ 마이그레이션 실패: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
