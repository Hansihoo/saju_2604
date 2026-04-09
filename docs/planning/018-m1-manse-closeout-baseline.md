# M1 Manse Closeout Baseline 018

## Goal
- Freeze the current M1 baseline for code-driven saju calculation and manse validation.
- Clarify what is already stable before moving into M2 LLM-based interpretation.

## Included In M1
- Birth input validation
- Region selection through autocomplete
- Time normalization and regional solar correction
- Solar/lunar normalization
- Four-pillars calculation
- Manse schema generation
- Decade luck-cycle calculation
- Golden-answer validation pipeline
- User-facing summary result contract without raw manse table exposure

## Explicitly Excluded From M1
- LLM-generated narrative
- User-facing raw manse table rendering
- Account, storage, and history features
- Official production-grade national region dataset

## Stable Contracts

### Region boundary
- Region access now goes through a typed repository boundary.
- Current seed fields:
  - `id`
  - `display_name`
  - `country`
  - `province`
  - `city`
  - `tzid`
  - `longitude`
  - `regional_time_offset_minutes`
  - `correction_basis`
  - `aliases`
- Future swap-in fields already reserved:
  - `latitude`
  - `admin_code`
  - `source`
  - `is_active`

### Preview response
- `response_mode` is now `preview`
- `manse` remains part of the backend/debug contract
- `result.signals` is the stable frontend-facing summary input for M1 and M2

### Luck-cycle rule
- Internal diagnostic value:
  - `exact_start_age_years = delta_days / 3.0`
- Displayed start age baseline:
  - `precise_start_age_years = delta_days * 120 / 365.2422`
  - `display_start_age = floor(precise_start_age_years + 0.5)`

## Validation Baseline
- Backend unit tests pass
- Golden validation matches all registered answer sheets
- Frontend production build passes

## Current Exit Condition For M1
- Keep the current region boundary stable
- Keep user-facing result output summary-only
- Do not re-open manse or DaYun formulas unless a new verified answer sheet fails
- Treat `response.manse` as the stable backend/debug contract for:
  - raw pillars
  - table rows
  - supplementary positions
  - luck cycles
  - code-driven analysis summary

## Next Step
- M2 should build LLM input payloads on top of:
  - `result.signals`
  - `result.limitations`
  - `manse` backend data
  - selected evidence summaries
- 만세력 응답은 raw table만이 아니라 analysis block까지 포함해, 후속 해석 단계가 점수 근거와 첫 대운 메타를 직접 재사용할 수 있다.
