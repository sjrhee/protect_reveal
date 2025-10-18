# protect_reveal

protect/reveal API와 상호작용하는 파이썬 클라이언트 라이브러리와 CLI 도구입니다. 단건 및 배치(bulk) 처리를 지원하며, 두 모드 모두 동일한 Summary 형식으로 결과를 보여줍니다.

## 프로젝트 구조

```
.
├── protect_reveal/             # 패키지 소스 코드
│   ├── cli.py                  # 통합 CLI 엔트리포인트
│   ├── client.py               # HTTP 클라이언트 및 응답 파서
│   ├── runner.py               # 단건/배치 실행 로직
│   └── utils.py                # 유틸 함수
├── protect_reveal.py           # 얇은 래퍼(패키지 CLI 호출)
├── requirements.txt            # 런타임 의존성
├── requirements-dev.txt        # 개발/테스트 의존성(pytest 등)
├── tests/                      # 단위 테스트
├── setup.sh                    # 빠른 환경 설정 스크립트
└── README.md                   # 이 문서
```

## 주요 기능

- 단건/배치 protect → reveal 처리 및 측정
- HTTP 세션 재사용으로 성능 최적화
- 견고한 에러 처리(APIError, 비성공 응답도 구조화해 반환)
- 옵션에 따른 진행 로그/본문 출력 제어
- 두 모드 모두 동일한 Summary 출력 형식

## 설치 및 설정

### 요구사항

- Python 3.10 이상 권장(3.8+ 동작 가능)
- bash 쉘 환경(Linux/Mac)

### 빠른 설정

```bash
./setup.sh
source venv/bin/activate
```

### 수동 설정(.venv 권장)

```bash
# 가상환경 생성
python3 -m venv .venv
source .venv/bin/activate

# 런타임 의존성 설치
pip install -r requirements.txt

# (선택) 개발 의존성 설치 및 테스트 실행
pip install -r requirements-dev.txt
pytest -q
```

## 사용법

### 기본 실행

```bash
python protect_reveal.py
```

### 주요 명령행 옵션

```
--host HOST           API 호스트 (기본: 192.168.0.231)
--port PORT           API 포트 (기본: 32082)
--policy POLICY       보호 정책 이름 (기본: P03)
--start-data DATA     시작 데이터 (기본: 0123456789123)
--iterations N        반복 횟수 (기본: 100)
--timeout SEC         요청 타임아웃(초, 기본: 10)
--verbose             디버그 로깅 활성화
--show-bodies         요청/응답 본문 출력
--show-progress       진행 상황 출력

--bulk                배치 모드 사용(ProtectBulk/RevealBulk)
--batch-size N        배치 크기(기본: 25)
```

메시지 본문(JSON)은 기본적으로 출력하지 않습니다. `--show-bodies`를 주면 다음을 출력합니다.
- 단건 모드: 각 반복의 protect/reveal 결과를 배치 모드와 동일한 JSON 구조로 출력
- 배치 모드: 각 배치의 protect/reveal 결과를 JSON으로 출력

### 출력 형식

두 모드 모두 실행 후 동일한 Summary 블록을 출력합니다.

```
Summary:
Iterations attempted: <총 시도 개수>
Successful (both 2xx): <성공(둘 다 2xx) 개수>
Revealed matched original data: <원본과 일치 개수>
Total time: <전체 벽시계 시간(s)>
Average per-iteration time: <반복당 평균 시간(s)>
```

배치 모드에서 평균 시간은 “각 배치 처리 시간 합 / 총 아이템 수”로 계산합니다.

### 예시

```bash
# 기본 실행(단건)
python protect_reveal.py

# 배치 모드(기본 배치 25개)
python protect_reveal.py --bulk

# 본문/진행 로그 확인
python protect_reveal.py --iterations 10 --show-bodies --show-progress
```

## 에러 처리

- `APIError`: API 호출 중 예외 상황을 표현. `status_code`, `response` 포함.
- 비성공(4xx/5xx) 응답도 `APIResponse`로 감싸 처리하여, 배치 중 일부 실패가 있어도 가능한 범위에서 계속 진행합니다.

## 개발 및 테스트

```bash
git clone <repository-url>
cd protect_reveal

# 권장: .venv 사용
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
pip install -r requirements-dev.txt
pytest -q
```

테스트 항목에는 배치 실행의 정상/부분 실패 케이스가 포함됩니다.
