#!/bin/sh
# Docker 진입점 스크립트
# 목적: 환경변수 확장 및 애플리케이션 실행
# 중요: main.py를 직접 호출하여 PORT 환경변수를 올바르게 처리

# 0. logs 디렉토리 생성 (존재하지 않으면)
mkdir -p /app/logs

# 1. 배치 크롤러 백그라운드 실행 (배포 시 자동 크롤링)
echo "🚀 Starting batch crawler in background..."
# stdout과 파일에 동시 출력 (Railway 로그에서도 확인 가능)
python -m app.batch.main 2>&1 | tee /app/logs/batch-startup.log &
BATCH_PID=$!
echo "✅ Batch crawler started (PID: $BATCH_PID)"
echo "📋 Batch logs: /app/logs/batch-startup.log"

# 2. FastAPI 서버 시작
echo "🌐 Starting FastAPI server..."
exec python main.py
