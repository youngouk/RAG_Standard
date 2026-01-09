#!/usr/bin/env python3
"""
Weaviate 데이터 확인 스크립트

Railway 환경에서 Weaviate에 저장된 데이터를 확인합니다.

실행 방법:
    railway run python scripts/check_weaviate.py
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.lib.logger import get_logger
from app.lib.weaviate_client import get_weaviate_client

logger = get_logger(__name__)


async def check_weaviate_data():
    """Weaviate 데이터 존재 여부 및 상태 확인"""
    try:
        logger.info("=" * 60)
        logger.info("🔍 Weaviate 데이터 확인 시작")
        logger.info("=" * 60)

        # Weaviate 클라이언트 가져오기
        weaviate_client = get_weaviate_client()

        if weaviate_client.client is None:
            logger.error("❌ Weaviate 연결 실패")
            return

        client = weaviate_client.client

        # 1. 연결 상태 확인
        if client.is_ready():
            logger.info("✅ Weaviate 연결 성공")
        else:
            logger.error("❌ Weaviate 준비되지 않음")
            return

        # 2. Documents Collection 존재 확인
        if not client.collections.exists("Documents"):
            logger.error("❌ Documents 스키마 없음")
            logger.info("📝 해결 방법: WEAVIATE_AUTO_INIT=true 설정 후 재배포")
            return

        logger.info("✅ Documents 스키마 존재")

        # 3. 문서 개수 확인
        collection = client.collections.get("Documents")

        # 전체 문서 개수 확인
        result = collection.aggregate.over_all(total_count=True)
        count = result.total_count

        logger.info("=" * 60)
        logger.info(f"📊 저장된 문서 개수: {count}개")
        logger.info("=" * 60)

        if count == 0:
            logger.warning("⚠️  데이터 없음 - Weaviate에 문서가 없습니다")
            logger.info("📝 해결 방법:")
            logger.info("   1. python3 scripts/index_all_data.py")
            logger.info("   2. 또는 WEAVIATE_AUTO_INDEX=true 설정 후 재배포")
            return

        logger.info(f"✅ 데이터 인덱싱 성공: {count}개 문서")

        # 4. 샘플 문서 출력
        logger.info("=" * 60)
        logger.info("📄 샘플 문서:")
        logger.info("=" * 60)

        sample = collection.query.fetch_objects(limit=3)

        for i, obj in enumerate(sample.objects, 1):
            props = obj.properties
            logger.info(f"\n[문서 {i}]")
            logger.info(f"  UUID: {obj.uuid}")
            logger.info(f"  내용: {props.get('content', 'N/A')[:150]}...")
            logger.info(f"  출처: {props.get('source', 'N/A')}")

            # Flat structure로 변경됨 (metadata nested 구조 아님)
            if props.get("entity_name"):
                logger.info(f"  이름: {props.get('entity_name')}")
            if props.get("location"):
                logger.info(f"  위치: {props.get('location')}")
            if props.get("price"):
                logger.info(f"  가격: {props.get('price')}")
            if props.get("capacity"):
                logger.info(f"  수용인원: {props.get('capacity')}명")
            if props.get("rating"):
                logger.info(f"  평점: {props.get('rating')}")

        # 5. 검색 테스트 (데이터가 있을 때만)
        if count > 0:
            logger.info("=" * 60)
            logger.info("🔍 검색 테스트: '서울 지점'")
            logger.info("=" * 60)

            # OpenAI Embedding 생성
            from app.modules.core.embedding.openai_embedder import OpenAIEmbedder

            embedder = OpenAIEmbedder()

            query = "서울 지점"
            vector = await embedder.embed_query(query)

            # 하이브리드 검색 (return_properties 명시)
            search_results = collection.query.hybrid(
                query=query,
                vector=vector,
                limit=3,
                alpha=0.6,
                return_properties=[
                    "content",
                    "entity_name",
                    "location",
                    "price",
                    "capacity",
                    "rating",
                    "source",
                    "created_at",
                ],
            )

            if search_results.objects:
                logger.info(f"✅ 검색 성공: {len(search_results.objects)}개 결과")

                for i, obj in enumerate(search_results.objects, 1):
                    props = obj.properties
                    logger.info(f"\n[검색 결과 {i}]")
                    logger.info(f"  점수: {obj.metadata.score if obj.metadata.score else 'N/A'}")
                    logger.info(f"  내용: {props.get('content', 'N/A')[:100]}...")
                    if props.get("entity_name"):
                        logger.info(f"  이름: {props.get('entity_name')}")
                    if props.get("location"):
                        logger.info(f"  위치: {props.get('location')}")
            else:
                logger.warning("⚠️  검색 결과 없음")

        logger.info("=" * 60)
        logger.info("✅ Weaviate 데이터 확인 완료")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"❌ 오류 발생: {e}", exc_info=True)


if __name__ == "__main__":
    import asyncio

    asyncio.run(check_weaviate_data())
