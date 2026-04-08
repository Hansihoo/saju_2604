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
