#!/bin/bash

# 창이 열리면 현재 스크립트가 있는 폴더로 자동 이동
cd "$(dirname "$0")"

echo "============================================"
echo "      경북대 학식 디스코드 전송 봇 (로컬)      "
echo "============================================"

# .env 파일 체크
if [ ! -f ".env" ]; then
    echo "[!] 경고: .env 파일이 없습니다!"
    echo "    .env.example 파일을 복사하여 .env 로 이름을 바꾼 뒤,"
    echo "    디스코드 토큰과 채널 ID를 채워주세요."
    echo ""
    read -p "엔터를 누르면 종료됩니다..."
    exit 1
fi

echo "[*] 가상 환경 및 필수 패키지 확인 중..."

# 가상 환경이 없으면 생성
if [ ! -d ".venv" ]; then
    echo "[*] 새로운 가상 환경(.venv)을 생성합니다..."
    python3 -m venv .venv
fi

# macOS/bash, zsh 용 가상환경 활성화
source .venv/bin/activate

# 필요 패키지 설치 유무 확인 및 자동 설치
pip install -r requirements.txt -q

echo "[*] 식단 정보를 가져옵니다. 잠시만 기다려주세요..."
python3 -m src.main

echo "============================================"
echo "[완료] 봇 실행이 종료되었습니다. 창을 닫으셔도 됩니다."
read -p "엔터를 누르면 종료됩니다..."
