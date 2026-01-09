#!/usr/bin/env python3
"""
Weaviate NotionMetadata 컬렉션 생성 스크립트

Notion API에서 추출한 구조화 메타데이터를 저장할 별도 컬렉션을 생성합니다.
기존 Documents 컬렉션과 분리하여 데이터 관리를 격리합니다.

사용법:
    python scripts/migrations/002_create_notion_metadata_collection.py
    python scripts/migrations/002_create_notion_metadata_collection.py --dry-run
    python scripts/migrations/002_create_notion_metadata_collection.py --delete-existing

작성일: 2025-12-03
"""

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

# 프로젝트 루트 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.lib.logger import get_logger

logger = get_logger(__name__)

# =============================================================================
# 설정
# =============================================================================

WEAVIATE_URL = os.getenv("WEAVIATE_URL", "https://weaviate-production-70aa.up.railway.app")

# NotionMetadata 컬렉션 스키마
# Documents 컬렉션과 동일하게 vectorizer: none 사용
# (벡터는 업로드 시 직접 제공)
NOTION_METADATA_SCHEMA = {
    "class": "NotionMetadata",
    "description": "Notion API에서 추출한 구조화 메타데이터 (벡터 검색용)",
    "vectorizer": "none",
    "properties": [
        # 청크 콘텐츠 (벡터화 대상)
        {"name": "content", "dataType": ["text"], "description": "청크 텍스트 내용"},
        # 엔티티 식별
        {
            "name": "entity_id",
            "dataType": ["text"],
            "description": "Notion 페이지 UUID",
            "indexFilterable": True,
            "indexSearchable": False,
        },
        {
            "name": "entity_name",
            "dataType": ["text"],
            "description": "엔티티명",
            "indexFilterable": True,
            "indexSearchable": True,
        },
        # 카테고리
        {
            "name": "category",
            "dataType": ["text"],
            "description": "도메인 카테고리 (예: domain_1 | domain_2)",
            "indexFilterable": True,
            "indexSearchable": False,
        },
        {
            "name": "source_file",
            "dataType": ["text"],
            "description": "notion_domain_1 | notion_domain_2",
            "indexFilterable": True,
            "indexSearchable": False,
        },
        # 섹션 분류
        {
            "name": "section",
            "dataType": ["text"],
            "description": "규정 | 비용 | 위치 | 기타",
            "indexFilterable": True,
            "indexSearchable": False,
        },
        # 청킹 메타
        {"name": "chunk_index", "dataType": ["int"], "description": "청크 인덱스"},
        {"name": "total_chunks", "dataType": ["int"], "description": "해당 업체 총 청크 수"},
        {
            "name": "source_field",
            "dataType": ["text"],
            "description": "원본 Notion Property 이름",
            "indexFilterable": True,
            "indexSearchable": False,
        },
        {"name": "token_estimate", "dataType": ["int"], "description": "추정 토큰 수"},
        # 동기화 메타
        {"name": "synced_at", "dataType": ["date"], "description": "동기화 시간 (UTC)"},
        {
            "name": "notion_last_edited",
            "dataType": ["date"],
            "description": "Notion 페이지 최종 수정 시간",
        },
    ],
}


# =============================================================================
# 함수
# =============================================================================


def check_collection_exists(url: str, class_name: str) -> bool:
    """컬렉션 존재 여부 확인"""
    try:
        response = httpx.get(f"{url}/v1/schema/{class_name}", timeout=30.0)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"컬렉션 확인 실패: {e}")
        return False


def delete_collection(url: str, class_name: str) -> bool:
    """컬렉션 삭제"""
    try:
        response = httpx.delete(f"{url}/v1/schema/{class_name}", timeout=30.0)
        if response.status_code in (200, 204):
            logger.info(f"✅ 컬렉션 삭제 완료: {class_name}")
            return True
        else:
            logger.error(f"삭제 실패 (status={response.status_code}): {response.text}")
            return False
    except Exception as e:
        logger.error(f"삭제 오류: {e}")
        return False


def create_collection(url: str, schema: dict, dry_run: bool = False) -> bool:
    """컬렉션 생성"""
    class_name = schema["class"]

    if dry_run:
        logger.info(f"[DRY-RUN] 컬렉션 생성 예정: {class_name}")
        logger.info(f"스키마:\n{json.dumps(schema, indent=2, ensure_ascii=False)}")
        return True

    try:
        response = httpx.post(f"{url}/v1/schema", json=schema, timeout=60.0)

        if response.status_code == 200:
            logger.info(f"✅ 컬렉션 생성 완료: {class_name}")
            return True
        else:
            logger.error(f"생성 실패 (status={response.status_code}): {response.text}")
            return False

    except Exception as e:
        logger.error(f"생성 오류: {e}")
        return False


def get_collection_info(url: str, class_name: str) -> dict | None:
    """컬렉션 정보 조회"""
    try:
        response = httpx.get(f"{url}/v1/schema/{class_name}", timeout=30.0)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None


def main():
    """메인 실행"""
    parser = argparse.ArgumentParser(description="Weaviate NotionMetadata 컬렉션 생성")
    parser.add_argument("--dry-run", action="store_true", help="실제 생성 없이 스키마만 출력")
    parser.add_argument(
        "--delete-existing", action="store_true", help="기존 컬렉션이 있으면 삭제 후 재생성"
    )
    parser.add_argument("--url", type=str, default=WEAVIATE_URL, help="Weaviate URL")

    args = parser.parse_args()

    print("=" * 60)
    print("🚀 Weaviate NotionMetadata 컬렉션 생성")
    print("=" * 60)
    print(f"URL: {args.url}")
    print(f"컬렉션: {NOTION_METADATA_SCHEMA['class']}")
    print(f"Properties: {len(NOTION_METADATA_SCHEMA['properties'])}개")
    print()

    # 1. 기존 컬렉션 확인
    class_name = NOTION_METADATA_SCHEMA["class"]
    exists = check_collection_exists(args.url, class_name)

    if exists:
        logger.info(f"⚠️ 기존 컬렉션 발견: {class_name}")

        if args.delete_existing:
            logger.info("기존 컬렉션 삭제 중...")
            if not delete_collection(args.url, class_name):
                logger.error("삭제 실패. 종료합니다.")
                return
        else:
            # 기존 정보 출력
            info = get_collection_info(args.url, class_name)
            if info:
                prop_count = len(info.get("properties", []))
                logger.info(f"기존 컬렉션 정보: {prop_count}개 properties")

            logger.info("기존 컬렉션을 유지합니다. 삭제하려면 --delete-existing 사용")
            return

    # 2. 컬렉션 생성
    if create_collection(args.url, NOTION_METADATA_SCHEMA, dry_run=args.dry_run):
        if not args.dry_run:
            # 3. 생성 확인
            info = get_collection_info(args.url, class_name)
            if info:
                print()
                print("=" * 60)
                print("✅ 컬렉션 생성 완료")
                print("=" * 60)
                print(f"Class: {info.get('class')}")
                print(f"Vectorizer: {info.get('vectorizer')}")
                print(f"Properties: {len(info.get('properties', []))}개")

                print("\nProperty 목록:")
                for prop in info.get("properties", []):
                    print(f"  - {prop['name']}: {prop['dataType']}")


if __name__ == "__main__":
    main()
