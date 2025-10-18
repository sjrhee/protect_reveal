# protect_reveal

이 레포지토리에는 protect/reveal API와 상호작용하는 파이썬 클라이언트 라이브러리와 CLI 도구가 포함되어 있습니다.

## 프로젝트 구조

```
.
├── protect_reveal.py  # 메인 파이썬 스크립트
├── requirements.txt   # 의존성 목록
├── setup.sh           # 설치 스크립트
├── README.md          # 문서
└── (venv/)            # 가상 환경 (로컬에서 자동 생성; 저장소에 커밋하지 마세요)
```

## 기능

- 재사용 가능한 API 클라이언트 라이브러리
- HTTP 연결 재사용을 통한 성능 최적화
- 강력한 타입 힌트와 에러 처리
- 상세한 진행 상황 및 통계 보고
- 사용자 정의 가능한 설정

## 설치 및 설정

### 요구사항

- Python 3.7 이상
- bash 쉘 환경

### 빠른 설정

포함된 설정 스크립트를 사용하여 자동으로 가상 환경을 생성하고 의존성을 설치할 수 있습니다:

```bash
./setup.sh
```

### 수동 설정

가상 환경을 수동으로 설정하려면:

```bash
# 가상 환경 생성
python3 -m venv venv

# 가상 환경 활성화
source venv/bin/activate  # Linux/Mac
# 또는
.\venv\Scripts\activate   # Windows

# 의존성 설치
pip install -r requirements.txt
```

## 사용법

### 가상 환경 활성화

스크립트를 실행하기 전에 항상 가상 환경을 활성화해야 합니다:

```bash
source venv/bin/activate  # Linux/Mac
# 또는
.\venv\Scripts\activate   # Windows
```

작업이 끝난 후에는 가상 환경을 비활성화할 수 있습니다:
```bash
deactivate
```

### 기본 실행

```bash
python3 protect_reveal.py
```

### 주요 명령행 옵션

```
--host HOST           API 호스트 (기본값: 192.168.0.231)
--port PORT           API 포트 (기본값: 32082)
--policy POLICY       보호 정책 이름 (기본값: P03)
--start-data DATA     시작 데이터 (기본값: 0123456789123)
--iterations N        반복 횟수 (기본값: 100)
--timeout SEC         요청 타임아웃 (기본값: 10초)
--verbose             디버그 로깅 활성화
--show-bodies         요청/응답 본문 출력
--show-progress       진행 상황 출력 활성화 (기본값: 비활성화)

--bulk                bulk(배치) 모드 사용 (프로텍트/리빌 연산을 배치로 처리)
--batch-size N        bulk 모드의 배치 크기 (기본값: 25)
--show-bodies         bulk 모드에서 요청/응답 본문을 출력 (기본: 비활성화)
```

기본적으로 진행 상황 출력은 비활성화(OFF)입니다. 대량 반복이나 디버깅이 필요할 때 실시간 진행 상태를 보려면 `--show-progress` 옵션을 사용하세요.

### 예시 실행

```bash
# 사용자 정의 호스트와 포트로 실행
python3 protect_reveal.py --host api.example.com --port 8443

# 디버그 모드로 10회 반복 실행
python3 protect_reveal.py --iterations 10 --verbose --show-bodies

# 다른 시작 데이터와 정책으로 실행
python3 protect_reveal.py --policy CustomPolicy --start-data 9876543210
```

## 에러 처리

라이브러리는 다음과 같은 예외를 발생시킬 수 있습니다:

- `APIError`: API 호출 중 발생한 오류
    - `status_code`: HTTP 상태 코드
    - `response`: 원본 응답 객체

## 개발 환경 설정

이 프로젝트의 개발에 참여하려면:

1. 저장소 복제
```bash
git clone <repository-url>
cd protect_reveal
```

2. 가상 환경 설정

```bash
./setup.sh
source venv/bin/activate
```

3. 코드 수정 및 테스트

```bash
python protect_reveal.py --verbose  # 테스트 실행
```
# 테스트

개발 중 테스트를 실행하려면 가상환경을 만들고 의존성을 설치한 뒤 pytest를 실행하세요:

```bash
# 가상환경 생성 (권장 이름: .venv)
python3 -m venv .venv
source .venv/bin/activate

# 개발 의존성 설치
python -m pip install --upgrade pip
pip install -r requirements-dev.txt

# 테스트 실행
pytest -q
```
# CRDP
