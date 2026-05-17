# Accuracy Work Sync

## Purpose
- Keep accuracy work aligned while primary behavior stays protected.
- Prefer data, fixtures, and reports before changing calculation providers.
- Treat this file as the lightweight status board for accuracy-related work.

## Source Of Truth
- Accuracy roadmap: `docs/planning/027-saju-accuracy-improvement-roadmap.md`
- Calculation source map: `docs/planning/029-saju-calculation-source-map.md`
- Current calculation rules: `docs/planning/033-current-calculation-rules.md`
- Golden/reference coverage: `docs/planning/030-golden-reference-coverage.md`
- Lunar reference table strategy: `docs/planning/031-lunar-reference-table-strategy.md`
- Solar-term reference table strategy: `docs/planning/032-solar-term-reference-table-strategy.md`
- Golden validation system: `docs/planning/016-golden-answer-validation-system.md`
- DaYun formula validation: `docs/planning/017-daeun-formula-validation-update.md`
- Accuracy mode diff report: `apps/api/tests/reports/accuracy_mode_diff_report.md`
- Lunar reference diff report: `apps/api/tests/reports/lunar_reference_diff_report.md`
- KASI iljin/day-pillar diff report: `apps/api/tests/reports/iljin_reference_diff_report.md`
- Solar-term reference diff report: `apps/api/tests/reports/solar_term_reference_diff_report.md`
- Canonical year/month shadow diff report: `apps/api/tests/reports/canonical_year_month_diff_report.md`
- Reference fixtures: `apps/api/tests/fixtures/reference_cases/`
- Lunar reference table: `apps/api/app/domain/saju/data/lunar_reference/`
- Solar-term reference table: `apps/api/app/domain/saju/data/solar_terms_reference/`
- Skyfield ephemeris prepare command: `pnpm ensure:skyfield`

## Current Direction
- Keep default primary mode as `accuracy_mode=legacy`.
- Keep `corrected_solar_datetime` meaning unchanged.
- Keep primary manse pillars protected by golden tests.
- Any first luck-cycle change must be tied to an explicit reference/Skyfield boundary source and verified before release.
- Use checked-in reference data for fast lookup and reviewable validation.
- Use verified solar-term reference rows where they are approved; otherwise use Skyfield ephemeris for boundary lookup, with `lunar_python` kept as the last fallback.
- Treat `de440s.bsp` as a prepared runtime resource: download/verify before serving requests, never during requests.
- Keep canonical year/month pillar calculation in shadow mode unless `SAJU_USE_CANONICAL_YEAR_MONTH_PILLARS=1` is explicitly enabled.
- Use the checked-in KASI iljin table for primary day-pillar gan-zhi when the reference date is covered; fall back to `lunar_python` outside the table.
- For sect1 late-zi, derive the KASI iljin query date from the local civil datetime after calendar normalization; keep year/month on the existing corrected-time basis.
- Keep candidate charts, alternate time bases, and uncertainty details in debug/developer paths unless explicitly promoted.
- LLMs may verbalize only precomputed facts; they must not calculate pillars or uncertainty.

## Status Board

| Status | Item | Linked IDs | Next action |
| --- | --- | --- | --- |
| Done | Replace calendar normalization source with KASI official data | A01 | Keep live KASI verification as an explicit maintenance command. |
| Done | Add checked-in 1900-2050 lunar/solar reference table | A01, A02 | Maintain table hash and review mismatches through reports. |
| Done | Add table integrity checks and lookup tests | A01, A16 | Keep checks in safety script and API tests. |
| Done | KASI lunar/solar/iljin reference values | A02, A03 | Hard fixtures now use KASI official values. |
| Done | Promote day-pillar gan-zhi to KASI table-backed lookup | A03 | Keep full-range iljin diff report at zero mismatch; fallback remains `lunar_python`. |
| Done | Fix late-zi iljin query date basis | A03, A07 | 23:00+ uses the local civil next-day iljin query date and recalculates the hour pillar from the adjusted day stem. |
| Ongoing | Solar-term boundary reference values | A04, A05, A06 | Verified `official_reference_table` rows are used first; Skyfield fills missing/unverified boundary lookup; secondary rows still need KASI image/PDF cross-check before use. |
| Needs review | Unknown birth-time interval policy | A11, A17 | Keep placeholder-based candidate warnings limited. |
| Needs review | DaYun start-age official/expert comparison | A12 | Primary DaYun adjacent Jie boundary now prefers KASI official rows, then Skyfield, then legacy fallback; compare against expert manse sheets near solar-term boundaries. |
| Ongoing | Accuracy mode diff report refresh | A16 | Regenerate after fixture/table updates. |
| Deferred | True solar time primary switch | A08, A09 | Keep candidate/debug only until equation-of-time data is validated. |
| Ongoing | Solar-term provider replacement | A05 | Boundary provider selection is now reference -> Skyfield -> lunar fallback. Canonical year/month shadow calculation and diff report exist; primary replacement stays behind an off-by-default feature flag. |
| Deferred | Deterministic annual luck module | A13 | Add after major-cycle and solar-term sources are stable. |

## Update Rules
- Update this file whenever an accuracy-related source, fixture, report, or provider boundary changes.
- Do not adjust golden expected values just to make tests pass.
- If a mismatch appears, classify it first:
  - input normalization
  - timezone/DST
  - lunar/solar conversion
  - solar-term boundary
  - midnight rule
  - luck-cycle start-age
  - source/reference difference
- Any production calculation change must record:
  - changed calculation basis
  - golden primary impact
  - reference validation result
  - rollback path

## Next Checklist
- [x] Build checked-in lunar/solar reference table for 1900-2050.
- [x] Add table loader and integrity checks.
- [x] Use table lookup for calendar normalization while preserving legacy primary behavior.
- [x] Collect KASI lunar/solar/iljin reference values.
- [x] Compare KASI values with the checked-in table and current hard fixtures.
- [x] Add KASI-confirmed hard reference cases.
- [x] Build initial solar-term timestamp references for common recent years.
- [x] Extend solar-term timestamp references with KASI almanac archive years 2011-2017.
- [x] Fill 2018-2020 from KASI annual almanac PDFs.
- [x] Add an extended candidate solar-term table for current age-80 review coverage.
- [x] Use verified solar-term reference rows for uncertainty boundary lookup and fall back to Skyfield/`lunar_python` when verified rows are unavailable.
- [x] Use the same reference -> Skyfield -> fallback boundary path for DaYun adjacent Jie lookup while keeping primary pillars unchanged.
- [x] Add non-rounded year/month precision fields for DaYun start/change ages while preserving legacy `start_age`.
- [x] Add full-range KASI iljin/day-pillar diff report generation.
- [x] Use checked-in KASI iljin values for day-pillar gan-zhi when table coverage exists.
- [x] Add KASI solar-term reference vs `lunar_python` timestamp diff report generation.
- [x] Add verified solar-term boundary threshold hard tests for common Jie boundaries.
- [x] Add KASI live spot-check command as an explicit maintenance action.
- [x] Add Skyfield ephemeris prepare/check command and runtime no-download validation.
- [x] Add canonical year/month pillar shadow calculation and diff report with primary flag default off.
- [ ] Replace or confirm extended secondary solar-term rows with official KASI image/PDF checks.
- [ ] Confirm solar-term timestamp rows against official 월력요항/관보 sources.
- [ ] Continue collecting verified solar-term data so more of the age-80 range can move from fallback to reference lookup.
- [ ] Refresh `accuracy_mode_diff_report.md` after new references are added.

## Validation Commands

```powershell
pnpm ensure:skyfield
pnpm test:api
pnpm --filter web build
cd apps/api
python -m app.tools.ensure_skyfield_ephemeris --check
python -m app.tools.build_lunar_reference_table --check
python -m app.tools.build_solar_term_reference_table --check
python -m app.tools.build_extended_solar_term_reference_table --check
python -m app.tools.run_golden_validation
python tests/generate_iljin_reference_diff_report.py
python tests/generate_lunar_reference_diff_report.py
python tests/generate_solar_term_reference_diff_report.py
python tests/generate_accuracy_mode_diff_report.py
python tests/generate_canonical_year_month_diff_report.py
```

Or run the bundled safety check from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File ./scripts/accuracy-safety-check.ps1
```

## Last Sync
- Date: 2026-05-17
- Summary:
  - Added the versioned lunar/solar reference table and loader.
  - Regenerated the lunar/solar reference table from KASI official API values.
  - Connected calendar normalization to table lookup for the table range.
  - Fixed solar-input leap-month reporting so converted lunar leap months are exposed correctly.
  - Added integrity tests and safety-script validation.
  - Preserved `accuracy_mode=legacy`, `corrected_solar_datetime`, primary pillars, and first luck-cycle behavior.
  - Added KASI solar-term timestamp table for 2011-2027 with resumable manifest/log collection.
  - Added an extended mixed-source solar-term candidate table for 1946-2027 age-80 coverage review.
  - Recorded that 1946 is partial and that 1946-2011 secondary rows are not approved for primary use until KASI image/PDF cross-check.
  - Added reference/fallback solar-term boundary lookup for uncertainty flags: verified rows are used when available, otherwise Skyfield is tried before the previous `lunar_python` lookup.
  - Recorded that verified solar-term data must continue to be collected before any primary provider promotion.
  - Added month-level DaYun age precision so reports and UI are not forced to rely only on rounded `start_age`.
  - Added safe diagnostic reports for full KASI iljin comparison and KASI solar-term timestamp drift.
  - Added explicit `pnpm verify:kasi` live spot-check path; normal tests still do not call KASI.
  - Promoted KASI iljin/day-pillar gan-zhi lookup into the primary engine and candidate/uncertainty paths for covered dates, with `lunar_python` fallback and no golden output change.
  - Corrected the 23:00 late-zi path so KASI iljin lookup uses the local civil day-pillar basis date; year/month and `corrected_solar_datetime` remain unchanged.
  - Added Skyfield `almanac_east_asia.solar_terms` as the independent ephemeris fallback for solar-term boundaries and connected DaYun adjacent Jie lookup to the same provider path.
  - Canonicalized Jie detection by `term_id` so `sohan` is treated as a month boundary even when a source row labels it as `junggi`.
  - Added `pnpm ensure:skyfield` / `app.tools.ensure_skyfield_ephemeris` so `de440s.bsp` is prepared and checksum-verified before runtime; runtime Skyfield loading now refuses to download.
  - Added canonical year/month pillar shadow calculation using the same solar-term provider path, plus `canonical_year_month_diff_report.md`; production primary remains legacy unless `SAJU_USE_CANONICAL_YEAR_MONTH_PILLARS=1` is explicitly set.
