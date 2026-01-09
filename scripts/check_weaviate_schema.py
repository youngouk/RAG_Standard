#!/usr/bin/env python3
"""Weaviate 스키마 확인"""


import requests

WEAVIATE_URL = "https://weaviate-production-70aa.up.railway.app"

try:
    response = requests.get(f"{WEAVIATE_URL}/v1/schema", timeout=10)
    schema = response.json()

    # Documents 클래스 찾기
    for cls in schema.get("classes", []):
        if cls["class"] == "Documents":
            print("📋 Documents 클래스 필드:\n")
            for prop in cls["properties"]:
                print(f"  - {prop['name']}: {prop['dataType']}")
            break
except Exception as e:
    print(f"❌ 에러: {e}")
