# Saju Calculation Source Map

## Purpose
- Current calculation responsibility and data sources are recorded here so accuracy work does not blur provider boundaries.
- This document is descriptive. It does not authorize primary behavior changes.

## Current Pipeline Source Map

| Stage | Responsibility | Current source | Primary impact | Notes |
| --- | --- | --- | --- | --- |
| Input policy | Unknown birth-time handling, placeholder time, disabled sections | Internal code | Yes | Unknown birth time uses an internal `00:00` placeholder but disables hour pillar and luck cycles. |
| Timezone normalization | Local time, UTC time, ambiguous/nonexistent local time | Python `zoneinfo` / IANA tzdb | Yes | `fold=1` is selected for ambiguous local times. |
| DST offset | Korean DST correction for legacy regional correction | Internal table + `zoneinfo` offset | Yes | Current standard offset table only includes `Asia/Seoul`. |
| Calendar normalization | Solar/lunar/leap-month conversion | Checked-in KASI official reference table | Yes | Uses `apps/api/app/domain/saju/data/lunar_reference/` for 1900-2050 and falls back to `korean-lunar-calendar` outside the table. |
| Regional solar correction | Longitude offset plus DST offset | Internal formula | Yes | `corrected_solar_datetime = normalized_solar_datetime + regional offset + DST offset`. |
| BirthTimeContext | Debug-only observed time bases | Internal derivation | No | Records legal, standard, mean solar, and legacy corrected times. |
| Primary natal chart | Year/month/hour pillars, day derived attributes | `lunar_python` EightChar by default; canonical year/month shadow uses reference/Skyfield Jie boundaries | Yes | Year/month keep the existing corrected-time basis and legacy primary source unless `SAJU_USE_CANONICAL_YEAR_MONTH_PILLARS=1` is explicitly enabled. Day/time use the local civil basis only when the sect1 23:00 rule changes the day reference date. |
| Primary day gan-zhi | Day-pillar gan-zhi/stem/branch | Checked-in KASI iljin table, falling back to `lunar_python` | Yes | KASI iljin query uses the local civil day-pillar basis date: 23:00 and later resolves to the next solar date. |
| Candidate charts | Alternate time bases and midnight rules | Internal wrapper around `lunar_python` plus KASI day gan-zhi lookup | No by default | Stored in `debug_trace` and used for uncertainty detection. |
| Solar-term boundary risk | Nearby Jie boundary detection | Verified checked-in solar-term reference rows, Skyfield, then `lunar_python` fallback | No direct primary change | `official_reference_table` rows are used when available for the request timezone/range; Jie filtering uses canonical `term_id` membership. Otherwise prepared and checksum-verified Skyfield `de440s.bsp` is tried before the legacy fallback. Runtime requests do not download ephemeris files. |
| Luck cycles | Direction, first age, sequence | Internal formula + reference/Skyfield Jie boundary with `lunar_python` fallback | Yes | Year/month pillars are unchanged; only the adjacent Jie boundary source for DaYun start timing is provider-backed. |
| Five elements / ten gods | Relationship tables and normalized output | Engine output + internal normalization | Yes | Should stay deterministic and independently tested. |
| Special stars | 12 shinsal and auxiliary star rules | Internal rule tables | Yes | Some stars remain diagnostic until convention is fixed. |
| Interpretation payload | Facts passed to narrative layer | Internal builder | No calculation | Payload is facts-only and should not ask LLM to calculate. |
| Narrative generation | User-facing wording | OpenAI or fallback formatter | No calculation | LLM may verbalize only precomputed facts and flags. |

## Replacement Boundaries

### Already Replaced
- Solar to lunar conversion
- Lunar to solar conversion
- Leap lunar month handling
- Calendar normalization fixture coverage for known `lunar_python` gaps
- Versioned 1900-2050 lunar/solar lookup table for calendar normalization
- Primary and candidate day-pillar gan-zhi lookup for table-covered dates
- Late-zi KASI iljin query date based on local civil time, while preserving the corrected-time basis for year/month
- Luck-cycle adjacent Jie boundary lookup, using verified solar-term rows first and Skyfield fallback before the legacy path

### Diagnostic Only
- Candidate charts
- BirthTimeContext alternate time bases
- Uncertainty flags
- Accuracy mode diff report
- Canonical year/month shadow diff report
- Lunar reference diff report
- Solar-term reference lookup for uncertainty flags

### Not Yet Replaced
- Primary year pillar
- Primary month pillar
- Day-pillar derived attributes outside the late-zi day-basis correction
- Primary hour pillar outside the late-zi day-basis correction
- Solar-term provider for primary month/year boundaries

## Required Before Any Further Primary Replacement
- Official or independently reproducible reference data must exist.
- Golden primary output impact must be known.
- `accuracy_mode=legacy` must remain the default unless explicitly approved.
- `corrected_solar_datetime` must not change meaning without explicit approval.
- The replacement must be reversible and covered by regression tests.

## Related Files
- Calendar normalization: `apps/api/app/domain/saju/calendar_normalization.py`
- Lunar reference lookup: `apps/api/app/domain/saju/reference_calendar.py`
- Lunar reference data: `apps/api/app/domain/saju/data/lunar_reference/`
- Lunar reference builder: `apps/api/app/tools/build_lunar_reference_table.py`
- Primary engine adapter: `apps/api/app/domain/saju/adapters/lunar_python_engine.py`
- Time correction: `apps/api/app/domain/saju/time_correction.py`
- Candidate charts: `apps/api/app/domain/saju/services/generate_candidate_charts.py`
- Uncertainty detection: `apps/api/app/domain/saju/services/detect_uncertainty.py`
- Accuracy roadmap: `docs/planning/027-saju-accuracy-improvement-roadmap.md`
- Accuracy sync board: `docs/planning/028-accuracy-work-sync.md`
- Lunar reference table strategy: `docs/planning/031-lunar-reference-table-strategy.md`
- Solar-term boundary provider: `apps/api/app/domain/saju/services/solar_term_boundaries.py`
- Canonical year/month shadow calculator: `apps/api/app/domain/saju/services/canonical_year_month.py`
- Canonical year/month diff report: `apps/api/tests/reports/canonical_year_month_diff_report.md`
- Skyfield ephemeris preparation: `apps/api/app/tools/ensure_skyfield_ephemeris.py`
