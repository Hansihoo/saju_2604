# Golden Answer Validation System 016

## 목적
- 사용자가 제공한 만세력 정답지를 프로젝트 내부의 표준 스키마로 변환한다.
- 현재 사주 계산 결과도 같은 표준 스키마로 출력한다.
- 두 결과를 JSON 기준으로 비교해 어떤 필드가 틀렸는지 구조적으로 확인한다.
- 생성된 diff 로그를 Codex가 다시 읽고, 오류가 집중되는 단계나 필드를 추적할 수 있게 만든다.

## 핵심 개념
- 원본 정답지: 사람이 읽는 `.txt`
- 표준 정답지: 테스트용 canonical JSON
- 실제 출력: 현재 엔진이 만든 canonical JSON
- 비교 리포트: expected vs actual diff JSON

즉 비교 단위는 텍스트가 아니라 정규화된 JSON이다.

## 적용 파일
- 정답 비교 스키마: [golden.py](/D:/5_project/SaJu(2)/apps/api/app/domain/saju/golden.py)
- 정답지 파서: [parse_golden_answer_text.py](/D:/5_project/SaJu(2)/apps/api/app/domain/saju/services/parse_golden_answer_text.py)
- 실제 결과 exporter: [build_golden_snapshot.py](/D:/5_project/SaJu(2)/apps/api/app/domain/saju/services/build_golden_snapshot.py)
- 정답지 변환 도구: [import_golden_cases.py](/D:/5_project/SaJu(2)/apps/api/app/tools/import_golden_cases.py)
- 비교 도구: [compare_golden_cases.py](/D:/5_project/SaJu(2)/apps/api/app/tools/compare_golden_cases.py)
- 일괄 실행 도구: [run_golden_validation.py](/D:/5_project/SaJu(2)/apps/api/app/tools/run_golden_validation.py)
- 테스트: [test_golden_case_tools.py](/D:/5_project/SaJu(2)/apps/api/tests/test_golden_case_tools.py)
- 엄격 비교 테스트: [test_golden_known_answers.py](/D:/5_project/SaJu(2)/apps/api/tests/test_golden_known_answers.py)

## 디렉터리 구조
```text
apps/api/tests/golden_cases/
  source/
    pororo.txt
    aru.txt
    okji.txt
    lee-hyeonjin.txt
    gomaebi.txt
  expected/
    pororo.json
    aru.json
    okji.json
    lee-hyeonjin.json
    gomaebi.json

apps/api/tests/golden_reports/
  latest/
    actual/
    diff/
    summary.json
```

`golden_reports`는 생성 산출물이므로 Git에서 추적하지 않는다.

## 현재 canonical 비교 범위
1. `basic_info`
- 양력 생년월일시
- 음력 생년월일시
- 성별 표기
- 출생지
- 보정시간
- 지역시 보정 분
- 서머타임 보정 분

2. `pillar_table`
- 생년 / 생월 / 생일 / 생시
- 천간
- 천간 십성
- 지지
- 지지 십성
- 지장간
- 12운성
- 12신살

3. `luck_cycles`
- 시작 나이
- 간지
- 천간
- 지지

## 비교에서 제외하는 값
- `basic_info.name`

이 값은 계산 결과가 아니라 원본 정답지의 대상자 식별 정보라서, 엔진 정확도 비교 기준에서는 제외한다.

## 실행 명령
정답지 txt를 JSON fixture로 변환:
```powershell
cd D:\5_project\SaJu(2)\apps\api
python -m app.tools.import_golden_cases
```

현재 엔진 결과와 비교:
```powershell
cd D:\5_project\SaJu(2)\apps\api
python -m app.tools.compare_golden_cases
```

한 번에 fixture 갱신 + 비교:
```powershell
cd D:\5_project\SaJu(2)\apps\api
python -m app.tools.run_golden_validation
```

불일치가 있으면 종료 코드를 실패로 받고 싶을 때:
```powershell
python -m app.tools.run_golden_validation --fail-on-mismatch
```

## 생성 로그
비교 실행 후 아래가 생성된다.
- 실제 출력: `apps/api/tests/golden_reports/latest/actual/*.actual.json`
- diff 리포트: `apps/api/tests/golden_reports/latest/diff/*.report.json`
- 요약 파일: `apps/api/tests/golden_reports/latest/summary.json`

`summary.json`에는 케이스별 mismatch 수와 report 경로가 들어간다.
또한
- `mismatch_groups`: `basic_info`, `pillar_table`, `luck_cycles` 중 어디에 오차가 몰리는지
- `mismatch_fields`: `luck_cycles.gan_zhi`, `pillar_table.twelve_shinsal` 같은 세부 필드 단위로 어디가 반복적으로 틀리는지
- `diagnosis_counts`: 자동 진단 태그 기준으로 어떤 유형의 문제가 많은지
를 바로 볼 수 있다.

케이스별 `diagnostic_context`에는 아래도 포함된다.
- `expected_luck_cycles`
- `actual_luck_cycles`
- `invalid_expected_luck_cycles`
- `luck_cycle_stem_mismatch_count`
- `luck_cycle_branch_mismatch_count`
- `luck_cycle_gan_zhi_mismatch_count`

즉 Codex는 mismatch 수만 보는 것이 아니라, 정답지 대운표 자체가 표준 60갑자로 해석 가능한지까지 함께 판단할 수 있다.

## Codex가 이 로그를 어떻게 활용할지
1. `summary.json`에서 mismatch 수가 큰 케이스를 찾는다.
2. 해당 케이스의 `diff/*.report.json`을 연다.
3. `path` 기준으로 오류가 어느 계층에 몰리는지 본다.
- `basic_info.*`: 시간 보정 / 지역 보정 문제
- `pillar_table.*`: 사주 원국 계산 문제
- `luck_cycles.*`: 대운 계산 또는 정규화 문제
4. 실제 산출물 `actual/*.actual.json`과 `expected/*.json`을 함께 비교한다.
5. 수정 후 `run_golden_validation`을 다시 돌려 mismatch 감소 여부를 확인한다.

## 현재 상태 (2026-04-07)
- 사주 4주(`year/month/day/time` 간지)는 5개 정답 케이스에서 모두 일치한다.
- 12신살은 정답지와 동일한 기준으로 정리되었다.
- 최신 golden validation 기준 총 mismatch는 `42`개다.
- 현재 남은 주요 mismatch는 대부분 `luck_cycles`에 집중된다.
- 진행 기록은 [003-m1-manse-progress-log.md](/D:/5_project/SaJu(2)/docs/delivery/003-m1-manse-progress-log.md)에 누적한다.
- summary에는 자동 진단 태그와 추천 조치도 포함된다.

최신 집계 기준 핵심 오차 필드:
- `basic_info.corrected_datetime`
- `basic_info.regional_time_offset_minutes`
- `luck_cycles.gan_zhi`
- `luck_cycles.branch`
- `luck_cycles`

최신 진단 집계:
- `regional_display_rounding_mismatch`: `1`
- `luck_cycle_progression_rule_mismatch`: `3`
- `luck_cycle_branch_only_mismatch`: `3`
- `expected_luck_cycle_unparseable`: `2`
- `expected_luck_cycle_branch_nonstandard`: `2`
- `expected_luck_cycle_tail_anomaly`: `1`
- `expected_luck_cycle_branch_tail_anomaly`: `1`

즉, 다음 우선순위는 `대운 간지 흐름`과 `지역 보정 표시 규칙` 검토다.

현재까지의 진행:
- `n=11` 대운 비교와 빈 `index=0` 제외 처리로 `lee-hyeonjin`, `okji`는 golden과 일치하게 되었다.
- `pororo`는 마지막 대운 한 칸이 표준 역행 규칙상 `신묘`로 계산되지만, 정답지는 `신축`으로 적혀 있어 별도 확인이 필요하다.

추가 확인:
- `lunar-python`의 `Yun.getDaYun()` 기본값은 빈 `index=0`을 포함한 10개를 반환한다.
- 현재 프로젝트는 빈 간지를 필터링해 표시하므로 기본값만 사용하면 실제 대운 9칸이 남는다.
- 하지만 단순히 `n=11`로 늘리는 것만으로는 golden 정답의 마지막 대운과 일치하지 않았다.
- 추가로 현재 비교기는 정답지 대운표의 `gan_zhi`가 표준 60갑자에 없는 조합이면 `expected_luck_cycle_unparseable`로 바로 표시한다.
- 현재 기준으로:
  - `aru` 비표준 예상 대운: `갑사`, `을자`, `병묘`, `기진`
  - `gomaebi` 비표준 예상 대운: `병사`, `정인`, `무묘`, `기진`, `경사`, `신오`, `임미`, `계신`, `갑유`
  - `pororo`는 전 구간이 표준 60갑자로 해석되지만 마지막 행만 흐름이 끊겨 `expected_luck_cycle_tail_anomaly`로 분류된다.
- 원본 txt의 대운표는 `천간`, `지지`를 분리된 컬럼으로 제공하므로, 현재 비교기는 `luck_cycle_branch_only_mismatch`도 함께 기록한다.
- 현재 `aru`, `gomaebi`, `pororo`는 모두 천간 mismatch 없이 지지 mismatch만 남아 있다.
- 추가로 지지열 자체의 delta를 계산해 `branch_sequence_nonstandard`, `branch_sequence_tail_anomaly`를 진단하고, 이를 각각 `expected_luck_cycle_branch_nonstandard`, `expected_luck_cycle_branch_tail_anomaly` 태그로 요약한다.
- 현재 기준:
  - `aru`, `gomaebi`: 지지열 자체가 표준 순행/역행이 아니다.
  - `pororo`: 지지열은 역행을 유지하다가 마지막 칸에서만 꺾인다.

## 확인된 규칙 메모
- 12신살은 만세력마다 기준이 다를 수 있다.
- 현재 정답지는 `년의 신살은 일지 기준`, `월/일/시의 신살은 년지 기준` 규칙과 일치했다.
- 참고: [포스텔러만세력 12신살 적용기준](https://backgram.tistory.com/entry/%ED%8F%AC%EC%8A%A4%ED%85%94%EB%9F%AC%EB%A7%8C%EC%84%B8%EB%A0%A5-12%EC%8B%A0%EC%82%B4-%ED%99%95%EC%9D%B8%EB%B2%95)

- 대운 간지 흐름은 일반적으로 월주를 기준으로 순행이면 다음 간지, 역행이면 이전 간지부터 이어진다.
- 참고: [사주팔자(四柱八字) 구성](https://octofeet.tistory.com/entry/%EC%82%AC%EC%A3%BC%ED%8C%94%EC%9E%90%E5%9B%9B%E6%9F%B1%E5%85%AB%E5%AD%97-%EA%B5%AC%EC%84%B1)

- 대운수(시작 나이)는 만세력마다 반올림/절삭 차이가 존재한다.
- 참고: [사주의 구성](https://ahtohallan.tistory.com/entry/%EC%82%AC%EC%A3%BC%EC%9D%98-%EA%B5%AC%EC%84%B1)

## 현재 기대 효과
- 텍스트 정답지와 현재 결과를 수작업으로 비교하지 않아도 된다.
- 어디가 틀렸는지 `path` 단위로 바로 확인할 수 있다.
- Codex가 diff JSON만 읽어도 다음 수정 포인트를 좁힐 수 있다.

## 다음 확장 후보
- `용신 분석`, `신강/신약`, `오행/십성 분포`까지 canonical 비교 범위 확대
- KASI 기반 오라클 필드 추가
- `pillar_table`, `basic_info`에도 비표준 표기 탐지 추가
- mismatch 패턴 자동 분류 고도화
- 대운 지지 진행 규칙 후보별 시뮬레이션 비교
- CI에 `golden validation` 별도 작업 추가
## 2026-04-07 Golden Expansion Update

- Added `참치`, `호연` golden source files and canonical fixtures
- Latest validation baseline:
  - total cases: `7`
  - total mismatches: `42`
  - fully matching cases: `chamchi`, `hoyeon`, `lee-hyeonjin`, `okji`
- Added new diagnosis tag:
  - `luck_cycle_start_age_only_mismatch`
  - `expected_answer_sheet_suspect`
- Added new diagnostic context fields:
  - `expected_luck_cycle_start_ages`
  - `actual_luck_cycle_start_ages`
  - `luck_cycle_start_age_mismatch_count`
- Meaning of the new tag:
  - DaYun gan-zhi/stem/branch progression is correct
  - only displayed `start_age` values differ
  - likely cause is `대운수/시작 나이 반올림 또는 절삭 규칙`
- Current status:
  - `참치`는 해당 규칙 조정으로 해결됨
  - tag is kept for future regressions
  - `aru`, `gomaebi`, `pororo`처럼 표준 흐름과 정답지 흐름이 다를 때는 answer-sheet suspicion도 함께 기록한다

## 2026-04-08 Display Convention Update

### Resolved
- `aru` 케이스의 `basic_info.corrected_datetime`, `basic_info.regional_time_offset_minutes` mismatch를 해결했다.
- golden snapshot의 지역시차 표시 규칙은 이제 `경도 0.1도 정규화 -> 분 환산 -> 정수 분 표시`를 사용한다.

### Why this rule
- 현재 7개 정답지의 지역시차 표시값과 모두 일치한다.
- raw `regional_time_offset_minutes`의 소수점 반올림 규칙만으로는 `aru`를 설명할 수 없었다.
- 경도 기반 표시 규칙으로 바꾸면 `pororo`, `hoyeon`, `chamchi`, `aru`가 동시에 일관되게 맞는다.

### Latest validation baseline
- total cases: `7`
- total mismatches: `40`
- case status counts:
  - `match`: `4`
  - `answer_sheet_review`: `3`
- mismatch fields:
  - `luck_cycles.gan_zhi`
  - `luck_cycles.branch`
- diagnosis counts:
  - `luck_cycle_progression_rule_mismatch`: `3`
  - `luck_cycle_branch_only_mismatch`: `3`
  - `expected_luck_cycle_unparseable`: `2`
  - `expected_luck_cycle_branch_nonstandard`: `2`
  - `expected_answer_sheet_suspect`: `3`
  - `expected_luck_cycle_tail_anomaly`: `1`
  - `expected_luck_cycle_branch_tail_anomaly`: `1`

### Current interpretation
- 남은 mismatch는 모두 대운(`luck_cycles`)에 집중된다.
- `aru`, `gomaebi`는 정답지 대운표 자체가 표준 60갑자/연속 지지 규칙과 다를 가능성이 높다.
- `pororo`는 마지막 행 1칸만 어긋나는 tail anomaly 패턴이다.

## 2026-04-08 Explicit Formula and Candidate Rules

### Added diagnostics
- `expected_start_age_matches_alternative_rule`

### Candidate first-age rules now logged
- `current_day_count_r2`
- `exclude_both_day_count_r2`
- `floor_exact`
- `ceil_exact`
- `round_exact`

### Latest baseline
- total cases: `7`
- total mismatches: `50`
- mismatch fields:
  - `luck_cycles.branch`
  - `luck_cycles.gan_zhi`
  - `luck_cycles.start_age`
- case status counts:
  - `match`: `4`
  - `answer_sheet_review`: `3`

### Why this matters
- `aru` no longer looks like a simple engine bug.
- The summary now shows that its expected first age `5` matches alternative display conventions, while its branch flow is still non-standard.
- This gives Codex enough structure to separate:
  - start-age display convention review
  - branch progression review
  - answer-sheet anomaly review

## 2026-04-08 Header-aware answer-sheet validation

### Added validation scope
- Parse the raw header line `대운 분석 (대운수: n, 월주)` into `luck_cycle_header`.
- Compare that header against:
  - actual month pillar
  - actual DaYun sequence
  - expected answer-sheet DaYun sequence

### New interpretation rule
- If the header month pillar matches the actual month pillar,
- and the engine DaYun rows follow that header sequence,
- but the expected answer-sheet rows do not,
- classify the case as `answer_sheet_review`.

### Latest verified state
- test suite: `42 passed`, `1 skipped`
- golden cases: `7`
- case status counts:
  - `match`: `4`
  - `answer_sheet_review`: `3`
- current review-only cases:
  - `aru`
  - `gomaebi`
  - `pororo`

## 2026-04-09 Golden Baseline Reset

### Validation outcome
- The current golden baseline is now fully green.
- Registered golden cases: `7`
- Total mismatches: `0`
- Case status counts:
  - `match`: `7`

### Rule change that closed the last gap
- Displayed first DaYun age now uses a precise proportional conversion:
  - `precise_start_age_years = delta_days * 120 / 365.2422`
  - `display_start_age = floor(precise_start_age_years + 0.5)`
- The older `delta_days / 3.0` exact value remains in the report as a diagnostic field.

### Operational meaning
- The golden suite is no longer blocked by known DaYun mismatches.
- `summary.json` should now be interpreted as a regression alarm:
  - if `total_mismatches > 0`, something changed
  - if `case_status_counts` differs from `{"match": 7}`, the pipeline regressed

### Current source of truth
- Use `apps/api/tests/golden_reports/latest/summary.json` after each validation run.
- Use `diagnostic_context.actual_precise_start_age_years` to inspect the precise displayed-age basis.
