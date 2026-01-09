#!/usr/bin/env python3
"""
Railway PostgreSQL에서 마이그레이션 003 실행 스크립트
목적: batch_runs 테이블의 status CHECK 제약조건에 'running' 상태 추가
"""
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

# 환경변수 로드 (.env 파일 또는 Railway 환경변수)
load_dotenv()

# DATABASE_URL 가져오기
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ DATABASE_URL 환경변수가 설정되지 않았습니다.")
    print("   Railway: railway variables 명령으로 확인하세요")
    sys.exit(1)

# 마이그레이션 SQL 파일 읽기
migration_file = Path(__file__).parent / "migrations" / "003_add_running_status.sql"
if not migration_file.exists():
    print(f"❌ 마이그레이션 파일을 찾을 수 없습니다: {migration_file}")
    sys.exit(1)

with open(migration_file, encoding="utf-8") as f:
    migration_sql = f.read()

print("🔧 Railway PostgreSQL 마이그레이션 시작...")
print(f"📁 파일: {migration_file.name}")
print(f"🔗 DATABASE_URL: {DATABASE_URL[:30]}...")
print()

try:
    # PostgreSQL 연결
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    print("✅ PostgreSQL 연결 성공")

    # 마이그레이션 실행
    cur.execute(migration_sql)
    conn.commit()

    print("✅ 마이그레이션 실행 완료")

    # 제약조건 확인
    cur.execute(
        """
        SELECT conname, pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid = 'batch_runs'::regclass
        AND contype = 'c'
        AND conname = 'batch_runs_status_check';
    """
    )

    result = cur.fetchone()
    if result:
        constraint_name, constraint_def = result
        print(f"✅ CHECK 제약조건 확인: {constraint_name}")
        print(f"   {constraint_def}")
    else:
        print("⚠️  CHECK 제약조건을 찾을 수 없습니다.")

    cur.close()
    conn.close()

    print()
    print("🎉 마이그레이션 성공!")
    print("   이제 배치 크롤러가 정상적으로 실행됩니다.")

except Exception as e:
    print(f"❌ 마이그레이션 실패: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
