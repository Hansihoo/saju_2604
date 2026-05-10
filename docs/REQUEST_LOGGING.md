# Request Logging Guide

## 목적
`/saju/preview` 요청에서 오류가 발생했을 때 같은 입력값으로 다시 테스트할 수 있도록 서버에 요청 로그를 남긴다.

로그는 사용자 브라우저나 사용자 PC가 아니라 **FastAPI 백엔드가 실행되는 서버**에 저장된다.

```text
사용자 브라우저
  -> 서버 FastAPI /saju/preview
  -> 서버 프로세스가 로그 작성
  -> 서버의 SAJU_REQUEST_LOG_PATH 위치에 JSONL 저장
```

## 저장 위치
기본 저장 위치:

```powershell
D:\5_project\SaJu(2)\.dev-runtime\saju-request-events.jsonl
```

서버 배포 환경에서는 실행 서버 기준 경로에 저장된다. 예를 들어 Linux 서버라면 아래처럼 영구 볼륨 경로를 지정한다.

```bash
export SAJU_REQUEST_LOG_PATH=/var/log/saju/saju-request-events.jsonl
```

파일 로그를 끄려면:

```bash
export SAJU_REQUEST_LOG_ENABLED=0
```

## 로그 파일 크기와 회전
기본값은 로그 파일 1개당 최대 `10MB`, 백업 파일 `3개` 보관입니다.

```bash
export SAJU_REQUEST_LOG_MAX_BYTES=10485760
export SAJU_REQUEST_LOG_BACKUP_COUNT=3
```

현재 로그가 최대 크기를 넘으면 기존 파일은 아래처럼 밀려납니다.

```text
saju-request-events.jsonl
saju-request-events.jsonl.1
saju-request-events.jsonl.2
saju-request-events.jsonl.3
```

`SAJU_REQUEST_LOG_MAX_BYTES=0`으로 설정하면 앱 내부 회전을 끄고, 운영체제의 `logrotate`나 로그 수집 서비스에 맡길 수 있습니다.

로그 파일 경로 권한, 디스크 용량, 파일 잠금 문제로 쓰기에 실패해도 `/saju/preview` API 응답은 실패시키지 않습니다. 이 경우 서버 일반 로그에 `request_log` 단계의 `write_failed` 경고만 남깁니다.

## 배포 환경 주의
현재 파일 로그 방식은 베타 운영이나 단일 서버 환경에서 바로 재현 테스트를 하기 위한 기본 구현입니다.

서버 인스턴스가 여러 대이면 각 서버의 로컬 파일에 로그가 나뉘어 남을 수 있습니다. 이 경우 `SAJU_REQUEST_LOG_PATH`를 공유 영구 볼륨으로 지정하거나, 운영 로그 수집 서비스/객체 스토리지/DB 중 하나로 모으는 구성이 필요합니다.

## 로그 형식
한 요청이 JSON 한 줄로 기록된다. 주요 필드는 다음과 같다.

```json
{
  "logged_at": "2026-05-10T13:29:18.123456+00:00",
  "trace_id": "trc_selected_params_001",
  "method": "POST",
  "path": "/saju/preview",
  "status_code": 400,
  "stage": "time_correction",
  "error_code": "INVALID_BIRTH_TIME",
  "message": "Birth time must stay within 00:00 to 23:59.",
  "selected_parameters": {
    "locale": "ko",
    "calendar_type": "solar",
    "birth_date": "2024-02-10",
    "birth_time": "99:99",
    "is_birth_time_estimated": false,
    "is_lunar_leap_month": false,
    "gender": "male",
    "region_id": "kr-seoul",
    "debug": true
  },
  "meta": {
    "birth_time": "99:99"
  },
  "replay_command": "python -m app.tools.replay_saju_request_log --trace-id trc_selected_params_001"
}
```

`selected_parameters`가 사용자가 선택한 재현용 입력값이다.

## 로컬에서 보기
최근 로그 확인:

```powershell
Get-Content .dev-runtime\saju-request-events.jsonl -Tail 20
```

특정 trace id 검색:

```powershell
Select-String -Path .dev-runtime\saju-request-events.jsonl -Pattern "trc_selected_params_001"
```

보기 좋게 JSON으로 확인:

```powershell
$line = Select-String -Path .dev-runtime\saju-request-events.jsonl -Pattern "trc_selected_params_001" | Select-Object -Last 1
$line.Line | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

## 서버에서 보기
SSH로 서버에 들어간 뒤 로그 경로를 확인한다.

```bash
tail -n 20 /var/log/saju/saju-request-events.jsonl
```

특정 trace id 검색:

```bash
grep "trc_selected_params_001" /var/log/saju/saju-request-events.jsonl
```

`jq`가 있으면 보기 좋게 확인할 수 있다.

```bash
grep "trc_selected_params_001" /var/log/saju/saju-request-events.jsonl | tail -n 1 | jq .
```

## 요청 재현
로그에 기록된 `trace_id`로 같은 입력을 다시 실행한다.

```powershell
cd D:\5_project\SaJu(2)\apps\api
python -m app.tools.replay_saju_request_log --trace-id trc_selected_params_001
```

서버에서 실행할 때:

```bash
cd /path/to/app/apps/api
python -m app.tools.replay_saju_request_log --trace-id trc_selected_params_001
```

기본 재현은 LLM 호출을 fallback으로 막아서 비용 없이 실행한다. 실제 LLM 호출까지 포함하려면:

```bash
python -m app.tools.replay_saju_request_log --trace-id trc_selected_params_001 --use-llm
```

가장 최근 실패 요청을 재현:

```bash
python -m app.tools.replay_saju_request_log
```

가장 최근 `/saju/preview` 요청을 재현:

```bash
python -m app.tools.replay_saju_request_log --last
```

## 개인정보와 보관 주의
현재 로그에는 이름, 연락처, IP 주소는 저장하지 않는다. 다만 생년월일, 생시, 성별, 지역 조합은 개인 관련 정보로 볼 수 있으므로 서버 접근 권한을 제한해야 한다.

베타 운영에서는 다음 기준을 권장한다.

- 로그 파일은 서버 관리자만 볼 수 있는 경로에 둔다.
- 배포 서버가 임시 파일시스템이면 `SAJU_REQUEST_LOG_PATH`를 영구 볼륨으로 지정한다.
- 오래된 로그는 주기적으로 삭제한다.
- 운영 전환 시에는 DB, 객체 스토리지, 로그 수집 서비스 중 하나로 이관한다.
