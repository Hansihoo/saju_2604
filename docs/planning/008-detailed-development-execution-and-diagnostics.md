# Detailed Development Execution And Diagnostics 008

## 목적
- 개발을 실제 실행 가능한 단계로 더 잘게 나눈다.
- 각 단계마다 무엇을 구현하고 무엇으로 검증할지 고정한다.
- 문제가 생겼을 때 AI와 사람이 같은 흐름으로 원인을 추적할 수 있게 진단 구조를 정의한다.

## 핵심 방향
- 개발 순서는 `계약 -> 입력 정규화 -> 시간 보정 -> 달력 정규화 -> 사주 계산 -> 분석 -> LLM 표현 -> 결과 UI -> 운영 자동화`로 간다.
- 각 단계는 독립적으로 검증 가능해야 한다.
- 각 요청은 `trace_id`를 가지며, 단계별 실행 상태와 핵심 메타데이터를 로그로 남긴다.
- 디버그 옵션을 켜면 "어디까지 성공했고 어디서 실패했는지"를 응답과 로그에서 동시에 볼 수 있어야 한다.
- AI가 문제를 해결할 수 있으려면 "재현 가능한 입력", "단계별 상태", "구조화 로그", "고정 비교 케이스"가 있어야 한다.

## 개발 원칙

### 원칙 1. 단계별 완료 기준이 있어야 한다
- 구현 완료는 "코드가 있음"이 아니라 "테스트와 수동 검증이 통과함"이다.
- 각 단계는 다음 단계로 넘기기 전에 명확한 acceptance criteria를 만족해야 한다.

### 원칙 2. 관측 가능성이 기능만큼 중요하다
- 시간 보정, 사주 계산, 분석 엔진은 잘못되더라도 UI만 보고는 원인을 알기 어렵다.
- 그래서 각 단계는 입력, 출력, 변환 규칙, 실패 이유를 구조화해 남겨야 한다.

### 원칙 3. debug 모드는 선택적으로 켠다
- 일반 사용자 응답은 간단해야 한다.
- 개발 및 검증 시에는 특정 옵션으로 상세 단계 로그와 디버그 정보를 확인할 수 있어야 한다.
- 운영 환경에서는 민감정보와 비용 문제 때문에 디버그 강도를 제한한다.

### 원칙 4. 재현 가능한 고정 케이스를 반드시 가진다
- 사주 계산은 "한 번 맞아 보였다"로 끝나면 안 된다.
- 절기 경계, 자시 경계, 음력/윤달, 한국 대표 케이스를 고정 입력으로 보유하고 회귀 검증해야 한다.

## 권장 개발 단계

## 0단계. 프로젝트 계약과 진단 골격

### 목표
- 이후 모든 단계가 기대는 공통 계약과 진단 필드를 먼저 만든다.

### 구현
- 입력 스키마
- 결과 응답 스키마
- 에러 응답 스키마
- `trace_id`
- `debug` 요청 옵션
- `pipeline_status` 공통 구조

### 완료 기준
- 프런트와 백엔드가 동일한 요청/응답 구조를 사용한다.
- 각 API 응답에 최소한 `trace_id`가 포함된다.
- 에러 응답에도 어느 단계에서 실패했는지 담긴다.

### 검증
- schema unit test
- mock API smoke test
- 프런트 입력/응답 contract test

## 1단계. 지역 검색과 입력 정규화

### 목표
- 사용자가 지역을 텍스트로 입력해도 계산에는 정규화된 `tzid`가 전달되게 만든다.

### 구현
- 한국 중심 지역 데이터셋
- 자동완성 API
- 선택된 지역의 `country`, `city`, `tzid`, `display_name`
- 프런트 자동완성 UI

### 완료 기준
- 자유 입력 문자열 자체로 제출되지 않는다.
- 반드시 후보 중 하나를 선택해야 제출 가능하다.
- 선택 결과에서 `tzid`가 확보된다.

### 검증
- 지역 검색 unit test
- 지역 선택 integration test
- E2E: 검색어 입력 -> 추천 노출 -> 선택 -> 제출

## 2단계. 시간 보정 모듈

### 목표
- `local datetime + tzid`를 계산 가능한 출생 현지 시각 정보로 정규화한다.

### 구현
- `zoneinfo` + `tzdata`
- DST 존재/중복 체크
- 역사적 UTC offset 반영
- `normalized_local_datetime`
- `normalized_utc_datetime`
- `time_correction_meta`

### 완료 기준
- 잘못된 tzid는 즉시 실패한다.
- 존재하지 않는 시각은 명확한 에러가 난다.
- 중복 시각은 fold 정책과 함께 기록된다.

### 검증
- unit: timezone lookup
- unit: nonexistent local time
- unit: ambiguous local time
- golden: 한국 표준 샘플
- integration: 지역 선택 -> 시간 보정

## 3단계. 양력/음력 정규화

### 목표
- 입력 달력 유형을 계산 엔진이 요구하는 표준 형태로 바꾼다.

### 구현
- `calendar_type`
- 음력 입력 시 윤달 여부 처리 규칙
- 양력 대응값 생성
- 정규화 결과 메타데이터

### 완료 기준
- 양력과 음력 입력이 같은 내부 구조로 정리된다.
- 윤달 여부가 사라지지 않는다.

### 검증
- unit: solar path
- unit: lunar path
- golden: 음력/윤달 샘플
- regression: 알려진 케이스 비교

## 4단계. 사주 계산 adapter

### 목표
- `lunar-python`을 우리 서비스 인터페이스 뒤에 붙인다.

### 구현
- `SajuEngine` 인터페이스
- `LunarPythonEngine`
- 표준 결과 구조:
  - `pillars`
  - `elements`
  - `ten_gods`
  - `luck_cycles`
  - `meta`

### 완료 기준
- 엔진 호출이 서비스 전역에 직접 퍼지지 않는다.
- 계산 결과가 표준 응답 형태로 변환된다.
- 엔진 실패 시 조용한 fallback 없이 실패가 명확히 드러난다.

### 검증
- adapter unit test
- integration: 정규화 입력 -> 계산 결과
- golden: 절기 경계, 자시 경계

## 5단계. 출생시간 미상 처리

### 목표
- `00:00` 기본값과 `is_birth_time_estimated` 정책을 계산과 결과에 일관되게 반영한다.

### 구현
- 입력 플래그
- 시주 기반 항목 제한 규칙
- UI 제한 안내 문구
- 응답 필드:
  - `is_birth_time_estimated`
  - `hour_pillar_enabled`
  - `disabled_sections`

### 완료 기준
- 출생시간 미상 케이스가 일반 결과처럼 과신되지 않는다.
- 제한 항목과 이유가 응답과 UI에 모두 반영된다.

### 검증
- unit: policy rule test
- integration: estimated-time response shape
- E2E: 시간 미상 흐름

## 6단계. 분석 엔진

### 목표
- 오행, 십성, 대운 기반의 점수/등급/근거를 코드로 만든다.

### 구현
- 오행 불균형 판단
- 희귀 조합 플래그
- 점수 계산
- 등급 계산
- 근거 요약

### 완료 기준
- 동일 입력에 대해 항상 동일한 점수와 등급이 나온다.
- 결과의 근거가 코드 레벨에서 설명 가능하다.

### 검증
- unit: score functions
- unit: grade boundaries
- snapshot: explanation payload
- property/regression test

## 7단계. LLM 표현 레이어

### 목표
- 분석 엔진 출력을 사용자 친화적인 문장으로 만든다.

### 구현
- prompt builder
- structured output schema
- fallback formatter
- 안전 규칙:
  - 과장 금지
  - 새로운 판단 생성 금지
  - 제한된 항목은 제한된 상태로 표현

### 완료 기준
- LLM 출력이 schema를 만족한다.
- LLM이 점수/등급을 새로 만들지 않는다.
- 실패 시 fallback 문장 생성기가 작동한다.

### 검증
- unit: prompt builder
- contract: output parsing
- integration: mock provider / real provider 분리 테스트

## 8단계. 결과 UI

### 목표
- 요약 우선, 근거는 접어서 보는 결과 경험을 완성한다.

### 구현
- 요약 카드
- 강점/약점/운세 섹션
- 오행/십성/대운 아코디언
- 제한 안내 UI
- trace/debug 전용 개발 패널

### 완료 기준
- 사용자는 요약만 보고도 결과를 이해할 수 있다.
- 필요 시 근거를 펼쳐볼 수 있다.
- 개발 환경에서는 요청 trace를 바로 볼 수 있다.

### 검증
- component test
- E2E: 정상/오류/제한 케이스
- manual: 문장 톤, 과장 여부

## 9단계. 운영 검증과 자동화

### 목표
- CI와 진단 수단을 붙여 회귀를 막는다.

### 구현
- lint / typecheck / unit / integration / golden / e2e 파이프라인
- healthcheck
- 배포 전 smoke test
- golden comparison job

### 완료 기준
- PR마다 핵심 검증이 자동 실행된다.
- 배포 전 사주 계산 핵심 샘플이 자동 비교된다.

### 검증
- CI dry run
- 수동 배포 체크리스트
- 장애 재현 템플릿 테스트

## 단계별 게이트

### Gate A
- 0~1단계 완료
- 아직 실제 사주 계산은 없지만 입력과 추적 구조는 완성

### Gate B
- 2~4단계 완료
- 시간 보정과 실제 사주 계산이 연결됨

### Gate C
- 5~7단계 완료
- 제한 정책, 분석 엔진, LLM 표현까지 연결됨

### Gate D
- 8~9단계 완료
- 사용자 경험과 운영 안정성까지 갖춤

## 진단 구조 설계

## 1. 공통 trace_id
- 모든 요청에 `trace_id`를 부여한다.
- 프런트 요청 시작 시 없으면 생성하고, 백엔드는 그대로 이어받거나 새로 만든다.
- 모든 로그, 에러 응답, debug 응답은 이 값을 포함한다.

예시:

```json
{
  "trace_id": "trc_20260405_abc123"
}
```

## 2. 단계별 pipeline_status
- 각 요청은 다음 단계의 상태를 기록한다.

예시:

```json
{
  "pipeline_status": {
    "input_validation": "passed",
    "region_resolution": "passed",
    "time_correction": "passed",
    "calendar_normalization": "passed",
    "saju_calculation": "failed",
    "analysis_engine": "skipped",
    "llm_formatting": "skipped"
  }
}
```

상태 값:
- `passed`
- `failed`
- `skipped`
- `disabled`

## 3. 구조화 로그
- 문자열 로그가 아니라 JSON 로그를 기본으로 한다.
- 최소 필드:
  - `timestamp`
  - `level`
  - `service`
  - `trace_id`
  - `stage`
  - `event`
  - `message`
  - `duration_ms`
  - `error_code`
  - `meta`

예시:

```json
{
  "level": "INFO",
  "service": "api",
  "trace_id": "trc_20260405_abc123",
  "stage": "time_correction",
  "event": "normalized",
  "duration_ms": 12,
  "meta": {
    "tzid": "Asia/Seoul",
    "source_local_datetime": "1990-01-01T10:30:00",
    "normalized_utc_datetime": "1990-01-01T01:30:00+00:00"
  }
}
```

## 4. debug 옵션

### 런타임 환경 변수
- `SAJU_DEBUG=1`
  - 전체 debug 기능 켜기
- `SAJU_TRACE_PAYLOADS=1`
  - 단계별 입력/출력 샘플 로깅
- `SAJU_TRACE_LLM=1`
  - LLM prompt/result 메타 로깅
- `SAJU_FAIL_FAST=1`
  - 첫 오류에서 즉시 중단
- `SAJU_LOG_LEVEL=DEBUG`
  - 로그 강도 조절

### 요청 단위 옵션
- 개발 환경에서만 허용
- 헤더 또는 body 플래그로 받는다.
  - `X-Saju-Debug: 1`
  - `debug: true`

### debug 응답 확장
- 일반 사용자 응답에는 숨긴다.
- debug 요청일 때만 `debug_trace`를 함께 반환한다.

예시:

```json
{
  "trace_id": "trc_20260405_abc123",
  "debug_trace": {
    "stage_order": [
      "input_validation",
      "region_resolution",
      "time_correction",
      "calendar_normalization",
      "saju_calculation",
      "analysis_engine",
      "llm_formatting"
    ],
    "failed_stage": "saju_calculation",
    "checkpoints": [
      {
        "stage": "time_correction",
        "status": "passed"
      },
      {
        "stage": "saju_calculation",
        "status": "failed",
        "error_code": "ENGINE_VALUE_ERROR"
      }
    ]
  }
}
```

## 5. 민감정보 보호
- debug 로그라도 원문 생년월일시와 전체 사용자 입력을 무조건 평문 저장하지 않는다.
- 운영 환경에서는 payload 전체 덤프를 막는다.
- 필요 시 마스킹 규칙을 적용한다.

## AI 자기 진단 흐름

## 목표
- AI가 장애를 만났을 때 "어디서 깨졌는지"를 자동으로 좁힐 수 있게 한다.

## 표준 분석 순서
1. `trace_id`를 확인한다.
2. `pipeline_status`에서 실패 단계와 마지막 성공 단계를 찾는다.
3. 해당 단계의 구조화 로그를 확인한다.
4. 입력과 직전 단계 출력을 비교한다.
5. 같은 유형의 golden test가 있는지 확인한다.
6. 문제를 코드/데이터/환경 중 어디로 분류할지 결정한다.
7. 가능한 경우 단일 단계만 다시 실행해 재현한다.

## 장애 분류 기준

### 입력 문제
- schema validation 실패
- 지역 선택 누락
- 존재하지 않는 시각

### 데이터 문제
- 지역 데이터셋에 없는 값
- 윤달 정보 누락
- 한국 표준 샘플과 불일치

### 엔진 문제
- adapter 변환 오류
- `lunar-python` 호출 오류
- 경계 시각 계산 결과 이상

### 분석 문제
- 점수 범위 이탈
- 등급 경계 오류
- 제한 정책 미반영

### LLM 문제
- schema 파싱 실패
- 과장된 표현
- 근거와 불일치

## AI가 쉽게 해결할 수 있게 만드는 장치
- 요청마다 `trace_id`
- 단계별 `pipeline_status`
- 구조화 로그
- golden test 케이스
- fallback 여부 명시
- 에러 코드 표준화

## 표준 에러 코드 예시
- `INPUT_SCHEMA_ERROR`
- `REGION_NOT_SELECTED`
- `INVALID_TIMEZONE`
- `NON_EXISTENT_LOCAL_TIME`
- `AMBIGUOUS_LOCAL_TIME`
- `CALENDAR_NORMALIZATION_ERROR`
- `ENGINE_VALUE_ERROR`
- `ENGINE_OUTPUT_SCHEMA_ERROR`
- `ANALYSIS_RULE_ERROR`
- `LLM_OUTPUT_PARSE_ERROR`

## 검증 전략

## 자동 검증
- unit
- integration
- golden
- e2e
- contract

## 수동 검증
- 대표 사용자 시나리오 5개
- 시간 미상 시나리오
- 절기 경계 시나리오
- 잘못된 tzid 시나리오
- debug 응답 확인 시나리오

## 관측 구조 자체 검증
- debug 옵션이 꺼져 있을 때 응답이 과도하게 무거워지지 않는지
- debug 옵션이 켜졌을 때 실패 단계가 명확히 표시되는지
- trace_id로 단일 요청을 로그에서 재구성할 수 있는지
- 에러 코드와 사용자 메시지가 분리되어 있는지

## 추천 구현 순서
1. `trace_id`, `pipeline_status`, 표준 에러 코드부터 만든다.
2. 지역 검색과 입력 검증을 붙인다.
3. 시간 보정과 golden test를 먼저 붙인다.
4. 달력 정규화와 `lunar-python` adapter를 붙인다.
5. 시주 제한 정책을 넣는다.
6. 분석 엔진을 넣는다.
7. LLM formatter를 붙인다.
8. 결과 UI와 debug 패널을 넣는다.
9. CI와 golden regression을 자동화한다.

## 이번 문서로 확정한 것
- 개발은 기능 순서가 아니라 "검증 가능한 순서"로 진행한다.
- 로그는 선택적이되, 켰을 때는 단계별 흐름이 완전히 보여야 한다.
- AI가 스스로 분석할 수 있도록 trace 중심 구조를 기본 설계에 포함한다.
- 계산 정확도 검증은 일반 단위 테스트보다 golden test와 cross-check가 더 중요하다.

## 다음 문서 후보
- `009-saju-engine-adapter-spec.md`
- `010-golden-test-cases-and-reference-samples.md`
- `011-debug-response-and-log-schema.md`
