# Saju Accuracy Improvement Roadmap

## Purpose
- Track the work needed to improve manse calculation accuracy without losing the protected legacy baseline.
- Keep calculation logic, reference data, verification reports, and narrative generation responsibilities separate.
- Keep `accuracy_mode=legacy` as the default until primary behavior changes are explicitly approved.
- LLMs may verbalize precomputed facts only; they must not calculate pillars, luck cycles, or uncertainty.

## Sync Note
- Current status and next actions are synchronized in `docs/planning/028-accuracy-work-sync.md`.
- This document keeps the direction and item list stable; the sync doc records daily state.

## Current Baseline
- Solar/lunar normalization uses a checked-in KASI official 1900-2050 reference table.
- Primary day-pillar gan-zhi uses the checked-in KASI iljin table for covered dates and falls back to `lunar_python` outside the table.
- Primary year/month/hour pillars, and day-pillar derived attributes, still come from `lunar_python`.
- Sect1 23:00 late-zi day-pillar lookup uses the local civil datetime after calendar normalization, so `23:00` and later queries the next KASI iljin date.
- Primary DaYun adjacent Jie boundary lookup now prefers verified solar-term reference rows, then Skyfield, then the legacy `lunar_python` fallback.
- Primary year/month pillar boundaries still come from `lunar_python`.
- Canonical year/month pillar calculation exists in shadow mode and is recorded in debug/report paths; `SAJU_USE_CANONICAL_YEAR_MONTH_PILLARS` is off by default.
- Solar-term boundary uncertainty lookup now uses verified checked-in reference rows where available and falls back to Skyfield/`lunar_python` otherwise.
- `corrected_solar_datetime` keeps its existing legacy meaning.
- Golden tests, reference fixtures, and accuracy-mode diff reports protect the current behavior.
- Alternate time bases and candidate charts stay in debug/developer paths unless explicitly promoted.

## Accuracy Items

| ID | Item | Goal | Current status | Data needed | Priority | Done when |
| --- | --- | --- | --- | --- | --- | --- |
| A01 | Replace lunar/solar conversion data | Remove solar/lunar/leap-month conversion errors | Done | KASI official reference table | High | Round-trip tests and golden tests pass |
| A02 | KASI lunar/solar/iljin references | Verify against official external values | Done for calendar normalization | KASI API | High | Hard reference fixtures contain expected values |
| A03 | Independent iljin/day-pillar validation | Compare and table-back day-pillar gan-zhi against external references | Done for KASI 1900-2050 day gan-zhi; expert sheets still useful for convention review | KASI iljin, expert manse sheets | High | Mismatch report is reviewed and documented |
| A04 | Solar-term timestamp references | Verify year/month boundary and luck-cycle boundary times | KASI-oriented table built for 2011-2027; extended candidate table covers 1947-2027 complete years and 1946 partial | KASI calendarData, KASI almanac archive/PDF, remaining image/gazette confirmation pending | High | Boundary fixtures pass within tolerance |
| A05 | Solar-term provider replacement review | Decide whether to reduce `lunar_python` solar-term dependency | DaYun/uncertainty boundary lookup now uses reference -> Skyfield -> legacy fallback; year/month shadow calculation and diff report exist | A04 results plus Skyfield validation | High | Provider comparison is documented |
| A06 | Year/month boundary tests | Protect chart changes near solar terms | Partial; canonical shadow tests cover Ipchun/Gyeongchip/Cheongmyeong/Sohan/Daeseol boundaries | A04 references | High | Ipchun/Gyeongchip/Cheongmyeong/Ipha fixtures pass |
| A07 | Midnight-rule verification | Detect sect1/sect2 differences around 23:00 and 00:00 | Fixed for local civil KASI iljin query date; more expert convention examples still useful | Internal rules and expert convention examples | Medium | Default behavior stays protected and differences are reported |
| A08 | Standard/mean/true solar time separation | Make longitude and equation-of-time concepts explicit | Diagnostic exists | Longitude and equation-of-time data | Medium | Legacy/standard/mean/true bases are reported separately |
| A09 | True solar time option validation | Improve optional true-solar-time accuracy | Pending | Skyfield/Astropy or validated equation-of-time table | Low | Optional mode passes references without changing default |
| A10 | DST/timezone validation | Protect legal-time conversion | Partial | IANA tzdb/zoneinfo expected values | Medium | Ambiguous/nonexistent/DST cases pass |
| A11 | Unknown birth-time interval handling | Prevent `00:00` placeholder from being treated as exact | Stabilized, needs review | No extra data | High | Unknown-time flags stay limited and hour/luck sections disabled |
| A12 | DaYun start-age validation | Verify first luck-cycle age and direction | Partial; adjacent Jie boundary now uses reference/Skyfield when available, legacy rounded `start_age` is preserved, and non-rounded year/month precision fields are exposed | Expert manse sheets, solar-term references | High | First luck-cycle fixtures pass |
| A13 | Deterministic annual luck module | Keep annual luck out of LLM calculation | Pending | Ganzhi/year rules | Medium | Annual-luck fixtures pass |
| A14 | Ten-gods/hidden-stems rule table lock | Protect interpretation input facts | Partial | Internal rule tables and comparison cases | Medium | Rule-table snapshots pass |
| A15 | Special-star convention cleanup | Document convention differences | Partial | Chosen convention references | Low | Strict/diagnostic rules are separated |
| A16 | Candidate chart diff report | Understand impact before primary promotion | Exists | Golden/reference cases | High | Mode-by-mode pillar/luck differences are reported |
| A17 | Uncertainty flag stability | Surface uncertainty without warning spam | Exists, stabilized | Candidate charts and BirthTimeContext | High | Warning/critical flags are evidence-based |
| A18 | Reference fixture expansion | Move from internal comparisons to external references | Ongoing | KASI, tzdb, ephemeris, expert manse | High | Pending references are promoted to hard references over time |
| A19 | Golden answer coverage expansion | Protect known answer-sheet behavior | Partial | Verified answer sheets | Medium | More cases pass `run_golden_validation` |
| A20 | LLM payload consistency validation | Prevent narrative/calculation conflicts | Partial | No extra data | Medium | Payload and output consistency tests pass |

## Immediate Next Work
1. Keep the KASI lunar reference table hash and metadata stable.
2. Confirm the initial KASI solar-term timestamp rows against official almanac/gazette sources.
3. Cross-check extended secondary solar-term rows against official KASI source images/PDFs before any primary promotion.
4. Continue collecting verified solar-term data so age-80 coverage can move from fallback to reference lookup.
5. Use DaYun year/month precision in reports before considering any rounded `start_age` policy change.
6. Continue reviewing KASI iljin and solar-term diff reports before extending provider promotion.
7. Add expert manse sheets for solar-term and midnight boundaries.
8. Refresh `accuracy_mode_diff_report` after fixture/table updates.
9. Review `canonical_year_month_diff_report` before enabling canonical year/month primary behavior.
10. Do not change primary year/month/hour providers until reference impact is known.

## Data Plan
- Do not call official APIs on every user request.
- Fetch official data as an explicit maintenance action and store it as a versioned dataset or fixture.
- Record source, retrieval date, supported range, timezone, tolerance, row count, and hash.
- If sources disagree, document the mismatch before changing production behavior.

## Replacement Policy
- Already safe to replace:
  - Solar/lunar conversion
  - Leap-month detection
  - Lunar-input to solar-date normalization
  - Day-pillar gan-zhi for 1900-2050 table-covered dates, with `lunar_python` fallback
  - DaYun adjacent Jie boundary lookup, using KASI official rows first and Skyfield fallback before `lunar_python`
- Requires more verification before replacement:
  - Broad solar-term timestamp replacement for year/month pillar boundaries
  - Canonical year/month primary switch; shadow calculation exists but feature flag defaults off
- Debug/optional only until approved:
  - Standard solar time primary
  - Mean solar time primary
  - True solar time primary
- Not a calculation source:
  - LLM narrative wording
  - General user UI debug details

## Validation Commands

```powershell
pnpm test:api
pnpm --filter web build
cd apps/api
python -m unittest discover -s tests -p "test_*.py"
python -m app.tools.build_lunar_reference_table --check
python -m app.tools.build_solar_term_reference_table --check
python -m app.tools.build_extended_solar_term_reference_table --check
python tests/generate_iljin_reference_diff_report.py
python tests/generate_solar_term_reference_diff_report.py
python -m app.tools.run_golden_validation
python tests/generate_accuracy_mode_diff_report.py
python tests/generate_canonical_year_month_diff_report.py
```

## Do Not Change Without Explicit Approval
- `accuracy_mode` default value: `legacy`
- `corrected_solar_datetime` formula and meaning
- Legacy primary pillar outputs
- Existing API response field names or field removal
- Debug exposure level on the general user screen
