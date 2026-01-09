#!/bin/bash
# Langfuse 중지 스크립트
# 기능: Langfuse 및 모든 의존성 서비스 중지
# 사용: ./scripts/stop-langfuse.sh [--volumes]

set -e

echo "🛑 Langfuse Self-hosted 중지..."

# 프로젝트 루트 디렉토리로 이동
cd "$(dirname "$0")/.."

# 볼륨 삭제 옵션 확인
if [ "$1" == "--volumes" ] || [ "$1" == "-v" ]; then
    echo "⚠️  볼륨도 함께 삭제됩니다 (데이터 손실 주의!)"
    read -p "계속하시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ 중단되었습니다."
        exit 0
    fi

    # 컨테이너 + 볼륨 삭제
    docker compose -f docker-compose.langfuse.yml down -v
    echo "✅ 컨테이너 및 볼륨 삭제 완료"
else
    # 컨테이너만 중지
    docker compose -f docker-compose.langfuse.yml down
    echo "✅ 컨테이너 중지 완료 (볼륨은 유지됨)"
fi

echo ""
echo "📋 참고:"
echo "   재시작: ./scripts/start-langfuse.sh"
echo "   볼륨 포함 삭제: ./scripts/stop-langfuse.sh --volumes"
echo ""
