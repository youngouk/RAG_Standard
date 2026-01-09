#!/bin/bash
# Langfuse 시작 스크립트
# 기능: Langfuse 및 모든 의존성 서비스 시작
# 사용: ./scripts/start-langfuse.sh

set -e

echo "🚀 Langfuse Self-hosted 시작..."

# 프로젝트 루트 디렉토리로 이동
cd "$(dirname "$0")/.."

# .env.langfuse 파일 확인
if [ ! -f ".env.langfuse" ]; then
    echo "❌ .env.langfuse 파일이 없습니다."
    echo "📝 환경 변수 설정 스크립트를 실행하세요:"
    echo "   ./scripts/setup-langfuse-env.sh"
    exit 1
fi

echo ""
echo "🐳 Docker Compose로 서비스 시작 중..."
echo "   - Langfuse Web (포트 3000)"
echo "   - Langfuse Worker"
echo "   - PostgreSQL (포트 5432)"
echo "   - Redis (포트 6379)"
echo "   - ClickHouse (포트 8123, 9000)"
echo "   - MinIO (포트 9000, 9001)"
echo ""

# Docker Compose 시작 (백그라운드)
docker compose -f docker-compose.langfuse.yml --env-file .env.langfuse up -d

echo ""
echo "⏳ 서비스 헬스체크 대기 중..."
sleep 5

# 서비스 상태 확인
echo ""
echo "📊 서비스 상태:"
docker compose -f docker-compose.langfuse.yml ps

echo ""
echo "✅ Langfuse 시작 완료!"
echo ""
echo "📋 접속 정보:"
echo "   🌐 Langfuse Web UI: http://localhost:3000"
echo "   🗄️  PostgreSQL: localhost:5432 (DB: langfuse)"
echo "   🔴 Redis: localhost:6379"
echo "   📊 ClickHouse: http://localhost:8123"
echo "   💾 MinIO Console: http://localhost:9001"
echo ""
echo "📖 로그 확인:"
echo "   docker compose -f docker-compose.langfuse.yml logs -f langfuse-web"
echo ""
echo "🛑 중지:"
echo "   docker compose -f docker-compose.langfuse.yml down"
echo ""
