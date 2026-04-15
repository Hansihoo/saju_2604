import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.domain.saju.golden import (
    GoldenKnownAnswerCase,
    compare_golden_snapshots,
    derive_display_minutes_from_longitude,
)
from app.domain.saju.services.build_golden_snapshot import build_actual_golden_snapshot
from app.domain.saju.services.parse_golden_answer_text import load_golden_answer_text
from app.tools.compare_golden_cases import compare_golden_cases


SOURCE_DIR = Path(__file__).parent / "golden_cases" / "source"
EXPECTED_DIR = Path(__file__).parent / "golden_cases" / "expected"


class GoldenCaseToolTests(unittest.TestCase):
    def test_parses_source_answer_into_canonical_case(self) -> None:
        case = load_golden_answer_text(
            SOURCE_DIR / "pororo.txt",
            case_id="pororo",
            source_name="뽀로로",
        )

        self.assertEqual(case.input.birth_date, "1997-02-03")
        self.assertEqual(case.input.birth_time, "17:00")
        self.assertEqual(case.input.gender, "female")
        self.assertEqual(case.expected.basic_info.birth_place, "서울특별시")
        self.assertEqual(case.expected.pillar_table["time"].gan_zhi, "병신")
        self.assertEqual(case.expected.luck_cycle_header.reference_pillar, "신축")
        self.assertEqual(case.expected.luck_cycle_header.start_age, 10)
        self.assertEqual(case.expected.luck_cycles[0].gan_zhi, "경자")

        aru_case = load_golden_answer_text(
            SOURCE_DIR / "aru.txt",
            case_id="aru",
            source_name="아르",
        )
        special_star_map = {star.key: star for star in aru_case.expected.special_stars}
        self.assertEqual(sorted(special_star_map.keys()), ["cheoneul-gwiin", "gwaegang", "yangin"])
        self.assertTrue(special_star_map["gwaegang"].active)
        self.assertEqual(special_star_map["gwaegang"].matched_pillars, ["day"])

    def test_builds_actual_golden_snapshot(self) -> None:
        case = GoldenKnownAnswerCase.model_validate_json(
            (EXPECTED_DIR / "pororo.json").read_text(encoding="utf-8")
        )

        actual = build_actual_golden_snapshot(case_input=case.input)

        self.assertRegex(actual.basic_info.corrected_datetime, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
        self.assertEqual(actual.basic_info.birth_place, "서울특별시")
        self.assertEqual(actual.pillar_table["year"].gan_zhi, "병자")
        self.assertEqual(actual.luck_cycle_header.reference_pillar, "신축")
        self.assertGreater(len(actual.luck_cycles), 0)
        special_star_map = {star.key: star for star in actual.special_stars}
        self.assertEqual(sorted(special_star_map.keys()), ["cheoneul-gwiin", "gwaegang", "yangin"])
        self.assertIsInstance(special_star_map["gwaegang"].matched_pillars, list)

    def test_reports_mismatch_paths_in_structured_form(self) -> None:
        case = GoldenKnownAnswerCase.model_validate_json(
            (EXPECTED_DIR / "pororo.json").read_text(encoding="utf-8")
        )
        actual = case.expected.model_copy(deep=True)
        actual.basic_info.corrected_datetime = "1997-02-03 16:29"

        report = compare_golden_snapshots(case=case, actual=actual)

        self.assertFalse(report.success)
        self.assertEqual(report.mismatch_count, 1)
        self.assertEqual(report.mismatches[0].path, "basic_info.corrected_datetime")

    def test_derives_display_minutes_from_longitude_using_answer_sheet_rule(self) -> None:
        self.assertEqual(derive_display_minutes_from_longitude(126.991824), -32)
        self.assertEqual(derive_display_minutes_from_longitude(127.258722), -31)
        self.assertEqual(derive_display_minutes_from_longitude(128.140959), -28)

    def test_compare_tool_writes_summary_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            report_dir = Path(temp_dir) / "reports"
            summary_file = report_dir / "summary.json"

            summary = compare_golden_cases(
                expected_dir=EXPECTED_DIR,
                report_dir=report_dir,
                summary_file=summary_file,
            )

            self.assertTrue(summary_file.exists())
            self.assertEqual(summary["total_cases"], 7)
            self.assertIn("cases", summary)
            self.assertIn("mismatch_fields", summary)
            self.assertIn("diagnosis_counts", summary)
            self.assertIn("case_status_counts", summary)
            self.assertEqual(summary["case_status_counts"], {"match": 7})
            self.assertEqual(summary["total_mismatches"], 0)
            self.assertEqual(summary["mismatch_fields"], {})

    def test_compare_tool_confirms_current_golden_alignment(self) -> None:
        with TemporaryDirectory() as temp_dir:
            report_dir = Path(temp_dir) / "reports"
            summary_file = report_dir / "summary.json"

            summary = compare_golden_cases(
                expected_dir=EXPECTED_DIR,
                report_dir=report_dir,
                summary_file=summary_file,
            )

            aru_summary = next(case for case in summary["cases"] if case["case_id"] == "aru")
            gomaebi_summary = next(case for case in summary["cases"] if case["case_id"] == "gomaebi")
            pororo_summary = next(case for case in summary["cases"] if case["case_id"] == "pororo")

            self.assertTrue(aru_summary["success"])
            self.assertEqual(aru_summary["case_status"], "match")
            self.assertEqual(aru_summary["diagnosis_tags"], [])
            self.assertEqual(
                aru_summary["diagnostic_context"]["actual_month_boundary_datetime"],
                "1988-12-07 06:34:28",
            )
            self.assertEqual(
                aru_summary["diagnostic_context"]["candidate_start_ages"]["round_precise"],
                5,
            )

            self.assertTrue(gomaebi_summary["success"])
            self.assertEqual(gomaebi_summary["case_status"], "match")
            self.assertEqual(gomaebi_summary["diagnosis_tags"], [])
            self.assertEqual(
                gomaebi_summary["diagnostic_context"]["actual_month_boundary_datetime"],
                "1989-01-05 17:45:55",
            )
            self.assertTrue(
                9.4
                < gomaebi_summary["diagnostic_context"]["actual_precise_start_age_years"]
                < 9.5
            )
            self.assertEqual(
                gomaebi_summary["diagnostic_context"]["candidate_start_ages"],
                {
                    "current_day_count_r2": 9,
                    "exclude_both_day_count_r2": 9,
                    "floor_exact": 9,
                    "ceil_exact": 10,
                    "round_exact": 10,
                    "floor_precise": 9,
                    "ceil_precise": 10,
                    "round_precise": 9,
                },
            )
            self.assertEqual(
                gomaebi_summary["diagnostic_context"]["matched_expected_start_age_rules"],
                [
                    "current_day_count_r2",
                    "exclude_both_day_count_r2",
                    "floor_exact",
                    "floor_precise",
                    "round_precise",
                ],
            )

            self.assertTrue(pororo_summary["success"])
            self.assertEqual(pororo_summary["case_status"], "match")
            self.assertEqual(pororo_summary["diagnosis_tags"], [])
            self.assertEqual(
                pororo_summary["diagnostic_context"]["candidate_start_ages"]["round_precise"],
                10,
            )

    def test_known_answer_cases_match_all_four_pillars(self) -> None:
        mismatches = []

        for expected_path in sorted(EXPECTED_DIR.glob("*.json")):
            case = GoldenKnownAnswerCase.model_validate_json(
                expected_path.read_text(encoding="utf-8")
            )
            actual = build_actual_golden_snapshot(case_input=case.input)
            for pillar_key in ["year", "month", "day", "time"]:
                expected_gan_zhi = case.expected.pillar_table[pillar_key].gan_zhi
                actual_gan_zhi = actual.pillar_table[pillar_key].gan_zhi
                if expected_gan_zhi != actual_gan_zhi:
                    mismatches.append(
                        {
                            "case_id": case.input.case_id,
                            "pillar": pillar_key,
                            "expected": expected_gan_zhi,
                            "actual": actual_gan_zhi,
                        }
                    )

        self.assertEqual(mismatches, [])

    def test_aru_display_values_follow_answer_sheet_convention(self) -> None:
        case = GoldenKnownAnswerCase.model_validate_json(
            (EXPECTED_DIR / "aru.json").read_text(encoding="utf-8")
        )

        actual = build_actual_golden_snapshot(case_input=case.input)

        self.assertEqual(actual.basic_info.regional_time_offset_minutes, -28)
        self.assertEqual(actual.basic_info.corrected_datetime, "1988-11-20 23:02")


if __name__ == "__main__":
    unittest.main()
