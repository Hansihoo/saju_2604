# Solar-Term Reference Table Strategy

## Purpose
- Build a reviewable KASI-published 24 solar-term timestamp table before changing any primary saju calculation.
- Collect high-traffic/common years first instead of attempting the full historical range in one run.
- Make collection resumable so an interrupted run can continue without losing completed years.

## Current Table
- Table id: `kasi_solar_terms_common_years`
- Rows: `apps/api/app/domain/saju/data/solar_terms_reference/kasi_solar_terms_common_years.jsonl`
- Metadata: `apps/api/app/domain/saju/data/solar_terms_reference/kasi_solar_terms_common_years.meta.json`
- Manifest: `apps/api/app/domain/saju/data/solar_terms_reference/kasi_solar_terms_common_years.manifest.json`
- Collection log: `apps/api/app/domain/saju/data/solar_terms_reference/kasi_solar_terms_common_years.collection.log.jsonl`
- Current collected years: 2011-2027
- Current row count: 408

## Extended Candidate Table
- Table id: `solar_terms_extended_1946_2027`
- Rows: `apps/api/app/domain/saju/data/solar_terms_reference/solar_terms_extended_1946_2027.jsonl`
- Metadata: `apps/api/app/domain/saju/data/solar_terms_reference/solar_terms_extended_1946_2027.meta.json`
- Collection log: `apps/api/app/domain/saju/data/solar_terms_reference/solar_terms_extended_1946_2027.collection.log.jsonl`
- Target purpose: current age-80 coverage as of 2026, using 1946-2027 as the review range.
- Current row count: 1966
- Complete years: 1947-2027
- Partial year: 1946, missing `sohan` and `daehan`.
- Source mix:
  - 2012-2027 is copied from the existing KASI-oriented table.
  - 1946-2011 uses a secondary Bebeyam KASI-almanac transcription with Uncle Tools comparison metadata.
- This table is a review candidate, not a primary calculation provider.

## Source Policy
- Current sources are KASI almanac archive HTML, KASI annual almanac PDF, and KASI `calendarData` pages/downloads.
- Each row keeps the KASI page URL, source method, source file name when available, and `official_almanac_confirmation`.
- `official_almanac_confirmation` remains `pending` until the matching 월력요항/관보 source is parsed.
- The table is reference data only. It is not used by the primary calculation path yet.
- Annual almanac PDF extraction uses `pypdf`; this is a maintenance-script dependency, not a runtime calculation provider.
- KASI year pages for 1946-2010 are available in the discovered interface, but they are image-only for the needed table, so direct machine extraction remains pending.
- The KASI `pageView/1` archive section for 2011 appears to expose stale 2004-like solar-term rows. Do not promote that 2011 archive extraction without an independent official check.
- Secondary transcriptions may be useful for coverage planning, but rows with `source_role=extended_secondary_reference` require KASI image/PDF cross-check before primary use.

## Runtime Lookup Policy
- `apps/api/app/domain/saju/services/solar_term_boundaries.py` uses checked-in reference rows only for uncertainty boundary lookup.
- A row is considered usable only when `source_role=official_reference_table` and the request timezone is `Asia/Seoul`.
- Runtime Jie filtering uses canonical `term_id` membership, not only the stored `term_type`, because some source rows label `sohan` as `junggi` even though it is a month-boundary Jie for this engine.
- If a usable reference row is unavailable, unsupported for the timezone, or outside the verified range, lookup tries Skyfield `almanac_east_asia.solar_terms` with `de440s.bsp`.
- The runtime loader validates an existing `de440s.bsp` file by size and SHA256 and does not download during requests.
- Prepare the file with `pnpm ensure:skyfield` or `python -m app.tools.ensure_skyfield_ephemeris --download --check`.
- Set `SAJU_SKYFIELD_DATA_DIR` to pin the ephemeris directory in production; otherwise the user cache directory is used.
- If Skyfield is unavailable, unprepared, invalid, or cannot resolve the boundary, lookup falls back to the previous `lunar_python` `getPrevJie()`/`getNextJie()` path and keeps evidence on the fallback path.
- The DaYun adjacent Jie boundary uses the same provider order: verified reference row, Skyfield, then legacy lunar_python fallback.
- This does not change primary year/month/day/hour pillars or `corrected_solar_datetime`.
- Verified solar-term data collection must continue so more of the 1946-2027 age-80 review range can be moved from fallback to reference lookup.

## Resume Commands
Run from `apps/api`:

```powershell
python -m app.tools.build_solar_term_reference_table --limit 2
python -m app.tools.build_solar_term_reference_table
python -m app.tools.build_solar_term_reference_table --check
```

Build or verify the extended candidate table:

```powershell
python -m app.tools.build_extended_solar_term_reference_table
python -m app.tools.build_extended_solar_term_reference_table --check
```

Use an explicit year set when expanding in small batches:

```powershell
python -m app.tools.build_solar_term_reference_table --years 2011-2017 --limit 2
python -m app.tools.build_solar_term_reference_table --years 2018-2019 --limit 1
python -m app.tools.build_solar_term_reference_table --years 2020 --refresh
python -m app.tools.build_solar_term_reference_table --years 2021-2027
```

Completed years are skipped unless `--refresh` is set. Every attempt appends to the JSONL collection log.

## Validation
- `pnpm ensure:skyfield`
- `python -m app.tools.ensure_skyfield_ephemeris --check`
- `python -m app.tools.build_solar_term_reference_table --check`
- `python -m app.tools.build_extended_solar_term_reference_table --check`
- `python -m unittest tests.test_solar_term_reference_table`
- `python -m unittest tests.test_extended_solar_term_reference_table`
- `python -m unittest tests.test_solar_term_boundaries`
- `python tests/generate_solar_term_reference_diff_report.py`
- `pnpm test:api`

## Diagnostic Diff Report
- Report: `apps/api/tests/reports/solar_term_reference_diff_report.md`
- Compares checked-in KASI solar-term timestamps against nearest `lunar_python` JieQi timestamps.
- The report is diagnostic only and does not promote any provider into primary calculation.

## Promotion Gate
Do not use this table as a primary year/month boundary provider until:
- the target years are confirmed against official 월력요항/관보 where available,
- golden primary pillars remain unchanged unless a deliberate migration is approved,
- lunar_python boundary differences are reported separately,
- rollback to `accuracy_mode=legacy` remains available.
- any extended secondary rows needed for primary behavior are either replaced with official KASI machine-readable rows or manually cross-checked from the KASI source image/PDF.
