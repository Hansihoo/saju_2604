# Request Logging Guide

## 기본 정책

사주 입력에는 생년월일·시간·성별이 포함되므로 요청 로그는 기본적으로 꺼져 있다.

```bash
SAJU_REQUEST_LOG_ENABLED=0
SAJU_REQUEST_LOG_INCLUDE_INPUT=0
```

`SAJU_REQUEST_LOG_ENABLED=1`을 켜더라도 기본 기록에는 아래처럼 운영에 필요한 비식별 메타데이터만 남긴다.

- trace ID, 경로, HTTP 상태, 파이프라인 상태
- locale, 달력 종류, 지역 ID, 입력 시간 추정 여부, 정확도 모드
- 오류 코드와 입력값이 제거된 오류 메타데이터

생년월일·시간·성별·사주 기둥·내부 점수·등급·LLM 출력문은 기록하지 않는다. 이 기본 로그는 재현용 입력을 보관하지 않으므로 `replay_command`도 비어 있다.

## 로컬 재현 전용 모드

특정 오류를 재현해야 할 때만 개발 PC의 짧은 시간 동안 아래 옵션을 명시적으로 켠다.

```bash
SAJU_REQUEST_LOG_ENABLED=1
SAJU_REQUEST_LOG_INCLUDE_INPUT=1
```

이 모드의 `/saju/preview` JSONL 레코드에는 재현에 필요한 원본 입력이 들어가며, 아래 명령으로 다시 실행할 수 있다.

```powershell
cd apps/api
python -m app.tools.replay_saju_request_log --trace-id <trace-id>
```

원본 입력 로그는 운영 환경에 설정하지 말고, 재현이 끝나면 즉시 삭제한다. 파일 권한도 해당 개발자만 읽을 수 있게 유지한다.

## 저장 위치와 회전

기본 경로는 `.dev-runtime/saju-request-events.jsonl`이며, 기본 크기는 파일당 10 MB·백업 3개다.

```bash
SAJU_REQUEST_LOG_PATH=/secure/path/saju-request-events.jsonl
SAJU_REQUEST_LOG_MAX_BYTES=10485760
SAJU_REQUEST_LOG_BACKUP_COUNT=3
```

파일 쓰기에 실패해도 API 응답은 실패하지 않으며 일반 런타임 로그에 `request_log` 경고만 남긴다. 여러 인스턴스 환경에서는 로컬 파일을 운영 관측 수단으로 삼지 말고 플랫폼 로그나 중앙 수집기로 확인한다.

## 런타임 로그

단계별 구조화 로그는 생년월일·시간·기둥·내부 점수·등급을 자동으로 `[redacted]` 처리한다. 로그에서 문제가 발생한 요청은 `X-Trace-Id`로만 추적한다.

공개 베타 환경 변수와 Vercel WAF 단계는 [PUBLIC_BETA_RUNBOOK.md](operations/PUBLIC_BETA_RUNBOOK.md)를 따른다.
