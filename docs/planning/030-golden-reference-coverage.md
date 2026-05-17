# Golden And Reference Coverage

## Purpose
- Golden answer sheets and reference fixtures protect different risks.
- This document records current coverage and missing coverage so accuracy work can choose the next safest case to add.

## Coverage Types

| Type | Location | Purpose |
| --- | --- | --- |
| Golden answer sheets | `apps/api/tests/golden_cases/` | Compare against known manse answer sheets and protect user-visible primary output. |
| Preview golden baseline | `apps/api/tests/fixtures/saju_preview_golden_cases.json` | Freeze API-level primary fields such as corrected time, pillars, and first luck cycle. |
| Hard reference fixtures | `apps/api/tests/fixtures/reference_cases/` | Compare individual technical layers against external or official expected values. |
| Pending reference fixtures | `apps/api/tests/fixtures/reference_cases/` | Track values that must be collected before becoming hard references. |
| Versioned lunar reference table | `apps/api/app/domain/saju/data/lunar_reference/` | Provide fast deterministic lunar/solar lookup without full-range test scans. |
| Diagnostic reports | `apps/api/tests/reports/` | Show mode/provider differences without changing primary behavior. |

## Current Golden Coverage

| Area | Current coverage | Gap |
| --- | --- | --- |
| Korean solar regular birth | Covered | Add more years and regions. |
| Unknown birth time | Covered in preview baseline/tests | Add more solar-term-day unknown cases. |
| Late-zi boundary | Covered | Add externally reviewed answer sheets for both midnight rules. |
| Early after midnight | Covered | Add more regions/timezones. |
| Seoul longitude correction | Covered | Add regional examples outside Seoul. |
| Korea 1988 DST | Covered | Add DST start/end boundary cases. |
| Lunar input | Covered with KASI table and fixtures | Add more historical edge cases if needed. |
| Leap lunar input | Covered with KASI table and fixtures | Add more leap-month edge cases if needed. |
| Solar-term boundary | Partially covered by uncertainty tests | Needs official/independent boundary timestamps. |
| Overseas timezone | Covered | Add ambiguous/nonexistent timezone cases for preview flow. |
| DaYun first age and sequence | Covered by golden set | Needs more expert answer sheets around solar-term boundaries. |

## Current Hard Reference Coverage

| Area | Current hard references | Gap |
| --- | --- | --- |
| Timezone/DST | `zoneinfo` Asia/Seoul, New York, Berlin | Add more historical Korea edge cases if needed. |
| Midnight boundary | `lunar_python` sect1 convention fixtures | Add external reviewed convention cases. |
| Lunar/solar conversion | Checked-in 1900-2050 KASI table plus KASI hard reference fixtures | Keep live KASI spot checks explicit. |
| Iljin/day pillar | Full checked-in KASI table backs day-pillar gan-zhi for covered dates and is compared through `iljin_reference_diff_report.md` | Review any future mismatch before extending provider scope. |
| Solar terms | KASI hard references exist for 2018-2020 and 2024 common boundaries; threshold tests use verified rows | Fill more KASI/ephemeris timestamps and cross-check secondary rows. |

## Next Coverage Additions
1. Expert manse answer sheets near solar-term boundaries.
2. Expert manse answer sheets around 23:00 and 00:00 conventions.
3. More overseas timezone cases with known timezone behavior.
4. Official cross-checks for secondary 1947-2010 solar-term rows.

## Lunar Reference Table Checks
- Table data: `apps/api/app/domain/saju/data/lunar_reference/kasi_lunar_calendar_1900_2050.jsonl`
- Metadata/hash: `apps/api/app/domain/saju/data/lunar_reference/kasi_lunar_calendar_1900_2050.meta.json`
- Build/update command: `cd apps/api && python -m app.tools.build_lunar_reference_table`
- Integrity command: `cd apps/api && python -m app.tools.build_lunar_reference_table --check`
- The table is not refreshed during normal tests; tests validate the checked-in file and representative lookups.

## Explicit Live KASI Spot Check
- Command: `pnpm verify:kasi`
- Scope: selected high-risk ranges, including 1914 leap-month boundary, 2023 leap lunar month, and 2024 lunar new year.
- This command requires `KASI_SERVICE_KEY` and is not part of normal `pnpm test:api`.

## Review Rule
- A new case should state which risk it protects.
- A new hard reference must include source, retrieval date, tolerance, and expected values.
- A new golden answer should not be adjusted to fit the engine; mismatches must be diagnosed first.
