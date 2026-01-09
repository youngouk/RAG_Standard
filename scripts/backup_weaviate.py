"""
Weaviate 운영 DB 로컬 백업 스크립트
=====================================
기능: 운영 Weaviate의 모든 Documents를 JSON 파일로 백업
용도: 주요 파이프라인 변경 전 데이터 보존
"""

import json
import os
from datetime import datetime

import requests

# Weaviate 설정
WEAVIATE_URL = "https://weaviate-production-70aa.up.railway.app"
BACKUP_DIR = "data/backups"


def get_all_documents(batch_size: int = 100) -> list[dict]:
    """
    Weaviate에서 모든 Documents를 페이지네이션으로 조회

    Args:
        batch_size: 한 번에 조회할 문서 수

    Returns:
        전체 문서 리스트
    """
    all_docs = []
    offset = 0

    print("📥 Weaviate 데이터 백업 시작...")

    while True:
        query = {
            "query": f"""{{
                Get {{
                    Documents(
                        limit: {batch_size}
                        offset: {offset}
                    ) {{
                        content
                        source_file
                        chunk_index
                        _additional {{
                            id
                        }}
                    }}
                }}
            }}"""
        }

        response = requests.post(
            f"{WEAVIATE_URL}/v1/graphql",
            json=query,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code != 200:
            print(f"❌ API 오류: {response.status_code}")
            break

        data = response.json()

        if "errors" in data:
            print(f"❌ GraphQL 오류: {data['errors']}")
            break

        documents = data.get("data", {}).get("Get", {}).get("Documents", [])

        if not documents:
            break

        all_docs.extend(documents)
        offset += batch_size

        print(f"  📦 {len(all_docs)}개 문서 조회 완료...")

    return all_docs


def save_backup(documents: list[dict]) -> str:
    """
    문서를 JSON 파일로 저장

    Args:
        documents: 백업할 문서 리스트

    Returns:
        저장된 파일 경로
    """
    # 백업 디렉토리 생성
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"weaviate_backup_{timestamp}")
    os.makedirs(backup_path, exist_ok=True)

    # 전체 데이터 저장
    full_backup_file = os.path.join(backup_path, "full_backup.json")
    with open(full_backup_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "backup_timestamp": timestamp,
                "total_documents": len(documents),
                "weaviate_url": WEAVIATE_URL,
                "documents": documents,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    # source_file별로 분리 저장
    by_source: dict[str, list] = {}
    for doc in documents:
        source = doc.get("source_file") or "unknown"
        if source not in by_source:
            by_source[source] = []
        by_source[source].append(doc)

    # 메타데이터 저장
    metadata_file = os.path.join(backup_path, "metadata.json")
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "backup_timestamp": timestamp,
                "total_documents": len(documents),
                "sources": {source: len(docs) for source, docs in by_source.items()},
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    # source별 개별 파일 저장
    sources_dir = os.path.join(backup_path, "by_source")
    os.makedirs(sources_dir, exist_ok=True)

    for source, docs in by_source.items():
        # 파일명에 사용할 수 없는 문자 제거
        safe_name = source.replace("/", "_").replace("\\", "_")
        source_file = os.path.join(sources_dir, f"{safe_name}.json")
        with open(source_file, "w", encoding="utf-8") as f:
            json.dump(docs, f, ensure_ascii=False, indent=2)

    return backup_path


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("🔄 Weaviate 운영 DB 백업")
    print("=" * 60)
    print(f"📍 Source: {WEAVIATE_URL}")
    print(f"📁 Backup Dir: {BACKUP_DIR}")
    print()

    # 전체 문서 조회
    documents = get_all_documents()

    if not documents:
        print("❌ 백업할 문서가 없습니다.")
        return

    print(f"\n✅ 총 {len(documents)}개 문서 조회 완료")

    # 백업 저장
    backup_path = save_backup(documents)

    print(f"\n{'=' * 60}")
    print("✅ 백업 완료!")
    print(f"📁 저장 위치: {backup_path}")
    print(f"📊 총 문서 수: {len(documents)}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
