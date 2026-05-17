# Lunar Reference Diff Report

- Generated at: `2026-05-17T06:48:14.044021+00:00`
- Ranges: `1914-06-20` to `1914-07-25`, `1956-12-25` to `1957-01-05`, `2023-03-20` to `2023-04-10`, `2024-02-01` to `2024-02-15`, `1988-05-15` to `1988-05-25`
- Reference candidate: checked-in `kasi_lunar_calendar_1900_2050` table
- Compared candidate: `lunar_python`
- Purpose: diagnostic only. This report does not change production primary pillars.

## Summary

| Metric | Count |
| --- | ---: |
| Total compared dates | 96 |
| Mismatch dates | 30 |
| Skipped dates | 0 |

## Field Mismatches

| Field | Count |
| --- | ---: |
| is_lunar_leap_month | 1 |
| lunar_day | 30 |

## Lunar Date Mismatch Ranges

| Start | End | Days |
| --- | --- | ---: |
| 1914-06-23 | 1914-07-22 | 30 |

## Sample Mismatches

| Solar date | Changed fields | reference table | lunar_python |
| --- | --- | --- | --- |
| 1914-06-23 | lunar_day, is_lunar_leap_month | 1914-05-30 regular 庚辰 | 1914-05-01 leap 庚辰 |
| 1914-06-24 | lunar_day | 1914-05-01 leap 辛巳 | 1914-05-02 leap 辛巳 |
| 1914-06-25 | lunar_day | 1914-05-02 leap 壬午 | 1914-05-03 leap 壬午 |
| 1914-06-26 | lunar_day | 1914-05-03 leap 癸未 | 1914-05-04 leap 癸未 |
| 1914-06-27 | lunar_day | 1914-05-04 leap 甲申 | 1914-05-05 leap 甲申 |
| 1914-06-28 | lunar_day | 1914-05-05 leap 乙酉 | 1914-05-06 leap 乙酉 |
| 1914-06-29 | lunar_day | 1914-05-06 leap 丙戌 | 1914-05-07 leap 丙戌 |
| 1914-06-30 | lunar_day | 1914-05-07 leap 丁亥 | 1914-05-08 leap 丁亥 |
| 1914-07-01 | lunar_day | 1914-05-08 leap 戊子 | 1914-05-09 leap 戊子 |
| 1914-07-02 | lunar_day | 1914-05-09 leap 己丑 | 1914-05-10 leap 己丑 |
| 1914-07-03 | lunar_day | 1914-05-10 leap 庚寅 | 1914-05-11 leap 庚寅 |
| 1914-07-04 | lunar_day | 1914-05-11 leap 辛卯 | 1914-05-12 leap 辛卯 |
| 1914-07-05 | lunar_day | 1914-05-12 leap 壬辰 | 1914-05-13 leap 壬辰 |
| 1914-07-06 | lunar_day | 1914-05-13 leap 癸巳 | 1914-05-14 leap 癸巳 |
| 1914-07-07 | lunar_day | 1914-05-14 leap 甲午 | 1914-05-15 leap 甲午 |
| 1914-07-08 | lunar_day | 1914-05-15 leap 乙未 | 1914-05-16 leap 乙未 |
| 1914-07-09 | lunar_day | 1914-05-16 leap 丙申 | 1914-05-17 leap 丙申 |
| 1914-07-10 | lunar_day | 1914-05-17 leap 丁酉 | 1914-05-18 leap 丁酉 |
| 1914-07-11 | lunar_day | 1914-05-18 leap 戊戌 | 1914-05-19 leap 戊戌 |
| 1914-07-12 | lunar_day | 1914-05-19 leap 己亥 | 1914-05-20 leap 己亥 |
| 1914-07-13 | lunar_day | 1914-05-20 leap 庚子 | 1914-05-21 leap 庚子 |
| 1914-07-14 | lunar_day | 1914-05-21 leap 辛丑 | 1914-05-22 leap 辛丑 |
| 1914-07-15 | lunar_day | 1914-05-22 leap 壬寅 | 1914-05-23 leap 壬寅 |
| 1914-07-16 | lunar_day | 1914-05-23 leap 癸卯 | 1914-05-24 leap 癸卯 |
| 1914-07-17 | lunar_day | 1914-05-24 leap 甲辰 | 1914-05-25 leap 甲辰 |
| 1914-07-18 | lunar_day | 1914-05-25 leap 乙巳 | 1914-05-26 leap 乙巳 |
| 1914-07-19 | lunar_day | 1914-05-26 leap 丙午 | 1914-05-27 leap 丙午 |
| 1914-07-20 | lunar_day | 1914-05-27 leap 丁未 | 1914-05-28 leap 丁未 |
| 1914-07-21 | lunar_day | 1914-05-28 leap 戊申 | 1914-05-29 leap 戊申 |
| 1914-07-22 | lunar_day | 1914-05-29 leap 己酉 | 1914-05-30 leap 己酉 |

## Review Notes

- Use this report to decide where official KASI fixtures are needed first.
- If KASI agrees with the checked-in table, promote those fields to hard reference cases.
- Do not use this report by itself to replace year/month/hour pillar logic.

## Regenerate

```powershell
cd apps/api
python tests/generate_lunar_reference_diff_report.py
```
