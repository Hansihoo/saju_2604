# DaYun Formula Validation Update

## Scope
- This note records the first explicit DaYun formula rollout after the project switched away from adapter-owned `Yun.getDaYun()` output.

## What Changed
- DaYun is now calculated in our codebase from:
  - corrected solar datetime
  - year pillar
  - month pillar
  - day pillar
- Month-boundary lookup still reuses `lunar-python` Jie helpers.
- External API compatibility is preserved.

## Active Validation Layers
1. Unit tests for direction, boundary, start-age, and sexagenary shift
2. Engine tests for end-to-end natal chart + DaYun output
3. Preview pipeline tests for API-level `luck_cycles`
4. Golden answer-sheet validation for Korean manse output

## Current Baseline
- `python -m unittest discover -s tests -p "test_*.py"`: passed
- `python -m app.tools.run_golden_validation`: passed
- `pnpm --dir "D:\\5_project\\SaJu(2)\\apps\\web" build`: passed

## Current Golden Summary
- total cases: `7`
- total mismatches: `50`
- mismatch fields:
  - `luck_cycles.branch`
  - `luck_cycles.gan_zhi`
  - `luck_cycles.start_age`
- case status counts:
  - `match`: `4`
  - `answer_sheet_review`: `3`

## Why Validation Needed to Expand
- The previous diagnostics were strong for gan-zhi progression anomalies.
- After the explicit formula rollout, `start_age` mismatches can now appear alongside branch progression mismatches.
- To make Codex troubleshooting easier, the comparison summary now needs to keep both:
  - progression mismatch signals
  - displayed start-age mismatch signals

## Current Diagnostic Reading
- `aru`
  - branch progression mismatch
  - start-age mismatch present
  - answer sheet also contains non-standard gan-zhi values
- `gomaebi`
  - branch progression mismatch
  - answer sheet looks non-standard
- `pororo`
  - only the tail row still breaks from the otherwise consecutive reverse flow

## Next Decision Points
1. Decide whether `aru` start ages should follow a separate displayed-age convention.
2. Gather a second trustworthy DaYun source before changing branch progression rules for `aru`, `gomaebi`, or `pororo`.
3. Once DaYun is stable enough, move on to user-facing manse table rendering.
