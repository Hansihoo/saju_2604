# Explicit DaYun Formula Progress

## Date
- 2026-04-08

## Goal
- Replace the adapter-side `lunar-python` DaYun flow with an explicit in-repo calculation.
- Reuse the existing corrected birth datetime and already computed natal pillars.
- Keep the external preview/manse response shape stable.

## Implemented
- Added a dedicated DaYun calculator:
  - `apps/api/app/domain/saju/services/calculate_luck_cycles.py`
- Replaced `Yun.getDaYun()` usage inside:
  - `apps/api/app/domain/saju/adapters/lunar_python_engine.py`
- Kept natal chart calculation untouched and reused:
  - corrected solar datetime
  - year pillar
  - month pillar
  - day pillar
- Preserved internal debug values on each luck cycle:
  - `direction`
  - `exact_start_age_years`
  - `month_boundary_datetime`

## Rule Baseline
- Direction:
  - `male + yang stem` -> forward
  - `female + yin stem` -> forward
  - otherwise -> backward
- Boundary:
  - forward -> birth datetime to next Jie
  - backward -> previous Jie to birth datetime
- First DaYun:
  - start from the adjacent pillar to the month pillar
- Display age:
  - use the explicit day-count convention from the project brief
- 60-cycle shift:
  - use the full sexagenary cycle
  - do not shift stem/branch independently

## Verification
- `python -m compileall app`
- `python -m unittest discover -s tests -p "test_*.py"`
- `pnpm --dir "D:\\5_project\\SaJu(2)\\apps\\web" build`
- `python -m app.tools.run_golden_validation`

## Result
- Required reference case matches:
  - female / `1996-06-19 15:03` / Seoul
  - corrected solar datetime `1996-06-19 14:30:58`
  - DaYun flow:
    - `5 癸巳`
    - `15 壬辰`
    - `25 辛卯`
    - `35 庚寅`
    - `45 己丑`
    - `55 戊子`
    - `65 丁亥`
    - `75 丙戌`
    - `85 乙酉`
    - `95 甲申`

## Golden Validation Snapshot
- Total cases: `7`
- Total mismatches: `50`
- Match cases: `4`
- Answer-sheet-review cases: `3`

## Interpretation
- The explicit DaYun formula improved rule transparency and testability.
- The golden mismatch increase from `40` to `50` comes from `aru` start-age differences now being surfaced explicitly.
- The remaining non-match cases are still concentrated in answer sheets that already look suspicious on branch progression or tail rows.

## Next
1. Review whether `aru` uses a different displayed start-age convention.
2. Keep `aru`, `gomaebi`, `pororo` in answer-sheet-review status until a second trustworthy source confirms their DaYun branch flow.
3. After DaYun stabilization, move to user-facing manse rendering.

## 2026-04-08 Follow-up
- Expanded the golden comparison summary with start-age convention candidates:
  - `current_day_count_r2`
  - `exclude_both_day_count_r2`
  - `floor_exact`
  - `ceil_exact`
  - `round_exact`
- `aru` now logs that its expected first age `5` matches alternative conventions such as `floor_exact`, while the current engine rule still yields `6`.
- Remaining non-match cases continue to point at answer-sheet review, not a confirmed engine regression:
  - `aru`: alternative start-age convention + non-standard branch progression
  - `gomaebi`: non-standard branch progression
  - `pororo`: last DaYun row tail anomaly only
