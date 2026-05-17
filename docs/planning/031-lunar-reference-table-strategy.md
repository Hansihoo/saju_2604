# Lunar Reference Table Strategy

## Purpose
- Avoid full-range brute-force comparisons during normal tests.
- Keep lunar/solar conversion data in a versioned, reviewable asset.
- Keep KASI replacement or cross-checking a data-build problem, not a production hot path problem.

## Implemented Table

| Item | Value |
| --- | --- |
| Table id | `kasi_lunar_calendar_1900_2050` |
| Data file | `apps/api/app/domain/saju/data/lunar_reference/kasi_lunar_calendar_1900_2050.jsonl` |
| Metadata file | `apps/api/app/domain/saju/data/lunar_reference/kasi_lunar_calendar_1900_2050.meta.json` |
| Range | `1900-01-01` to `2050-12-31` |
| Row count | `55152` |
| Source | KASI official lunisolar calendar API |
| Loader | `apps/api/app/domain/saju/reference_calendar.py` |
| Builder | `apps/api/app/tools/build_lunar_reference_table.py` |
| Package data | `apps/api/pyproject.toml` includes `data/lunar_reference/*.jsonl` and `*.json` |

Each row is keyed by solar date and also contains the matching lunar date,
leap-month flag, day ganzhi, and KASI Julian day from the source data.

## Runtime Use
- `normalize_calendar()` first looks up dates in the checked-in table.
- Dates outside the table range fall back to the existing `korean-lunar-calendar` path.
- Primary and candidate day-pillar gan-zhi/stem/branch use the table when the sect-adjusted reference date is covered.
- Day-pillar reference-date mapping uses the post-calendar-normalization local civil datetime for the sect1 rule: `23:00` and later resolves to the next solar date.
- The local civil day basis is applied to day/time pillars only when it changes the sect1 reference date; year/month keep the existing corrected-time basis.
- Dates outside the table range fall back to the existing `lunar_python` day-pillar value.
- Primary year/month/hour pillars and day-pillar derived attributes otherwise still come from `lunar_python` through the saju engine adapter.

## Validation Flow

```powershell
cd apps/api
python -m app.tools.build_lunar_reference_table --check
python -m unittest tests.test_lunar_reference_table
```

The `--check` command is offline and compares:
- metadata hash
- checked-in file hash
- row count
- expected range
- duplicate solar/lunar keys

Normal tests do not rewrite the table. Updating the table is explicit:

```powershell
cd apps/api
python -m app.tools.build_lunar_reference_table
```

Updating the table requires `KASI_SERVICE_KEY`. Encoded data.go.kr keys are passed through as-is; decoded keys are URL-encoded by the builder.

For a live KASI spot check without rewriting the table:

```powershell
cd apps/api
python -m app.tools.build_lunar_reference_table --verify-with-kasi --start-date 1914-06-20 --end-date 1914-07-25
```

From the repository root, run the bundled high-risk spot-check set:

```powershell
pnpm verify:kasi
```

For full offline iljin/day-pillar comparison:

```powershell
cd apps/api
python tests/generate_iljin_reference_diff_report.py
```

After an intentional update, run:

```powershell
pnpm test:api
python -m app.tools.run_golden_validation
```

## Review Policy
- Do not auto-refresh the table in `pnpm test:api`.
- Do not use this table alone to replace solar-term, month-pillar, or luck-cycle boundary logic.
- Keep source, retrieval date, range, row count, and hash in metadata for every table update.
- Any mismatch should be classified before changing production behavior:
  - source data difference
  - leap-month handling
  - iljin/day-ganzhi difference
  - unsupported range
  - provider convention difference

## Current Boundary
- Calendar normalization is table-backed for 1900-2050.
- Day-pillar gan-zhi is table-backed for 1900-2050 when the reference date is covered.
- 23:00 late-zi KASI iljin lookup uses the local civil basis date and records `iljin_query_date` in manse metadata.
- `accuracy_mode=legacy` remains the default.
- `corrected_solar_datetime` keeps its existing meaning.
- Primary manse pillar outputs and first luck-cycle output are protected by golden tests.
