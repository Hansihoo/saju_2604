# M1 Manse Progress Log

## 목적
- `M1. 만세력 계산과 검증 완료` 마일스톤의 실제 진행 기록을 남긴다.
- 어떤 순서로 작업했고, 어디까지 맞췄고, 무엇이 남았는지 다음 작업에서 바로 이어갈 수 있게 한다.
- golden validation 결과와 수정 방향을 함께 적어 회귀 검증 기준으로 사용한다.

## 2026-04-07

### 이번에 확인한 상태
- 사주 4주(`year/month/day/time`)는 golden 정답 5케이스와 모두 일치한다.
- 12신살은 golden 정답 기준과 일치한다.
- 최신 golden validation 기준 총 mismatch는 `42`개다.
- 남은 mismatch는 거의 전부 `luck_cycles`에 집중되어 있다.
- 자동 진단 집계:
  - `regional_display_rounding_mismatch`: `1`
  - `luck_cycle_progression_rule_mismatch`: `3`
  - `luck_cycle_branch_only_mismatch`: `3`
  - `expected_luck_cycle_unparseable`: `2`
  - `expected_luck_cycle_branch_nonstandard`: `2`
  - `expected_luck_cycle_tail_anomaly`: `1`
  - `expected_luck_cycle_branch_tail_anomaly`: `1`

### 이번에 한 일
1. golden validation을 다시 실행해 현재 오차를 최신 기준으로 고정했다.
2. `aru`, `gomaebi`, `pororo`, `lee-hyeonjin`, `okji` 케이스의 대운 차이를 다시 비교했다.
3. `lunar-python` 내부 `Yun`, `DaYun` 소스를 직접 확인해 기본 대운 계산 규칙을 추적했다.
4. 정답지 원본 txt의 `대운 분석` 표를 다시 확인해 파서 오인식이 아니라 원문 자체가 현재 canonical JSON과 동일하게 들어가고 있음을 확인했다.
5. golden summary에 자동 진단 태그와 추천 조치를 추가해 다음 수정 포인트를 더 빨리 좁힐 수 있게 했다.
6. `lunar-python`에서 대운 1칸을 더 가져오고, API 만세력에는 빈 `index=0` 대운을 제외하도록 조정했다.
7. 그 결과 `lee-hyeonjin`, `okji`는 golden과 완전 일치하게 되었고, `pororo`는 “누락”이 아니라 실제 마지막 대운 규칙 차이로 드러났다.
8. golden 비교기에 `expected_luck_cycle` 자체를 검증하는 단계도 추가했다.
9. 그 결과 `aru`, `gomaebi`의 정답지 대운표에는 표준 60갑자로 해석되지 않는 간지가 포함된다는 점을 자동으로 식별할 수 있게 되었다.
10. 원본 txt를 다시 확인해 보니 `대운 분석`은 애초에 `천간`과 `지지`를 분리된 컬럼으로 제공하고 있다.
11. 실제 golden 비교 결과도 `aru`, `gomaebi`, `pororo`는 `luck_cycle_stem_mismatch_count = 0`이고, 대운 오차가 사실상 지지 쪽에만 몰려 있음을 보여준다.
12. 지지열만 따로 분석하는 진단도 추가했다.
13. 그 결과 `aru`, `gomaebi`는 `expected_luck_cycle_branch_nonstandard`, `pororo`는 `expected_luck_cycle_branch_tail_anomaly`로 분류된다.

### 핵심 관찰
- `lunar-python`의 `DaYun.getGanZhi()`는 `월주`를 기준으로 순행이면 `+index`, 역행이면 `-index`로 진행한다.
- `Yun.getDaYun()` 기본값은 `n=10`이고, 이 안에는 빈 `index=0`이 포함된다.
- 그래서 현재 엔진 기본값만 쓰면 실제 대운 행은 9칸만 남는다.
- `n=11`로 늘리면 `lee-hyeonjin`, `okji`는 정답과 맞는다.
- 하지만 `aru`, `gomaebi`, `pororo`는 마지막 칸까지 포함해도 golden 정답과 자동으로 맞지 않는다.
- 외부 규칙 출처를 다시 확인해도 대운은 기본적으로 `월주를 기준으로 순행/역행`하는 설명이 일관되게 나온다.
- 따라서 현재 `aru`, `gomaebi` 대운 표는 표준 `lunar-python` 규칙과도, 일반 설명 자료와도 다르게 보인다.

### 케이스별 현재 판단
- `lee-hyeonjin`, `okji`
  - 대운 10칸 출력 문제를 해결한 뒤 golden과 완전 일치했다.
- `pororo`
  - 기존에는 마지막 대운 1칸 누락처럼 보였지만, 실제로는 마지막 간지가 표준 규칙과 다르다.
  - 더 정확히는 천간은 일치하고 마지막 지지만 `축 -> 묘` 차이가 남는다.
  - 지지열은 역행 패턴을 유지하다가 마지막 칸에서만 꺾인다.
- `aru`, `gomaebi`
  - 시작 나이는 현재 꽤 맞춰졌지만, 대운 간지/지지 흐름 자체가 `lunar-python` 기본 규칙과 다르다.
  - 게다가 정답지 대운표 안에 표준 60갑자에 없는 간지 조합이 포함되어 있다.
  - 하지만 천간 흐름은 실제 엔진과 일치하고, 지지 흐름만 어긋난다.
  - 지지 delta도 표준 순행 `+1` / 역행 `-1` 패턴이 아니다.
  - `aru` 비표준 간지: `갑사`, `을자`, `병묘`, `기진`
  - `gomaebi` 비표준 간지: `병사`, `정인`, `무묘`, `기진`, `경사`, `신오`, `임미`, `계신`, `갑유`

### 현재 결론
- 지금 단계에서 대운 mismatch는 구현 실수와 규칙 차이가 섞여 있지 않고, 대부분 “규칙 차이”로 보인다.
- 다만 `aru`, `gomaebi`는 이제 “규칙 차이”보다 먼저 “정답지 표기 자체가 표준 60갑자로 해석 가능한지”를 확인해야 하는 상태다.
- 따라서 다음 작업은 대운 규칙 출처를 더 확보하고, 어떤 규칙을 프로젝트 기준으로 채택할지 문서화한 뒤 코드에 반영하는 순서가 맞다.
- 특히 `aru`, `gomaebi`는 정답지의 `지지` 진행 규칙과 표준 60갑자 결합 규칙을 따로 봐야 한다.
- `pororo`는 표준 역행 규칙상 마지막 대운이 `신묘`로 계산되는데 정답지는 `신축`으로 적혀 있어, 마지막 지지 한 칸의 출처를 다시 확인해야 한다.

### 다음 작업
1. `aru`, `gomaebi` 정답지의 대운 지지 진행 규칙이 무엇인지 추가 확인
2. `pororo` 마지막 대운 `신축`의 마지막 지지(`축`)가 어떤 규칙에서 나오는지 추가 확인
3. 지역 보정 표시 규칙(`corrected_datetime`, `regional_time_offset_minutes`)을 별도 정책으로 정리

### 참고 실행 명령
```powershell
cd D:\5_project\SaJu(2)\apps\api
python -m app.tools.run_golden_validation
```

### 참고 문서
- [012-development-backlog-through-manse.md](/D:/5_project/SaJu(2)/docs/planning/012-development-backlog-through-manse.md)
- [016-golden-answer-validation-system.md](/D:/5_project/SaJu(2)/docs/planning/016-golden-answer-validation-system.md)
- [명리심리상담사 강의교안 PDF](https://www.ili.or.kr/upfiledata/Board/%EB%AA%85%EB%A6%AC%EC%8B%AC%EB%A6%AC%EC%83%81%EB%8B%B4%EC%82%AC_%EC%A0%84%EC%A0%95%ED%9B%88_%EA%B5%90%EC%95%88%EB%AA%A8%EC%9D%8C%5B1%5D.pdf)
  - 대운은 월주를 기준으로 순행/역행한다고 설명
- [대운 해석법](https://sajulatte.app/blog/daeun-interpretation)
  - 월주에서 순행이면 다음 간지, 역행이면 이전 간지로 진행하는 예시 제공
## 2026-04-07 Golden Expansion Update

### Added cases
- Added `참치`, `호연` answer sheets into `apps/api/tests/golden_cases/source`
- Re-generated canonical fixtures in `apps/api/tests/golden_cases/expected`

### Validation result
- Total golden cases: `7`
- Total mismatches: `52`
- Newly confirmed full match: `hoyeon`
- New isolated mismatch type: `chamchi`

### New finding
- `참치` is not a gan-zhi progression mismatch.
- `luck_cycles.gan_zhi`, `stem`, `branch` all match.
- Only `luck_cycles.start_age` differs, and every row is offset by `+1`.
- This points to a separate `대운수/시작 나이 반올림 규칙` issue.

### Validation system update
- Added diagnostic tag: `luck_cycle_start_age_only_mismatch`
- Added diagnostic context fields:
  - `expected_luck_cycle_start_ages`
  - `actual_luck_cycle_start_ages`
  - `luck_cycle_start_age_mismatch_count`
## 2026-04-07 Start Age Rule Update

### Result
- `참치` 케이스의 `luck_cycles.start_age` mismatch를 해결했다.
- 현재 golden 기준 완전 일치 케이스:
  - `chamchi`
  - `hoyeon`
  - `lee-hyeonjin`
  - `okji`

### Rule update
- 첫 대운 시작 나이 표시 규칙을 현재 golden convention에 맞게 조정했다.
- 적용 규칙:
  - 순행: 내림
  - 역행: 반올림

### Remaining focus
1. `aru`, `gomaebi`, `pororo` 대운 지지/간지 진행 규칙
2. `aru` 지역 보정 표시 규칙

## 2026-04-08 Answer Sheet Suspicion Diagnostics

### Goal
- 남은 대운 mismatch 중 일부가 엔진 계산 문제가 아니라 정답지 표기 문제일 가능성을 자동으로 분리한다.

### Added diagnosis
- `expected_answer_sheet_suspect`

### Intended meaning
- 엔진 출력은 표준 연속 60갑자/지지 흐름을 유지함
- 반면 정답지 대운표는 비표준 조합, 비연속 지지, 마지막 행 이상치 등을 보임
- 이 경우 Codex가 먼저 정답지 검토를 우선하도록 유도한다

## 2026-04-08 Regional Display Convention Match

### What changed
- `aru`에 남아 있던 지역시차 표시 mismatch를 해결했다.
- golden 표시 전용 규칙을 `raw 분 반올림` 대신 `경도 0.1도 정규화 -> 분 환산 -> 정수 분 표시`로 바꿨다.
- 이 규칙으로 현재 7개 정답지의 `regional_time_offset_minutes`와 `corrected_datetime` 표기가 모두 맞는다.

### Validation result
- `python -m unittest discover -s tests -p "test_*.py"` 통과
- `pnpm --dir "D:\\5_project\\SaJu(2)\\apps\\web" build` 통과
- `python -m app.tools.run_golden_validation` 통과

### Current status
- 전체 golden 케이스: `7`
- 전체 mismatch: `40`
- 더 이상 `basic_info` mismatch는 남아 있지 않다.
- 남은 mismatch는 전부 `luck_cycles`에만 있다.
- case status:
  - `match`: `4`
  - `answer_sheet_review`: `3`

### Remaining focus
1. `aru`, `gomaebi`의 비표준 대운 지지열/간지 표기 검증
2. `pororo` 마지막 대운 `신축` tail anomaly 출처 확인
3. answer-sheet suspicion 케이스를 리포트 상에서 더 분리할지 검토

## 2026-04-08 Explicit DaYun Formula Follow-up

### What changed
- adapter 내부 `Yun.getDaYun()` 의존을 걷어내고, 프로젝트 내부 계산식으로 대운을 명시적으로 계산하도록 전환했다.
- 이후 golden 비교기는 시작 나이 관례 후보까지 함께 기록하도록 확장했다.

### Latest baseline
- total cases: `7`
- total mismatches: `50`
- case status counts:
  - `match`: `4`
  - `answer_sheet_review`: `3`

### Current interpretation
- 사주 4주는 전체 케이스에서 모두 일치한다.
- 남은 mismatch는 전부 `luck_cycles`에만 있다.
- `aru`
  - 시작 나이 `5`가 `floor_exact`, `exclude_both_day_count_r2`, `round_exact`와는 맞는다.
  - 하지만 대운 branch 흐름 자체는 여전히 비표준이다.
- `gomaebi`
  - 시작 나이는 현재 규칙과도 맞지만, branch 흐름은 비표준이다.
- `pororo`
  - 전체 흐름은 표준 역행과 맞고 마지막 행만 tail anomaly 형태로 어긋난다.

### Next
1. `aru`, `gomaebi`, `pororo`를 정답지 재검토 대상으로 유지
2. 사용자 결과 화면에 만세력 표 반영 전, 대운 unresolved 규칙을 note로 남길지 결정

## 2026-04-08 Header Consistency Validation

### What was validated
- Re-ran the loop `validate -> inspect raw source txt -> adjust diagnostics`.
- Added `luck_cycle_header` parsing from the raw answer sheet line `대운 분석 (대운수: n, 월주)`.
- Added validator checks for whether expected DaYun rows follow the sequence implied by that header.

### Latest result
- Test suite: `42 passed`, `1 skipped`
- Golden cases: `7`
- Status counts:
  - `match`: `4`
  - `answer_sheet_review`: `3`

### Blocker after repeated attempts
- After more than two validate/research/fix cycles, the remaining failures do not look like engine bugs.
- For `aru`, `gomaebi`, and `pororo`:
  - actual month pillar matches the answer-sheet header reference pillar
  - actual engine DaYun rows follow the header-implied sequence
  - expected answer-sheet rows do not follow the header-implied sequence
- Current conclusion: keep these as `answer_sheet_review` unless corrected source answers are provided.

## 2026-04-08 Corrected Source TXT Re-import

### What was done
- Re-copied the updated external source files for `aru`, `gomaebi`, and `pororo` into the project golden source directory.
- Re-generated canonical JSON fixtures with `python -m app.tools.import_golden_cases`.
- Re-ran both the unit test suite and the full golden validation flow.

### Validation result
- `python -m unittest discover -s tests -p "test_*.py"`: `42 passed`, `1 skipped`
- `python -m app.tools.run_golden_validation`: completed

### Outcome
- The corrected TXT re-import did not change the remaining mismatch set.
- Current unresolved cases are still:
  - `aru`
  - `gomaebi`
  - `pororo`
- Remaining mismatch shape:
  - `aru`: DaYun `start_age` plus full `gan_zhi/branch` divergence
  - `gomaebi`: DaYun `gan_zhi/branch` divergence from row 2 onward
  - `pororo`: only the last DaYun row differs

### Interpretation
- The updated source TXT files were successfully imported, but the remaining DaYun mismatches persist.
- Next step should focus on either:
  1. another targeted source-answer review for those three cases, or
  2. a deliberate decision on whether `aru` should use an alternative displayed start-age convention.

## 2026-04-08 Aru Regional-Time Verification And Start-Age Rule Update

### What was verified
- `aru` answer sheet and current engine agree on the regional solar correction itself.
- Verified values:
  - corrected datetime: `1988-11-20 23:02`
  - regional time offset: `-28`
- This confirms the `5 vs 6` mismatch was not caused by longitude/regional-time correction.

### Rule decision
- Switched displayed DaYun start age from the day-count convention to `exact_start_age_years` half-up rounding.
- Applied rule:
  - `display_start_age = floor(exact_start_age_years + 0.5)`

### Why this rule was chosen
- Candidate rule coverage across the current 7 answer sheets:
  - `current_day_count_r2`: `5`
  - `exclude_both_day_count_r2`: `3`
  - `floor_exact`: `2`
  - `ceil_exact`: `4`
  - `round_exact`: `6`
- `round_exact` is the best fit for the current answer-sheet set and fixes `aru` without regressing the already matching cases.

### Result
- `aru` DaYun `start_age` now matches the answer sheet: `5, 15, 25, ...`
- Remaining `aru` mismatches are now only DaYun progression rows.
- `gomaebi` still remains an engine-review case because both the header/reference pillar and the start ages diverge from the current engine output.

## 2026-04-09 Exact Jie Boundary Investigation For Korea

### What was verified
- Re-checked the Korean answer-sheet mismatch against minute-level solar-term boundaries instead of day-only conventions.
- Confirmed that `lunar-python` jie timestamps align with a GMT+8/Beijing-style baseline, while KASI publishes solar-term times in Korean Standard Time.
- Applied a Korea-specific standard-offset adjustment when the region `tzid` is `Asia/Seoul`, so DaYun boundary diagnostics now use the same KST-style convention as the answer sheets.

### Result after applying exact boundary conversion
- `aru` boundary moved from `1988-12-07 05:34:28` to `1988-12-07 06:34:28`, matching the expected Korean-minute-level reference.
- Golden status improved to:
  - `match`: `6`
  - `engine_review`: `1`
- The only remaining mismatch is `gomaebi`, and it is now isolated to displayed `start_age` only:
  - expected `9, 19, ... 99`
  - actual `10, 20, ... 100`

### Interpretation
- The remaining `gomaebi` gap is no longer a regional-time or exact-jie-boundary problem.
- It is now purely a displayed DaYun start-age convention problem:
  - answer sheet aligns with `current_day_count_r2`, `exclude_both_day_count_r2`, or `floor_exact`
  - project currently uses `round_exact`

## 2026-04-09 Gomaebi Start-Age Factor Audit

### Scope
- Reviewed every value that can affect DaYun start order or displayed first age for `gomaebi`.
- Re-checked the current project output against the source answer sheet and web references.

### Factor-by-factor result
- Birth input
  - source answer sheet and current golden input both use `1988-12-08 03:00`, solar
  - no mismatch
- Time zone / DST
  - `Asia/Seoul` historical offset check shows UTC+9 with no DST on `1988-12-08`
  - this does not explain the remaining mismatch
- Regional solar correction
  - Seoul longitude dataset value `126.991824`, derived regional offset `-32.033`
  - displayed answer-sheet value `-32` matches current output
- Corrected birth time
  - answer sheet `1988-12-08 02:28`
  - current output `1988-12-08 02:28`
  - no mismatch
- Month pillar / direction / first DaYun pillar
  - current output: month pillar `갑자`, direction `forward`, first DaYun pillar `을축`
  - answer sheet matches all three
- Exact Jie boundary
  - current output: `1989-01-05 17:45:55`
  - corroborated by external references showing `1989-01-05 17:45` / `17:45:56`
  - boundary time no longer looks suspicious

### Remaining mismatch
- Only displayed DaYun `start_age` remains different:
  - expected `9, 19, ... 99`
  - current `10, 20, ... 100`
- Candidate-rule audit:
  - `current_day_count_r2 = 9`
  - `exclude_both_day_count_r2 = 9`
  - `floor_exact = 9`
  - `ceil_exact = 10`
  - `round_exact = 10`

### Conclusion
- `gomaebi` is not blocked by timezone, DST, regional correction, month pillar, direction, or DaYun progression.
- The only unresolved point is the displayed first-age convention.

## 2026-04-09 Precise Start-Age Ratio Adoption

### What changed
- Replaced the displayed DaYun first-age rule with a more precise proportional conversion:
  - `precise_start_age_years = delta_days * 120 / 365.2422`
  - displayed first age uses half-up rounding on that precise value
- Kept the older `delta_days / 3.0` value as `exact_start_age_years` for diagnostics and comparison.

### Why this rule was adopted
- It matches all current golden cases with one consistent rule.
- It preserves the already-correct minute-level Jie boundary handling and avoids per-case branching.
- It explains the `gomaebi` answer sheet without regressing `aru`.

### Result
- Golden status is now:
  - `match`: `7`
  - `engine_review`: `0`
- `gomaebi` now matches with first age `9`.
- Current project no longer has a known DaYun mismatch in the registered golden set.

## 2026-04-09 User Screen Scope Update

### Decision
- User-facing 화면에는 raw 만세력 표를 직접 붙이지 않기로 했다.
- 만세력은 내부 검증, golden 비교, 후속 분석 입력용 구조로 유지한다.

### Next focus
- 엔진/검증 단계가 안정화되었으므로 다음 작업은 지역 데이터 구조 정리와 사용자 결과 경험 설계다.
## 2026-04-09 Region Structure And User Result Contract

### Completed
- Region access now goes through a typed repository layer instead of raw dict access.
- The current seed dataset remains in place, but the code boundary is ready for an official dataset swap later.
- The preview API now exposes structured result signals for the frontend.
- The user-facing result screen now derives readable summaries from structured signals instead of developer-oriented API copy.

### Validation
- Backend unit tests passed
- Golden validation stayed fully matched
- Frontend build passed

### Next
1. Finish the region-data normalization step in planning docs
2. Stabilize the user-facing result contract as the M1 exit shape
3. Prepare the M2 LLM payload on top of the new result signals

## 2026-04-09 M2 Interpretation Payload Prep

### Completed
- Added an internal M2 interpretation payload model.
- Added a builder that converts preview facts into an LLM-ready facts-only payload.
- Added a developer CLI to dump the payload for a specific input.
- Added unit tests for normal and estimated-time cases.

### Why this matters
- The future LLM layer can now depend on a stable internal contract.
- The interpretation layer will not need to read developer-style response prose.

## 2026-04-09 M2 Fallback Formatter

### Completed
- Added a provider-agnostic fallback formatter on top of the M2 payload.
- Added a narrative schema separate from the preview response contract.
- Added a developer CLI that renders both payload and fallback interpretation for a single input.
- Added tests for Korean fallback output and estimated-time limitation propagation.

### Validation
- Backend unit tests passed
- Golden validation remained fully matched
- Frontend build remained healthy

### Next
1. Freeze the fallback formatter as the regression-safe baseline
2. Add the future provider interface above the payload and formatter boundary

## 2026-04-09 Manse Analysis Snapshot Completion

### Completed
- Added a deterministic `manse.analysis` block inside the backend manse payload.
- The analysis block now carries:
  - visible element total
  - element percentages
  - imbalance gap
  - visible ten-god distribution
  - score summary and first luck-cycle diagnostics
- Added a developer CLI to dump the full canonical manse snapshot without going through the browser UI.

### Validation
- Backend tests pass
- Golden validation remains `7/7`
- Frontend build remains healthy

## 2026-04-09 Service Result Review For Test Output

### Completed
- Reviewed the service UI before moving further into the LLM phase.
- Kept the input form narrow and familiar.
- Widened the result-state layout only after submission.
- Added a temporary testing block in the service result screen so Manse data can be inspected without opening debug-only tools.

### Included in the testing block
- corrected solar datetime
- day master and internal grade
- manse table rows
- five-element counts and percentages
- luck cycles
- supplementary positions
