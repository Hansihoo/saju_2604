# Canonical Year/Month Pillar Shadow Diff Report

Generated at: `2026-05-17T06:50:51Z`

Conclusion: Manual review required. The default primary remains legacy.

## Summary

| Total cases | 41 |
| Changed cases | 4 |
| Year pillar changed | 1 |
| Month pillar changed | 4 |
| Applied to primary | 0 |
| Boundary-explained changed cases | 4 |
| Boundary-explained ratio | 100.00% |

## Reason Counts

- `near_lichun_boundary`: 1
- `near_month_jie_boundary`: 3
- `unchanged`: 37

## Provider Counts

- `KASI`: 17
- `SKYFIELD`: 24

## Changed Rows

| Case | Basis | Legacy Y/M | Canonical Y/M | Boundary | Reason |
| --- | --- | --- | --- | --- | --- |
| golden:lunar_leap_month_input | 2023-04-05 09:57:58 | 癸卯 / 丙辰 | 癸卯 / 乙卯 | gyeongchip 2023-03-06 05:36:00 | near_month_jie_boundary |
| golden:solar_term_near_ipchun | 2024-02-04 16:27:58 | 甲辰 / 丙寅 | 癸卯 / 乙丑 | sohan 2024-01-06 05:49:00 | near_lichun_boundary |
| reference:kasi_lunar_leap_2023_02_15 | 2023-04-05 09:57:58 | 癸卯 / 丙辰 | 癸卯 / 乙卯 | gyeongchip 2023-03-06 05:36:00 | near_month_jie_boundary |
| reference:kasi_lunar_leap_2023_02_15_to_solar | 2023-04-05 09:57:58 | 癸卯 / 丙辰 | 癸卯 / 乙卯 | gyeongchip 2023-03-06 05:36:00 | near_month_jie_boundary |

## Regenerate

```powershell
cd apps/api
python tests/generate_canonical_year_month_diff_report.py
```
