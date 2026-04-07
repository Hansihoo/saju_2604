import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.domain.saju.golden import GoldenKnownAnswerCase, compare_golden_snapshots
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
            source_name="\ubf40\ub85c\ub85c",
        )

        self.assertEqual(case.input.birth_date, "1997-02-03")
        self.assertEqual(case.input.birth_time, "17:00")
        self.assertEqual(case.input.gender, "female")
        self.assertEqual(case.expected.basic_info.birth_place, "\uc11c\uc6b8\ud2b9\ubcc4\uc2dc")
        self.assertEqual(case.expected.pillar_table["time"].gan_zhi, "\ubcd1\uc2e0")
        self.assertEqual(case.expected.luck_cycles[0].gan_zhi, "\uacbd\uc790")

    def test_builds_actual_golden_snapshot(self) -> None:
        case = GoldenKnownAnswerCase.model_validate_json(
            (EXPECTED_DIR / "pororo.json").read_text(encoding="utf-8")
        )

        actual = build_actual_golden_snapshot(case_input=case.input)

        self.assertRegex(actual.basic_info.corrected_datetime, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
        self.assertEqual(actual.basic_info.birth_place, "\uc11c\uc6b8\ud2b9\ubcc4\uc2dc")
        self.assertEqual(actual.pillar_table["year"].gan_zhi, "\ubcd1\uc790")
        self.assertGreater(len(actual.luck_cycles), 0)

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
            self.assertEqual(summary["total_cases"], 5)
            self.assertIn("cases", summary)
            self.assertIn("mismatch_fields", summary)
            self.assertIn("diagnosis_counts", summary)
            self.assertTrue(
                any(key.startswith("luck_cycles") for key in summary["mismatch_fields"])
            )
            self.assertTrue(
                any(
                    "diagnosis_tags" in case_summary and "recommended_actions" in case_summary
                    for case_summary in summary["cases"]
                )
            )

    def test_compare_tool_flags_expected_luck_cycle_anomalies(self) -> None:
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

            self.assertIn("luck_cycle_branch_only_mismatch", aru_summary["diagnosis_tags"])
            self.assertIn("expected_luck_cycle_unparseable", aru_summary["diagnosis_tags"])
            self.assertEqual(
                aru_summary["diagnostic_context"]["invalid_expected_luck_cycles"],
                ["갑사", "을자", "병묘", "기진"],
            )
            self.assertEqual(aru_summary["diagnostic_context"]["luck_cycle_stem_mismatch_count"], 0)
            self.assertEqual(aru_summary["diagnostic_context"]["luck_cycle_branch_mismatch_count"], 10)
            self.assertIn("expected_luck_cycle_unparseable", gomaebi_summary["diagnosis_tags"])
            self.assertIn("luck_cycle_branch_only_mismatch", gomaebi_summary["diagnosis_tags"])
            self.assertEqual(
                gomaebi_summary["diagnostic_context"]["invalid_expected_luck_cycles"],
                ["병사", "정인", "무묘", "기진", "경사", "신오", "임미", "계신", "갑유"],
            )
            self.assertEqual(gomaebi_summary["diagnostic_context"]["luck_cycle_stem_mismatch_count"], 0)
            self.assertIn("expected_luck_cycle_tail_anomaly", pororo_summary["diagnosis_tags"])
            self.assertIn("luck_cycle_branch_only_mismatch", pororo_summary["diagnosis_tags"])
            self.assertEqual(
                pororo_summary["diagnostic_context"]["invalid_expected_luck_cycles"],
                [],
            )
            self.assertEqual(pororo_summary["diagnostic_context"]["luck_cycle_stem_mismatch_count"], 0)
            self.assertEqual(pororo_summary["diagnostic_context"]["luck_cycle_branch_mismatch_count"], 1)

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


if __name__ == "__main__":
    unittest.main()
