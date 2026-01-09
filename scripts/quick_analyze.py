#!/usr/bin/env python3
"""프로덕션 Weaviate 빠른 분석 (Railway 환경 전용)"""
import sys
from collections import Counter
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.lib.weaviate_client import get_weaviate_client


def main():
    client = get_weaviate_client()

    if not client.client or not client.client.is_ready():
        print("ERROR: Weaviate 연결 실패")
        return

    if not client.client.collections.exists("Documents"):
        print("ERROR: Documents 컬렉션 없음")
        return

    collection = client.client.collections.get("Documents")
    result = collection.aggregate.over_all(total_count=True)
    total = result.total_count

    print(f"\n총 청크 수: {total:,}개\n")

    # 배치로 소스별 통계 수집
    source_counter = Counter()
    data_source_counter = Counter()

    batch_size = 1000
    offset = 0

    while offset < total:
        batch = collection.query.fetch_objects(
            limit=batch_size,
            offset=offset,
            return_properties=["source", "data_source"]
        )

        if not batch.objects:
            break

        for obj in batch.objects:
            props = obj.properties
            source_counter[props.get("source", "Unknown")] += 1
            data_source_counter[props.get("data_source", "Unknown")] += 1

        offset += batch_size
        print(f"처리: {min(offset, total):,} / {total:,}", end="\r")

    print("\n\n=== 소스별 분포 (source) ===")
    for source, count in source_counter.most_common():
        pct = (count / total) * 100
        print(f"{source:30s}: {count:6,}개 ({pct:5.1f}%)")

    print("\n=== 데이터 소스별 분포 (data_source) ===")
    for ds, count in data_source_counter.most_common():
        pct = (count / total) * 100
        print(f"{ds:30s}: {count:6,}개 ({pct:5.1f}%)")

if __name__ == "__main__":
    main()
