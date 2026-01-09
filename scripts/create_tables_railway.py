"""
Railway PostgreSQL 테이블 생성 스크립트
Railway 환경에서 실행하여 배치 시스템 테이블을 생성합니다.
"""

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text


def create_batch_tables():
    """배치 시스템 테이블 생성"""

    # 1. DATABASE_URL 가져오기
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print("❌ DATABASE_URL 환경변수가 없습니다.")
        sys.exit(1)

    # Railway postgres:// → postgresql:// 변환
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    print(f"✅ DATABASE_URL 확인: {database_url[:50]}...")

    # 2. SQL 파일 읽기
    sql_file = Path(__file__).parent / "migrations" / "002_create_batch_tables.sql"

    if not sql_file.exists():
        print(f"❌ SQL 파일이 없습니다: {sql_file}")
        sys.exit(1)

    print(f"✅ SQL 파일 확인: {sql_file}")

    with open(sql_file, encoding="utf-8") as f:
        sql_content = f.read()

    # 3. PostgreSQL 연결
    try:
        engine = create_engine(database_url, pool_pre_ping=True)
        print("✅ PostgreSQL 연결 성공")

        # 4. SQL 실행
        with engine.connect() as conn:
            # 트랜잭션 시작
            trans = conn.begin()

            try:
                # SQL 파일 실행 (여러 문장으로 분리)
                statements = [s.strip() for s in sql_content.split(";") if s.strip()]

                for i, statement in enumerate(statements, 1):
                    if statement:
                        print(f"📝 문장 {i}/{len(statements)} 실행 중...")
                        conn.execute(text(statement))

                # 커밋
                trans.commit()
                print("✅ 모든 테이블 생성 완료!")

            except Exception as e:
                trans.rollback()
                print(f"❌ SQL 실행 실패: {e}")
                raise

        # 5. 테이블 확인
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name IN ('batch_runs', 'batch_source_logs', 'parsing_rules')
                ORDER BY table_name;
            """
                )
            )

            tables = [row[0] for row in result]

            if len(tables) == 3:
                print("\n✅ 테이블 생성 확인:")
                for table in tables:
                    print(f"   - {table}")
                print("\n🎉 Railway PostgreSQL 테이블 생성 성공!")
            else:
                print(f"\n⚠️ 예상과 다른 테이블 개수: {len(tables)}/3")
                for table in tables:
                    print(f"   - {table}")

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        sys.exit(1)


if __name__ == "__main__":
    create_batch_tables()
