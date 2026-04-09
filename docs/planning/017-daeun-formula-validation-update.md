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
- total mismatches: `11`
- mismatch fields:
  - `luck_cycle_header.start_age`
  - `luck_cycles.start_age`
- case status counts:
  - `match`: `6`
  - `engine_review`: `1`

## Why Validation Needed to Expand
- The previous diagnostics were strong for gan-zhi progression anomalies.
- After the explicit formula rollout, `start_age` mismatches can now appear alongside branch progression mismatches.
- To make Codex troubleshooting easier, the comparison summary now needs to keep both:
  - progression mismatch signals
  - displayed start-age mismatch signals

## Current Diagnostic Reading
- `aru`
  - regional-time correction matches the answer sheet (`23:02`, `-28`)
  - exact Jie boundary now also matches the KST-style answer-sheet convention (`1988-12-07 06:34:28`)
  - case is now fully matched
- `gomaebi`
  - month pillar and DaYun progression now match
  - the only remaining mismatch is displayed `start_age`
  - remains the sole `engine_review` case
- `pororo`
  - fully matched

## Research Notes
- A Korean DaYun reference reviewed on 2026-04-08 describes the standard progression as:
  - build DaYun from the month pillar
  - move forward/backward by sex + year-stem yin/yang
  - progress consecutively through the sexagenary cycle
- KASI publishes solar-term times in Korean Standard Time, while `lunar-python` appears to expose jie times on a GMT+8 / Beijing-style baseline. This introduces an exact `+1 hour` gap for Korean cases if left unadjusted.
- After applying a Korea standard-offset conversion on the boundary timestamp, `aru` moved from `05:34:28` to `06:34:28` and matched the answer sheet.
- Sources checked:
  - https://60saju.tistory.com/40
  - https://contents.premium.naver.com/eyesaju/damlon/contents/250714105124199vg
  - https://brunch.co.kr/%40saju6969/14
  - https://astro.kasi.re.kr/almanac/pageView/1
  - https://6tail.cn/calendar/faq.html

## Diagnostic Expansion
- The golden comparison summary now stores candidate first-age conventions for each case:
  - `current_day_count_r2`
  - `exclude_both_day_count_r2`
  - `floor_exact`
  - `ceil_exact`
  - `round_exact`
- This makes it easier to see whether a mismatch is caused by:
  - engine progression
  - answer-sheet branch flow
  - displayed start-age convention
- `aru` currently matches alternative first-age conventions such as `floor_exact`, while its branch flow still remains non-standard.

## Displayed Start-Age Rule Decision
- The project now uses `round_exact` for displayed first DaYun age:
  - `display_start_age = floor(exact_start_age_years + 0.5)`
- Reason:
  - among the current 7 answer sheets, candidate-rule coverage is:
    - `current_day_count_r2`: `6`
    - `exclude_both_day_count_r2`: `3`
    - `floor_exact`: `3`
    - `ceil_exact`: `4`
    - `round_exact`: `6`
- This rule fixes `aru` start age without regressing the already matching cases.

## Next Decision Points
1. Decide whether `gomaebi` should remain an exception handled by answer-sheet convention review, or whether the project should move from `round_exact` to a day-count / `floor_exact` style rule globally.
2. If no stronger primary source is adopted, keep the current exact-boundary correction and document `gomaebi` as the single remaining display-policy mismatch.
3. Once the `gomaebi` start-age convention is resolved or deferred, move on to user-facing manse table rendering.

## Gomaebi Revalidation Checklist
- Verified inputs match the source answer sheet:
  - solar birth `1988-12-08 03:00`
  - corrected birth `1988-12-08 02:28`
  - region offset `-32`
- Verified structural DaYun values now match:
  - month pillar `갑자`
  - direction `forward`
  - first DaYun pillar `을축`
  - full DaYun sequence `을축 -> 병인 -> 정묘 -> 무진 -> 기사 -> 경오 -> 신미 -> 임신 -> 계유 -> 갑술`
- Verified exact boundary timestamp now aligns with external minute-level references:
  - current project `1989-01-05 17:45:55`
  - corroborating references report `1989-01-05 17:45` / `17:45:56`
- Therefore the only unresolved mismatch is the displayed first age:
  - answer sheet favors `9`
  - current project returns `10` because it uses `round_exact`

## 2026-04-09 Precise Ratio Adoption

### Final rule update
- The project no longer derives displayed first DaYun age from `round(delta_days / 3.0)`.
- The displayed rule is now:
  - `precise_start_age_years = delta_days * 120 / 365.2422`
  - `display_start_age = floor(precise_start_age_years + 0.5)`
- The older `exact_start_age_years = delta_days / 3.0` is still retained for diagnostics only.

### Why this rule won
- It is the first single global rule that matches every registered golden answer sheet without per-case branching.
- It keeps the existing minute-level Jie boundary handling and Korea +1 hour standard-offset correction intact.
- It resolves the former `gomaebi` mismatch while preserving `aru`, `pororo`, and the already matched cases.

### Current validated state
- `python -m unittest discover -s tests -p "test_*.py"`: passed
- `python -m app.tools.run_golden_validation`: passed
- `pnpm --dir "D:\\5_project\\SaJu(2)\\apps\\web" build`: passed

### Current golden summary
- total cases: `7`
- total mismatches: `0`
- mismatch fields: `{}`
- case status counts:
  - `match`: `7`

### Current diagnostic interpretation
- `aru`
  - exact boundary and displayed first age both match
- `gomaebi`
  - exact boundary, DaYun sequence, and displayed first age now all match
- `pororo`
  - remains matched including the final DaYun row

### Next step
1. Close the DaYun start-age issue as resolved for the current golden set.
2. Move back to the M1 roadmap item for user-facing manse table rendering.
