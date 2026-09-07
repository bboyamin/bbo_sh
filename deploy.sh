#!/bin/bash
# ==========================================
# LocalIssueNotifier 사내 서버 자동 배포 스크립트
# ==========================================

set -e

echo "🚀 LocalIssueNotifier 서버 배포를 시작합니다..."

# 1. Check .env file
if [ ! -f ".env" ]; then
    echo "⚠️ .env 파일이 없습니다. .env.example 복사 중..."
    cp .env.example .env
    echo "❗ .env 파일에 NAVER_CLIENT_ID 및 NAVER_CLIENT_SECRET을 입력해 주세요."
fi

# 2. Check Docker availability
if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
    echo "🐳 Docker 및 Docker Compose 감지됨. 컨테이너 빌드 및 실행 중..."
    docker-compose down || true
    docker-compose up --build -d
    echo "✅ Docker 컨테이너 배포 완료! (포트 8080)"
else
    echo "🐍 Docker 미감지. Python 가상 환경 빌드 실행 중..."
    python3 -m pip install -r requirements.txt
    
    echo "🔄 기존 8080 포트 프로세스 정리 중..."
    lsof -ti :8080 | xargs kill -9 || true
    
    nohup python3 LocalIssueNotifier/server.py > server.log 2>&1 &
    echo "✅ 백그라운드 서버 실행 완료! (포트 8080)"
fi

echo "--------------------------------------------------"
echo "🎉 배포 성공! 아래 주소로 접속 가능합니다:"
echo "👉 http://localhost:8080/index.html"
echo "--------------------------------------------------"
