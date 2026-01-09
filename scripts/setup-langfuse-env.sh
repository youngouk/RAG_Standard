#!/bin/bash
# Langfuse 환경 변수 자동 생성 스크립트
# 기능: 보안 시크릿 자동 생성 및 .env.langfuse 파일 생성
# 사용: ./scripts/setup-langfuse-env.sh

set -e

echo "🔐 Langfuse 환경 변수 설정 시작..."

# 프로젝트 루트 디렉토리로 이동
cd "$(dirname "$0")/.."

# .env.langfuse 파일이 이미 존재하는지 확인
if [ -f ".env.langfuse" ]; then
    echo "⚠️  .env.langfuse 파일이 이미 존재합니다."
    read -p "덮어쓰시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ 중단되었습니다."
        exit 0
    fi
fi

echo ""
echo "🔑 보안 시크릿 생성 중..."

# 보안 시크릿 생성
NEXTAUTH_SECRET=$(openssl rand -base64 32)
SALT=$(openssl rand -base64 32)
ENCRYPTION_KEY=$(openssl rand -hex 32)

echo "✅ NEXTAUTH_SECRET 생성 완료"
echo "✅ SALT 생성 완료"
echo "✅ ENCRYPTION_KEY 생성 완료"

echo ""
echo "📝 비밀번호 설정..."

# 기본값 또는 사용자 입력
read -p "PostgreSQL 비밀번호 (기본값: langfuse_password): " POSTGRES_PASSWORD
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-langfuse_password}

read -p "MinIO 비밀번호 (기본값: minioadmin): " MINIO_ROOT_PASSWORD
MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD:-minioadmin}

echo ""
echo "📄 .env.langfuse 파일 생성 중..."

# .env.langfuse 파일 생성
cat > .env.langfuse << EOF
# Langfuse Self-hosted 환경 변수
# 자동 생성: $(date '+%Y-%m-%d %H:%M:%S')

# =============================================================================
# 보안 시크릿 (자동 생성됨 - 백업 필수!)
# =============================================================================

NEXTAUTH_SECRET=${NEXTAUTH_SECRET}
SALT=${SALT}
ENCRYPTION_KEY=${ENCRYPTION_KEY}

# =============================================================================
# PostgreSQL 설정
# =============================================================================

POSTGRES_USER=langfuse
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_DB=langfuse

# =============================================================================
# ClickHouse 설정
# =============================================================================

CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=
CLICKHOUSE_DB=default

# =============================================================================
# MinIO 설정
# =============================================================================

MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD}
EOF

echo "✅ .env.langfuse 파일 생성 완료!"
echo ""
echo "⚠️  중요: 이 파일을 안전한 곳에 백업하세요!"
echo "   생성된 시크릿은 재생성할 수 없으며, 분실 시 데이터 복구가 불가능합니다."
echo ""
echo "📋 다음 단계:"
echo "   1. .env.langfuse 파일 백업 (권장)"
echo "   2. Langfuse 시작: docker compose -f docker-compose.langfuse.yml --env-file .env.langfuse up -d"
echo "   3. 웹 UI 접속: http://localhost:3000"
echo ""
