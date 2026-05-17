# KASI Iljin Reference Diff Report

- Generated at: `2026-05-17T06:48:12.850080+00:00`
- Range: `1900-01-01` to `2050-12-31`
- Reference candidate: checked-in KASI `day_ganzhi_hanja` values
- Compared candidate: `lunar_python` `Lunar.getDayInGanZhi()`
- Purpose: verify the table-backed primary day-pillar gan-zhi source.

## Summary

| Metric | Count |
| --- | ---: |
| Total compared dates | 55152 |
| Mismatch dates | 0 |

## Mismatches By Year

None.

## Sample Mismatches

None.

## Review Notes

- If mismatches appear, inspect them before extending or changing the day-pillar provider.
- This report intentionally compares only the day ganzhi/iljin field.
- Lunar/solar conversion drift is covered separately by `lunar_reference_diff_report.md`.

## Regenerate

```powershell
cd apps/api
python tests/generate_iljin_reference_diff_report.py
```
