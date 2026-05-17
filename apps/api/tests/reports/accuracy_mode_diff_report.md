# Accuracy Mode Diff Report

- Generated at: `2026-05-17T06:50:18.358379+00:00`
- Conclusion: Manual review required. This report does not change the default primary mode.
- Default primary remains: `legacy`.
- Compared modes: `legacy`, `standard_time`, `mean_solar_time`, `compare`.

## Statistics

| Metric | Count |
| --- | ---: |
| Source cases prepared for comparison | 31 |
| Total compared cases | 31 |
| Unprocessed reference cases | 14 |
| Error cases | 0 |
| Standard-time mode changed cases | 7 |
| Mean-solar-time mode changed cases | 1 |
| Compare mode changed cases | 0 |
| Hour pillar changed | 5 |
| Day pillar changed | 1 |
| Month pillar changed | 0 |
| Year pillar changed | 0 |
| First luck-cycle start age changed | 3 |
| First luck-cycle start age month precision changed | 3 |
| Critical flag occurrences across all modes | 41 |

## Flag Counts

| Flag code | Count | Critical count |
| --- | ---: | ---: |
| ambiguous_local_time | 8 | 0 |
| birth_time_unknown | 4 | 0 |
| day_pillar_uncertain_due_to_unknown_time | 4 | 4 |
| leap_month_input_used | 24 | 0 |
| luck_cycle_start_age_changed | 12 | 0 |
| lunar_input_used | 32 | 0 |
| midnight_rule_changes_day_pillar | 12 | 12 |
| near_midnight | 52 | 0 |
| near_solar_term | 24 | 13 |
| primary_differs_from_candidate | 40 | 12 |
| standard_vs_mean_solar_changes_hour_pillar | 20 | 0 |
| timezone_dst_applied | 24 | 0 |

## Case Diffs

| Case | Source | Changed fields vs legacy | Legacy | Standard time | Mean solar time | Compare |
| --- | --- | --- | --- | --- | --- | --- |
| golden:kr_solar_regular | golden:saju_preview_golden_cases.json | - | 甲辰/丙寅/甲辰/己巳 luck=8y/94m_total flags=- | 甲辰/丙寅/甲辰/己巳 luck=8y/94m_total flags=- | 甲辰/丙寅/甲辰/己巳 luck=8y/94m_total flags=- | 甲辰/丙寅/甲辰/己巳 luck=8y/94m_total flags=- |
| golden:estimated_birth_time | golden:saju_preview_golden_cases.json | - | 甲戌/甲戌/壬申/None luck=Noney/Nonem_total flags=birth_time_unknown,day_pillar_uncertain_due_to_unknown_time | 甲戌/甲戌/壬申/None luck=Noney/Nonem_total flags=birth_time_unknown,day_pillar_uncertain_due_to_unknown_time | 甲戌/甲戌/壬申/None luck=Noney/Nonem_total flags=birth_time_unknown,day_pillar_uncertain_due_to_unknown_time | 甲戌/甲戌/壬申/None luck=Noney/Nonem_total flags=birth_time_unknown,day_pillar_uncertain_due_to_unknown_time |
| golden:late_zi_2330 | golden:saju_preview_golden_cases.json | day_pillar, hour_pillar | 戊辰/癸亥/庚辰/丙子 luck=5y/64m_total flags=near_midnight,standard_vs_mean_solar_changes_hour_pillar,midnight_rule_changes_day_pillar,primary_differs_from_candidate | 戊辰/癸亥/庚辰/丙子 luck=5y/64m_total flags=near_midnight,standard_vs_mean_solar_changes_hour_pillar,midnight_rule_changes_day_pillar,primary_differs_from_candidate | 戊辰/癸亥/己卯/乙亥 luck=5y/64m_total flags=near_midnight,standard_vs_mean_solar_changes_hour_pillar,midnight_rule_changes_day_pillar,primary_differs_from_candidate | 戊辰/癸亥/庚辰/丙子 luck=5y/64m_total flags=near_midnight,standard_vs_mean_solar_changes_hour_pillar,midnight_rule_changes_day_pillar,primary_differs_from_candidate |
| golden:early_0030 | golden:saju_preview_golden_cases.json | - | 戊辰/癸亥/庚辰/丙子 luck=5y/64m_total flags=near_midnight | 戊辰/癸亥/庚辰/丙子 luck=5y/64m_total flags=near_midnight | 戊辰/癸亥/庚辰/丙子 luck=5y/64m_total flags=near_midnight | 戊辰/癸亥/庚辰/丙子 luck=5y/64m_total flags=near_midnight |
| golden:seoul_longitude_correction | golden:saju_preview_golden_cases.json | hour_pillar | 丙子/甲午/丁亥/丁未 luck=5y/54m_total flags=standard_vs_mean_solar_changes_hour_pillar,primary_differs_from_candidate | 丙子/甲午/丁亥/戊申 luck=5y/54m_total flags=standard_vs_mean_solar_changes_hour_pillar,primary_differs_from_candidate | 丙子/甲午/丁亥/丁未 luck=5y/54m_total flags=standard_vs_mean_solar_changes_hour_pillar,primary_differs_from_candidate | 丙子/甲午/丁亥/丁未 luck=5y/54m_total flags=standard_vs_mean_solar_changes_hour_pillar,primary_differs_from_candidate |
| golden:korea_dst_1988 | golden:saju_preview_golden_cases.json | hour_pillar | 戊辰/丁巳/乙亥/辛巳 luck=5y/58m_total flags=timezone_dst_applied,standard_vs_mean_solar_changes_hour_pillar,primary_differs_from_candidate | 戊辰/丁巳/乙亥/壬午 luck=5y/58m_total flags=timezone_dst_applied,standard_vs_mean_solar_changes_hour_pillar,primary_differs_from_candidate | 戊辰/丁巳/乙亥/辛巳 luck=5y/58m_total flags=timezone_dst_applied,standard_vs_mean_solar_changes_hour_pillar,primary_differs_from_candidate | 戊辰/丁巳/乙亥/辛巳 luck=5y/58m_total flags=timezone_dst_applied,standard_vs_mean_solar_changes_hour_pillar,primary_differs_from_candidate |
| golden:lunar_input_regular | golden:saju_preview_golden_cases.json | - | 甲辰/丙寅/甲辰/己巳 luck=8y/94m_total flags=lunar_input_used | 甲辰/丙寅/甲辰/己巳 luck=8y/94m_total flags=lunar_input_used | 甲辰/丙寅/甲辰/己巳 luck=8y/94m_total flags=lunar_input_used | 甲辰/丙寅/甲辰/己巳 luck=8y/94m_total flags=lunar_input_used |
| golden:lunar_leap_month_input | golden:saju_preview_golden_cases.json | first_luck_cycle_start_age, first_luck_cycle_start_age_total_months | 癸卯/丙辰/癸巳/丁巳 luck=0y/0m_total flags=lunar_input_used,leap_month_input_used,near_solar_term,luck_cycle_start_age_changed,primary_differs_from_candidate | 癸卯/丙辰/癸巳/丁巳 luck=10y/121m_total flags=lunar_input_used,leap_month_input_used,near_solar_term,luck_cycle_start_age_changed,primary_differs_from_candidate | 癸卯/丙辰/癸巳/丁巳 luck=0y/0m_total flags=lunar_input_used,leap_month_input_used,near_solar_term,luck_cycle_start_age_changed,primary_differs_from_candidate | 癸卯/丙辰/癸巳/丁巳 luck=0y/0m_total flags=lunar_input_used,leap_month_input_used,near_solar_term,luck_cycle_start_age_changed,primary_differs_from_candidate |
| golden:solar_term_near_ipchun | golden:saju_preview_golden_cases.json | hour_pillar | 甲辰/丙寅/戊戌/庚申 luck=10y/116m_total flags=near_solar_term,standard_vs_mean_solar_changes_hour_pillar,primary_differs_from_candidate | 甲辰/丙寅/戊戌/辛酉 luck=10y/116m_total flags=near_solar_term,standard_vs_mean_solar_changes_hour_pillar,primary_differs_from_candidate | 甲辰/丙寅/戊戌/庚申 luck=10y/116m_total flags=near_solar_term,standard_vs_mean_solar_changes_hour_pillar,primary_differs_from_candidate | 甲辰/丙寅/戊戌/庚申 luck=10y/116m_total flags=near_solar_term,standard_vs_mean_solar_changes_hour_pillar,primary_differs_from_candidate |
| golden:overseas_timezone_new_york | golden:saju_preview_golden_cases.json | - | 庚午/癸未/辛巳/乙未 luck=3y/33m_total flags=leap_month_input_used | 庚午/癸未/辛巳/乙未 luck=3y/33m_total flags=leap_month_input_used | 庚午/癸未/辛巳/乙未 luck=3y/33m_total flags=leap_month_input_used | 庚午/癸未/辛巳/乙未 luck=3y/33m_total flags=leap_month_input_used |
| reference:kasi_solar_1914_06_23 | reference:lunar_solar_reference_cases.json | - | 甲寅/庚午/庚辰/丙子 luck=5y/60m_total flags=near_midnight | 甲寅/庚午/庚辰/丙子 luck=5y/60m_total flags=near_midnight | 甲寅/庚午/庚辰/丙子 luck=5y/60m_total flags=near_midnight | 甲寅/庚午/庚辰/丙子 luck=5y/60m_total flags=near_midnight |
| reference:kasi_lunar_1914_05_30_to_solar | reference:lunar_solar_reference_cases.json | - | 甲寅/庚午/庚辰/丙子 luck=5y/60m_total flags=near_midnight,lunar_input_used | 甲寅/庚午/庚辰/丙子 luck=5y/60m_total flags=near_midnight,lunar_input_used | 甲寅/庚午/庚辰/丙子 luck=5y/60m_total flags=near_midnight,lunar_input_used | 甲寅/庚午/庚辰/丙子 luck=5y/60m_total flags=near_midnight,lunar_input_used |
| reference:kasi_lunar_leap_1914_05_01_to_solar | reference:lunar_solar_reference_cases.json | - | 甲寅/庚午/辛巳/戊子 luck=5y/56m_total flags=near_midnight,lunar_input_used,leap_month_input_used | 甲寅/庚午/辛巳/戊子 luck=5y/56m_total flags=near_midnight,lunar_input_used,leap_month_input_used | 甲寅/庚午/辛巳/戊子 luck=5y/56m_total flags=near_midnight,lunar_input_used,leap_month_input_used | 甲寅/庚午/辛巳/戊子 luck=5y/56m_total flags=near_midnight,lunar_input_used,leap_month_input_used |
| reference:kasi_lunar_leap_1914_05_29_to_solar | reference:lunar_solar_reference_cases.json | - | 甲寅/辛未/己酉/甲子 luck=6y/70m_total flags=near_midnight,lunar_input_used,leap_month_input_used | 甲寅/辛未/己酉/甲子 luck=6y/70m_total flags=near_midnight,lunar_input_used,leap_month_input_used | 甲寅/辛未/己酉/甲子 luck=6y/70m_total flags=near_midnight,lunar_input_used,leap_month_input_used | 甲寅/辛未/己酉/甲子 luck=6y/70m_total flags=near_midnight,lunar_input_used,leap_month_input_used |
| reference:kasi_solar_1900_01_01_table_start | reference:lunar_solar_reference_cases.json | - | 己亥/丙子/甲戌/甲子 luck=8y/96m_total flags=near_midnight,timezone_dst_applied | 己亥/丙子/甲戌/甲子 luck=8y/96m_total flags=near_midnight,timezone_dst_applied | 己亥/丙子/甲戌/甲子 luck=8y/96m_total flags=near_midnight,timezone_dst_applied | 己亥/丙子/甲戌/甲子 luck=8y/96m_total flags=near_midnight,timezone_dst_applied |
| reference:kasi_solar_1956_12_31 | reference:lunar_solar_reference_cases.json | - | 丙申/庚子/壬申/庚子 luck=2y/23m_total flags=near_midnight,timezone_dst_applied | 丙申/庚子/壬申/庚子 luck=2y/23m_total flags=near_midnight,timezone_dst_applied | 丙申/庚子/壬申/庚子 luck=2y/23m_total flags=near_midnight,timezone_dst_applied | 丙申/庚子/壬申/庚子 luck=2y/23m_total flags=near_midnight,timezone_dst_applied |
| reference:kasi_lunar_leap_2023_02_15 | reference:lunar_solar_reference_cases.json | first_luck_cycle_start_age, first_luck_cycle_start_age_total_months | 癸卯/丙辰/癸巳/丁巳 luck=10y/118m_total flags=lunar_input_used,leap_month_input_used,near_solar_term,luck_cycle_start_age_changed,primary_differs_from_candidate | 癸卯/丙辰/癸巳/丁巳 luck=0y/0m_total flags=lunar_input_used,leap_month_input_used,near_solar_term,luck_cycle_start_age_changed,primary_differs_from_candidate | 癸卯/丙辰/癸巳/丁巳 luck=10y/118m_total flags=lunar_input_used,leap_month_input_used,near_solar_term,luck_cycle_start_age_changed,primary_differs_from_candidate | 癸卯/丙辰/癸巳/丁巳 luck=10y/118m_total flags=lunar_input_used,leap_month_input_used,near_solar_term,luck_cycle_start_age_changed,primary_differs_from_candidate |
| reference:kasi_lunar_2024_01_01_to_solar | reference:lunar_solar_reference_cases.json | - | 甲辰/丙寅/甲辰/己巳 luck=8y/94m_total flags=lunar_input_used | 甲辰/丙寅/甲辰/己巳 luck=8y/94m_total flags=lunar_input_used | 甲辰/丙寅/甲辰/己巳 luck=8y/94m_total flags=lunar_input_used | 甲辰/丙寅/甲辰/己巳 luck=8y/94m_total flags=lunar_input_used |
| reference:kasi_lunar_leap_2023_02_15_to_solar | reference:lunar_solar_reference_cases.json | first_luck_cycle_start_age, first_luck_cycle_start_age_total_months | 癸卯/丙辰/癸巳/丁巳 luck=10y/118m_total flags=lunar_input_used,leap_month_input_used,near_solar_term,luck_cycle_start_age_changed,primary_differs_from_candidate | 癸卯/丙辰/癸巳/丁巳 luck=0y/0m_total flags=lunar_input_used,leap_month_input_used,near_solar_term,luck_cycle_start_age_changed,primary_differs_from_candidate | 癸卯/丙辰/癸巳/丁巳 luck=10y/118m_total flags=lunar_input_used,leap_month_input_used,near_solar_term,luck_cycle_start_age_changed,primary_differs_from_candidate | 癸卯/丙辰/癸巳/丁巳 luck=10y/118m_total flags=lunar_input_used,leap_month_input_used,near_solar_term,luck_cycle_start_age_changed,primary_differs_from_candidate |
| reference:kasi_solar_1988_05_20_to_lunar | reference:lunar_solar_reference_cases.json | hour_pillar | 戊辰/丁巳/乙亥/辛巳 luck=5y/64m_total flags=timezone_dst_applied,standard_vs_mean_solar_changes_hour_pillar,primary_differs_from_candidate | 戊辰/丁巳/乙亥/壬午 luck=5y/64m_total flags=timezone_dst_applied,standard_vs_mean_solar_changes_hour_pillar,primary_differs_from_candidate | 戊辰/丁巳/乙亥/辛巳 luck=5y/64m_total flags=timezone_dst_applied,standard_vs_mean_solar_changes_hour_pillar,primary_differs_from_candidate | 戊辰/丁巳/乙亥/辛巳 luck=5y/64m_total flags=timezone_dst_applied,standard_vs_mean_solar_changes_hour_pillar,primary_differs_from_candidate |
| reference:kasi_solar_2050_12_31_table_end | reference:lunar_solar_reference_cases.json | - | 庚午/戊子/乙酉/丙子 luck=2y/22m_total flags=near_midnight | 庚午/戊子/乙酉/丙子 luck=2y/22m_total flags=near_midnight | 庚午/戊子/乙酉/丙子 luck=2y/22m_total flags=near_midnight | 庚午/戊子/乙酉/丙子 luck=2y/22m_total flags=near_midnight |
| reference:zoneinfo_asia_seoul_regular_1994 | reference:timezone_dst_reference_cases.json | - | 甲戌/甲戌/壬申/甲辰 luck=8y/101m_total flags=- | 甲戌/甲戌/壬申/甲辰 luck=8y/101m_total flags=- | 甲戌/甲戌/壬申/甲辰 luck=8y/101m_total flags=- | 甲戌/甲戌/壬申/甲辰 luck=8y/101m_total flags=- |
| reference:zoneinfo_asia_seoul_dst_1988 | reference:timezone_dst_reference_cases.json | - | 戊辰/丁巳/乙亥/壬午 luck=5y/64m_total flags=timezone_dst_applied | 戊辰/丁巳/乙亥/壬午 luck=5y/64m_total flags=timezone_dst_applied | 戊辰/丁巳/乙亥/壬午 luck=5y/64m_total flags=timezone_dst_applied | 戊辰/丁巳/乙亥/壬午 luck=5y/64m_total flags=timezone_dst_applied |
| reference:zoneinfo_new_york_ambiguous_fall_2024 | reference:timezone_dst_reference_cases.json | - | 甲辰/甲戌/辛未/己丑 luck=1y/14m_total flags=ambiguous_local_time | 甲辰/甲戌/辛未/己丑 luck=1y/14m_total flags=ambiguous_local_time | 甲辰/甲戌/辛未/己丑 luck=1y/14m_total flags=ambiguous_local_time | 甲辰/甲戌/辛未/己丑 luck=1y/14m_total flags=ambiguous_local_time |
| reference:zoneinfo_asia_seoul_dst_end_before_1988 | reference:timezone_dst_reference_cases.json | - | 戊辰/壬戌/丁酉/庚子 luck=10y/116m_total flags=near_midnight,timezone_dst_applied,near_solar_term | 戊辰/壬戌/丁酉/庚子 luck=10y/116m_total flags=near_midnight,timezone_dst_applied,near_solar_term | 戊辰/壬戌/丁酉/庚子 luck=10y/116m_total flags=near_midnight,timezone_dst_applied,near_solar_term | 戊辰/壬戌/丁酉/庚子 luck=10y/116m_total flags=near_midnight,timezone_dst_applied,near_solar_term |
| reference:zoneinfo_asia_seoul_after_dst_end_1988 | reference:timezone_dst_reference_cases.json | - | 戊辰/壬戌/丁酉/壬寅 luck=10y/116m_total flags=near_solar_term | 戊辰/壬戌/丁酉/壬寅 luck=10y/116m_total flags=near_solar_term | 戊辰/壬戌/丁酉/壬寅 luck=10y/116m_total flags=near_solar_term | 戊辰/壬戌/丁酉/壬寅 luck=10y/116m_total flags=near_solar_term |
| reference:zoneinfo_berlin_ambiguous_fall_2024 | reference:timezone_dst_reference_cases.json | - | 甲辰/甲戌/甲子/乙丑 luck=4y/42m_total flags=ambiguous_local_time | 甲辰/甲戌/甲子/乙丑 luck=4y/42m_total flags=ambiguous_local_time | 甲辰/甲戌/甲子/乙丑 luck=4y/42m_total flags=ambiguous_local_time | 甲辰/甲戌/甲子/乙丑 luck=4y/42m_total flags=ambiguous_local_time |
| reference:sect1_before_late_zi_1988_2259 | reference:midnight_boundary_cases.json | - | 戊辰/癸亥/己卯/乙亥 luck=5y/64m_total flags=- | 戊辰/癸亥/己卯/乙亥 luck=5y/64m_total flags=- | 戊辰/癸亥/己卯/乙亥 luck=5y/64m_total flags=- | 戊辰/癸亥/己卯/乙亥 luck=5y/64m_total flags=- |
| reference:sect1_at_late_zi_boundary_1988_2300 | reference:midnight_boundary_cases.json | - | 戊辰/癸亥/庚辰/丙子 luck=5y/64m_total flags=near_midnight,midnight_rule_changes_day_pillar,primary_differs_from_candidate | 戊辰/癸亥/庚辰/丙子 luck=5y/64m_total flags=near_midnight,midnight_rule_changes_day_pillar,primary_differs_from_candidate | 戊辰/癸亥/庚辰/丙子 luck=5y/64m_total flags=near_midnight,midnight_rule_changes_day_pillar,primary_differs_from_candidate | 戊辰/癸亥/庚辰/丙子 luck=5y/64m_total flags=near_midnight,midnight_rule_changes_day_pillar,primary_differs_from_candidate |
| reference:sect1_after_late_zi_1988_2330 | reference:midnight_boundary_cases.json | - | 戊辰/癸亥/庚辰/丙子 luck=5y/64m_total flags=near_midnight,midnight_rule_changes_day_pillar,primary_differs_from_candidate | 戊辰/癸亥/庚辰/丙子 luck=5y/64m_total flags=near_midnight,midnight_rule_changes_day_pillar,primary_differs_from_candidate | 戊辰/癸亥/庚辰/丙子 luck=5y/64m_total flags=near_midnight,midnight_rule_changes_day_pillar,primary_differs_from_candidate | 戊辰/癸亥/庚辰/丙子 luck=5y/64m_total flags=near_midnight,midnight_rule_changes_day_pillar,primary_differs_from_candidate |
| reference:sect1_after_civil_midnight_1988_0030 | reference:midnight_boundary_cases.json | - | 戊辰/癸亥/庚辰/丙子 luck=5y/64m_total flags=near_midnight | 戊辰/癸亥/庚辰/丙子 luck=5y/64m_total flags=near_midnight | 戊辰/癸亥/庚辰/丙子 luck=5y/64m_total flags=near_midnight | 戊辰/癸亥/庚辰/丙子 luck=5y/64m_total flags=near_midnight |

## Unprocessed Reference Cases

| Case | Source | Reason |
| --- | --- | --- |
| reference:zoneinfo_new_york_nonexistent_spring_2024 | reference:timezone_dst_reference_cases.json | nonexistent local time hard reference is not a preview-comparable birth chart |
| reference:zoneinfo_berlin_nonexistent_spring_2024 | reference:timezone_dst_reference_cases.json | nonexistent local time hard reference is not a preview-comparable birth chart |
| reference:kasi_2018_ipchun_boundary | reference:solar_term_reference_cases.json | solar-term reference lacks a concrete birth_time/input_datetime for accuracy-mode preview comparison |
| reference:kasi_2019_ipchun_boundary | reference:solar_term_reference_cases.json | solar-term reference lacks a concrete birth_time/input_datetime for accuracy-mode preview comparison |
| reference:kasi_2020_ipchun_boundary | reference:solar_term_reference_cases.json | solar-term reference lacks a concrete birth_time/input_datetime for accuracy-mode preview comparison |
| reference:kasi_2020_gyeongchip_boundary | reference:solar_term_reference_cases.json | solar-term reference lacks a concrete birth_time/input_datetime for accuracy-mode preview comparison |
| reference:kasi_2020_cheongmyeong_boundary | reference:solar_term_reference_cases.json | solar-term reference lacks a concrete birth_time/input_datetime for accuracy-mode preview comparison |
| reference:kasi_2020_ipha_boundary | reference:solar_term_reference_cases.json | solar-term reference lacks a concrete birth_time/input_datetime for accuracy-mode preview comparison |
| reference:kasi_2024_ipchun_boundary | reference:solar_term_reference_cases.json | solar-term reference lacks a concrete birth_time/input_datetime for accuracy-mode preview comparison |
| reference:kasi_2024_gyeongchip_boundary | reference:solar_term_reference_cases.json | solar-term reference lacks a concrete birth_time/input_datetime for accuracy-mode preview comparison |
| reference:kasi_2024_cheongmyeong_boundary | reference:solar_term_reference_cases.json | solar-term reference lacks a concrete birth_time/input_datetime for accuracy-mode preview comparison |
| reference:kasi_2024_ipha_boundary | reference:solar_term_reference_cases.json | solar-term reference lacks a concrete birth_time/input_datetime for accuracy-mode preview comparison |
| reference:independent_ephemeris_2024_ipchun_minus_30m | reference:solar_term_reference_cases.json | solar-term reference lacks a concrete birth_time/input_datetime for accuracy-mode preview comparison |
| reference:independent_ephemeris_2024_gyeongchip_plus_30m | reference:solar_term_reference_cases.json | solar-term reference lacks a concrete birth_time/input_datetime for accuracy-mode preview comparison |

## Errors

None.

## Regenerate

```powershell
cd apps/api
python tests/generate_accuracy_mode_diff_report.py
```
