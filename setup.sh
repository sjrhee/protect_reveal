#!/bin/bash

# 스크립트 중단 시 에러 표시
set -e

# 불필요한 권한 제한
umask 022

# 현재 디렉토리
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Python 버전 확인 (3.7 이상 필요)
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
REQUIRED_VERSION="3.7"

if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 이 설치되어 있지 않습니다."
    exit 1
fi

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then 
    echo "Error: Python $REQUIRED_VERSION 이상이 필요합니다. (현재 버전: $PYTHON_VERSION)"
    exit 1
fi

# venv 디렉토리가 있는지 확인
if [ ! -d "$DIR/venv" ]; then
    echo "가상 환경 생성 중..."
    python3 -m venv "$DIR/venv"
else
    echo "기존 가상 환경이 발견되었습니다."
fi

# venv 활성화
source "$DIR/venv/bin/activate"

# pip 업그레이드
echo "pip 업그레이드 중..."
pip install --upgrade pip

# 의존성 설치
echo "의존성 패키지 설치 중..."
pip install -r "$DIR/requirements.txt"

echo "
설정이 완료되었습니다!

가상 환경을 활성화하려면:
    source venv/bin/activate

스크립트를 실행하려면:
    python protect_reveal.py

가상 환경을 비활성화하려면:
    deactivate"