# protect_reveal

protect/reveal API와 상호작용하는 파이썬 클라이언트 라이브러리와 CLI 도구입니다. 단건 및 배치(bulk) 처리를 지원하며, 두 모드 모두 동일한 Summary 형식으로 결과를 보여줍니다.

## 프로젝트 구조

```
# protect_reveal

Protect/Reveal API 클라이언트 & CLI. 단건·배치 모두 지원하며, 두 모드의 Summary 형식은 동일합니다.

## 목차
- 소개(특징)
- 빠른 시작(Quick Start)
- 명령행 옵션(표)
- 출력 예시(요청/응답, Summary)
- 보안 주의사항
- 프로젝트 구조
- 개발/테스트

## 소개(특징)
- 단건/배치 Protect → Reveal 처리 및 시간 측정
- HTTP 세션 재사용으로 성능 최적화
- 견고한 에러 처리(APIError 래핑, 일부 실패에도 진행)
- `--show-bodies` 시 요청 메타(url/headers/body)와 서버 응답(JSON 원문) 출력
- 두 모드 모두 동일한 Summary 출력 형식

## 빠른 시작(Quick Start)
```bash
# 1) 가상환경과 의존성
./setup.sh && source .venv/bin/activate

# 2) 기본 실행(단건)
python protect_reveal.py

# 3) 배치 실행(기본 배치 25)
python protect_reveal.py --bulk

# 4) 본문/진행 로그 확인
python protect_reveal.py --iterations 10 --show-bodies --show-progress

# 5) JWT 토큰 헤더로 전달
python protect_reveal.py --auth-bearer "$(cat protect_reveal/token.txt)" --iterations 10

# 6) JWT 모드 + username 포함(reveal에 username 포함)
python protect_reveal.py --use-jwt --username alice --auth-bearer "$(cat protect_reveal/token.txt)" --iterations 10
```

## 명령행 옵션(표)

| 옵션 | 설명 | 기본값 |
|---|---|---|
| --host | API 호스트 | 192.168.0.231 |
| --port | API 포트 | 32082 |
| --policy | 보호 정책 이름 | P03 |
| --start-data | 시작 데이터 | 1234567890123 |
| --iterations | 반복 횟수 | 100 |
| --timeout | 요청 타임아웃(초) | 10 |
| --verbose | 디버그 로깅 | false |
| --show-bodies | 요청 url/headers/body와 응답 JSON 출력 | false |
| --show-progress | 진행 상황 출력 | false |
| --bulk | 배치 모드(ProtectBulk/RevealBulk) | false |
| --batch-size | 배치 크기 | 25 |
| --use-jwt | JWT 모드 사용(reveal에 username 포함) | false |
| --username | JWT 모드에서 사용할 사용자명 | - |
| --auth-bearer | Authorization: Bearer 토큰 값 | - |

## 출력 예시

요청/응답(단건 또는 배치 각 반복/배치마다) 예시:
```json
{
  "batch": 1,
  "protect": {
    "request": {
      "url": "http://<host>:<port>/v1/protect",
      "headers": { "Content-Type": "application/json" },
      "body": { "protection_policy_name": "P03", "data": "1234567890123" }
    },
    "response": { /* 서버가 준 JSON 원문 */ }
  },
  "reveal": {
    "request": {
      "url": "http://<host>:<port>/v1/reveal",
      "headers": { "Content-Type": "application/json" },
      "body": { "protection_policy_name": "P03", "protected_data": "..." }
    },
    "response": { /* 서버가 준 JSON 원문 */ }
  },
  "time_s": 0.1234
}
```

Summary 블록(두 모드 동일):
```
Summary:
Iterations attempted: <총 시도 개수>
Successful (both 2xx): <성공(둘 다 2xx) 개수>
Revealed matched original data: <원본과 일치 개수>
Total time: <총 소요 시간(s)>
Average per-iteration time: <반복당 평균 시간(s)>
```

## 보안 주의사항
- `--show-bodies` 출력에서 Authorization 헤더는 자동 마스킹됩니다.
- 토큰은 파일/환경변수로 전달을 권장합니다.
- 로그/공유 시 민감 정보가 포함되지 않도록 주의하세요.

## 프로젝트 구조
```
.
├── protect_reveal/             # 패키지 소스 코드
│   ├── cli.py                  # CLI 엔트리포인트
│   ├── client.py               # HTTP 클라이언트/응답 파서
│   ├── runner.py               # 단건/배치 실행 로직
│   └── utils.py                # 유틸 함수
├── protect_reveal.py           # 패키지 CLI 호출 래퍼
├── requirements.txt            # 런타임 의존성
├── requirements-dev.txt        # 개발/테스트 의존성
├── tests/                      # 단위 테스트
├── setup.sh                    # 환경 설정 스크립트
└── README.md                   # 이 문서
```

## 개발/테스트
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

테스트에는 배치 정상/부분 실패 케이스가 포함됩니다.

