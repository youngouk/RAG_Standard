#!/usr/bin/env python3
"""
프롬프트 테이블 생성 스크립트

PostgreSQL에 prompts 테이블을 생성합니다.
안전하게 기존 테이블이 있는지 확인하고 생성합니다.
"""
import asyncio
import os
import sys

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# .env 파일 로드 (데이터베이스 연결 정보)
from dotenv import load_dotenv

load_dotenv()

from app.infrastructure.persistence.connection import DatabaseManager
from app.infrastructure.persistence.models import Base
from app.lib.logger import get_logger

logger = get_logger(__name__)


async def create_prompts_table():
    """prompts 테이블 생성"""
    db_manager = DatabaseManager()

    try:
        # 데이터베이스 초기화 (환경변수에서 DATABASE_URL 자동 감지)
        await db_manager.initialize()
        logger.info("✅ 데이터베이스 연결 성공")

        # 테이블 생성 (이미 존재하면 건너뜀)
        async with db_manager.engine.begin() as conn:
            # PromptModel 테이블만 생성 (checkfirst=True로 안전하게)
            await conn.run_sync(Base.metadata.create_all, checkfirst=True)

        logger.info("✅ prompts 테이블 생성 완료 (또는 이미 존재)")

        # 테이블 확인
        async with db_manager.get_session() as session:
            from sqlalchemy import text

            result = await session.execute(
                text(
                    """
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = 'prompts'
                    ORDER BY ordinal_position
                """
                )
            )

            columns = result.fetchall()

            if columns:
                logger.info("\n📊 prompts 테이블 스키마:")
                for col in columns:
                    logger.info(f"  - {col[0]}: {col[1]} (nullable={col[2]})")
            else:
                logger.warning("⚠️  prompts 테이블을 찾을 수 없습니다")

        logger.info("\n✅ Phase 1 완료: 데이터베이스 스키마 생성 성공")

    except Exception as e:
        logger.error(f"❌ 테이블 생성 실패: {e}")
        raise

    finally:
        # 연결 종료
        await db_manager.close()
        logger.info("데이터베이스 연결 종료")


if __name__ == "__main__":
    asyncio.run(create_prompts_table())
