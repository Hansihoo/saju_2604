# 현재 사주 계산 규칙

## 목적

- 현재 선택했거나 보호하고 있는 계산 규칙을 한곳에 기록한다.
- 이 문서는 방향 검토용이다.
- 이 문서만으로 새로운 primary 동작 전환을 승인하지 않는다.
- primary 동작을 바꾸려면 별도 검토, golden/reference 리포트, 테스트가 필요하다.

## 절대 보호 규칙

- `accuracy_mode` 기본값은 `legacy`로 유지한다.
- `corrected_solar_datetime`의 기존 의미를 바꾸지 않는다.
- 기존 public API 응답 필드는 삭제하거나 이름을 바꾸지 않는다.
- LLM은 년주, 월주, 일주, 시주, 대운, 불확실성을 계산하지 않는다.
- LLM은 도메인 엔진이 계산한 값을 문장화만 한다.
- 일반 사용자 화면에는 candidate chart, provider 내부 정보, debug 근거를 과도하게 노출하지 않는다.
- provider, candidate, evidence 정보는 `debug_trace` 또는 개발자 화면에 둔다.
- golden 테스트는 의도적으로 승인된 변경 전까지 primary 결과를 보호한다.

## 입력과 시간 보정 규칙

### 양력/음력 입력

- 양력 입력은 그대로 solar 기준 입력으로 처리한다.
- 음력 입력은 지원 범위 안에서 KASI 기반 checked-in 음양력 reference table로 양력 변환한다.
- 윤달 입력은 변환 과정에서 윤달 여부를 유지해야 한다.
- KASI table 범위 밖에서는 fallback이 가능하지만, fallback 사용 여부는 debug/provider metadata에 남겨야 한다.

### Timezone / DST

- 지역 시간 정규화는 Python `zoneinfo`와 IANA timezone ID를 사용한다.
- ambiguous local time은 `ambiguous`, `fold`를 기록한다.
- 한국 DST는 현재 timezone/DST 보정 흐름에 따라 반영한다.
- timezone/DST 보정 결과는 `time_correction`에 노출한다.

### 지역 경도 보정

- 현재 legacy 보정 시각 공식은 다음과 같다.

```text
corrected_solar_datetime
= calendar_normalization.normalized_solar_datetime
+ regional_solar_correction.regional_time_offset_minutes
+ regional_solar_correction.daylight_saving_offset_minutes
```

- 이 공식은 현재 유지 대상이다.
- `corrected_solar_datetime`은 기본 primary 엔진에 전달되는 시간 기준이다.
- `regional_solar_correction.corrected_solar_datetime`의 의미를 별도 승인 없이 바꾸지 않는다.

### BirthTimeContext

- `BirthTimeContext`는 여러 시간 기준을 관측/검증용으로 기록한다.
- 기록 대상:
  - 법정 local time
  - normalized local/UTC time
  - standard local time
  - mean solar time
  - legacy corrected time
- `standard_local_datetime`, `mean_solar_datetime`은 기본적으로 candidate/debug 기준이다.
- 명시적 `accuracy_mode` 또는 feature flag 없이 기본 primary 계산에 사용하지 않는다.

## 출생시간 미상 규칙

- 출생시간 미상일 때 내부적으로만 `00:00` placeholder를 사용한다.
- 이 placeholder를 확정 출생시각처럼 노출하지 않는다.
- placeholder metadata를 남긴다.
  - `is_placeholder_time=true`
  - `placeholder_reason=birth_time_unknown`
- 출생시간 미상일 때 시주는 비활성화한다.
- 출생시간 미상일 때 대운은 비활성화한다.
- 출생시간 미상일 때 시주 기반 해석은 비활성화한다.
- placeholder 때문에 생긴 candidate 차이로 시주/대운 warning을 만들지 않는다.
- 출생시간 미상에서 허용하는 주요 uncertainty flag는 다음 정도로 제한한다.
  - `birth_time_unknown`
  - `day_pillar_uncertain_due_to_unknown_time`
  - `day_interval_contains_solar_term`
  - `year_or_month_pillar_may_change`

## 사주팔자 source 규칙

### 년주

- 현재 기본 primary 년주는 `lunar_python` EightChar 결과를 사용한다.
- KASI/Skyfield 절입 기준 canonical 년주는 shadow 계산으로만 만든다.
- canonical 년주 규칙:
  - 입춘을 년주 경계로 사용한다.
  - 기준 시각이 입춘 전이면 이전 사주년을 사용한다.
  - 기준 시각이 입춘 정각 또는 이후면 새 사주년을 사용한다.
- canonical 년주를 primary로 쓰려면 `SAJU_USE_CANONICAL_YEAR_MONTH_PILLARS=1`이 필요하다.
- 이 feature flag 기본값은 꺼짐이다.

### 월주

- 현재 기본 primary 월주는 `lunar_python` EightChar 결과를 사용한다.
- KASI/Skyfield 절입 기준 canonical 월주는 shadow 계산으로만 만든다.
- canonical 월주는 기준 시각 이전 또는 같은 시각의 가장 최근 12절입을 기준으로 한다.
- 12절입 월지 매핑:
  - 입춘 -> 인
  - 경칩 -> 묘
  - 청명 -> 진
  - 입하 -> 사
  - 망종 -> 오
  - 소서 -> 미
  - 입추 -> 신
  - 백로 -> 유
  - 한로 -> 술
  - 입동 -> 해
  - 대설 -> 자
  - 소한 -> 축
- 월간은 년간 기준으로 계산한다.
- canonical 월주를 primary로 쓰려면 `SAJU_USE_CANONICAL_YEAR_MONTH_PILLARS=1`이 필요하다.
- 이 feature flag 기본값은 꺼짐이다.

### 일주

- primary 일진/일주 gan-zhi는 지원 범위 안에서 checked-in KASI 일진 table을 우선 사용한다.
- KASI table 범위 밖이면 `lunar_python`으로 fallback한다.
- 현재 선택한 일주 규칙은 `sect1_23_changes_day`이다.
- 일주 기준일은 timezone/calendar normalization 이후의 local civil datetime으로 판단한다.
  - `22:59` -> 당일 일진
  - `23:00` -> 다음 날 일진
  - `23:30` -> 다음 날 일진
  - `00:30` -> 해당 날짜 일진
  - 다음 날 `23:00` -> 그 다음 날 일진
- KASI 일진 조회는 원래 출생 달력 날짜가 아니라 `day_pillar_basis_date`를 사용한다.
- 23시 이후 일주 보정은 일주/시주 계산에만 적용한다.
- 이 보정은 년주/월주 기준을 바꾸지 않는다.
- 이 보정은 `corrected_solar_datetime`을 바꾸지 않는다.

### 시주

- 시지는 현재 primary mode가 사용하는 시간 기준에서 결정한다.
- 기본 `legacy` primary에서는 기존 corrected-time 기준을 유지한다.
- `sect1_23_changes_day`에서는 23:00 이후 보정된 다음 날 일간을 기준으로 시간 천간을 계산한다.
- 시주는 KASI 일진 조회일과 같은 일간 기준을 봐야 한다.
- alternate midnight rule은 candidate/compare에서만 비교한다.
- alternate midnight rule은 기본 primary를 바꾸지 않는다.

## 절입 provider 규칙

- 절입 경계 조회 순서:
  - 검증된 checked-in reference row
  - Skyfield ephemeris
  - `lunar_python` fallback
- runtime 요청 중에는 Skyfield ephemeris를 다운로드하지 않는다.
- `de440s.bsp`는 배포/실행 전에 준비하고 checksum 검증한다.
- 절입 provider를 사용하는 영역:
  - 절입 근처 uncertainty 탐지
  - 대운 adjacent Jie boundary 조회
  - canonical 년주/월주 shadow 계산
- 어떤 provider가 사용됐는지는 debug/report metadata에 남긴다.

## 대운 규칙

- 대운 방향, 순서, 시작 나이는 도메인 엔진에서 결정한다.
- adjacent Jie boundary 조회는 reference -> Skyfield -> fallback provider path를 우선 사용한다.
- 기존 `start_age` 동작은 보호 대상이다.
- 반올림만 의존하지 않도록 `years + months`, total months 같은 정밀 필드를 함께 노출할 수 있다.
- 출생시간 미상일 때 대운은 비활성화한다.
- 첫 번째 대운 결과 변경은 golden/reference 검증 후에만 허용한다.

## accuracy_mode 규칙

- 허용 mode:
  - `legacy`
  - `standard_time`
  - `mean_solar_time`
  - `compare`
- 기본 mode는 `legacy`이다.
- `accuracy_mode`가 생략되면 반드시 `legacy`와 동일해야 한다.
- `compare`는 primary를 legacy로 유지하고 비교 정보만 debug/developer 경로에 제공한다.
- 일반 사용자 화면에 전체 candidate chart를 강제 노출하지 않는다.
- 일반 사용자 화면에는 필요한 경우 간단한 uncertainty summary만 노출한다.

## candidate chart 규칙

- candidate chart는 기본적으로 진단용이다.
- candidate chart는 `debug_trace`에 둔다.
- 4주와 첫 대운 시작 정보가 같은 후보는 중복 제거한다.
- 같은 결과를 만든 기준들은 `aliases`에 남긴다.
- candidate chart는 명시적 mode/flag 없이는 primary 결과를 바꾸지 않는다.

## uncertainty 규칙

- uncertainty flag는 LLM이 판단하지 않고 도메인 코드가 만든다.
- candidate chart 차이와 `BirthTimeContext` evidence를 근거로 삼는다.
- 단순 조건만 있으면 보통 `info`이다.
- 시주만 달라질 가능성이 있으면 `warning` 이상이 될 수 있다.
- 일주/월주/년주가 달라질 가능성이 있으면 `critical`이 될 수 있다.
- `result.uncertainty_summary`는 warning 이상만 optional로 제공한다.
- 전체 근거는 `debug_trace.uncertainty_flags`에 둔다.

## 해석 생성 규칙

- interpretation payload는 계산된 사실만 담는다.
- LLM은 사주팔자, 점수, flags, summaries를 새로 계산하지 않는다.
- LLM은 누락된 시주를 추론하지 않는다.
- 시주가 비활성화된 경우 시주 근거를 언급하면 안 된다.
- uncertainty가 있으면 이미 계산된 summary를 문장화할 수 있다.

## reference data 규칙

### KASI 음양력/일진 table

- checked-in KASI 음양력/일진 table은 `1900~2050` 범위를 다룬다.
- repository에 저장 가능한 크기다.
- table integrity test와 full-range 일진 diff report를 유지한다.
- 지원 범위 안에서는 KASI 일진 table을 primary 일주 gan-zhi source로 사용한다.

### 절입 reference table

- 자주 쓰이는 최근 연도 절입 row가 checked-in 되어 있다.
- `1946~2027` 확장 절입 row는 80세 coverage 검토용으로 존재한다.
- 일부 확장 row는 secondary source 후보라 공식 KASI 이미지/PDF 대조가 필요하다.
- 검증되지 않은 row를 곧바로 primary source로 승인하지 않는다.
- 누락 또는 미검증 구간은 Skyfield를 독립 ephemeris fallback으로 사용한다.

## 검증 규칙

- 계산 source나 정책을 바꾼 뒤 API 테스트를 실행한다.

```powershell
pnpm test:api
```

- API contract 또는 frontend 표시를 바꾸면 web build를 실행한다.

```powershell
pnpm --filter web build
```

- 계산 데이터/provider를 건드렸으면 accuracy safety check를 실행한다.

```powershell
powershell -ExecutionPolicy Bypass -File ./scripts/accuracy-safety-check.ps1
```

- 검토할 주요 리포트:
  - `apps/api/tests/reports/iljin_reference_diff_report.md`
  - `apps/api/tests/reports/lunar_reference_diff_report.md`
  - `apps/api/tests/reports/solar_term_reference_diff_report.md`
  - `apps/api/tests/reports/accuracy_mode_diff_report.md`
  - `apps/api/tests/reports/canonical_year_month_diff_report.md`

## 현재 검토 질문

- supported range에서 canonical 년주/월주를 primary로 전환해도 되는가?
- `1946~2027` 확장 절입 row를 어느 수준까지 신뢰할 것인가?
- 공식 reference row가 없는 절입은 Skyfield를 primary fallback으로 인정할 것인가?
- `sect1_23_changes_day`를 이 서비스의 기본 자시/일주 규칙으로 확정해도 되는가?
- 일반 사용자에게 uncertainty를 어느 강도로 보여줄 것인가?
- 대운 시작 나이는 반올림 년수보다 년+월 또는 total months 중심으로 보여주는 것이 맞는가?

## 현재 방향 요약

- legacy primary를 계속 보호한다.
- 명확히 검증된 KASI 공식 table은 적극 사용한다.
- 절입은 reference row를 우선 사용하고, 없으면 Skyfield를 독립 fallback으로 사용한다.
- canonical 년주/월주는 검토 전까지 shadow mode로 둔다.
- 23:00 이후 다음 날 일주 적용 규칙을 현재 primary 관례로 둔다.
- uncertainty와 candidate detail은 debug/developer surface에 둔다.
- 계산 source 전환은 리포트 기반 검토 후에만 진행한다.
