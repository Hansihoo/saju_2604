import unittest

from tests.generate_lunar_reference_diff_report import (
    build_markdown_report,
    collect_lunar_reference_diff_data,
)


class LunarReferenceDiffReportTests(unittest.TestCase):
    def test_report_detects_known_1914_lunar_python_calendar_gap(self) -> None:
        data = collect_lunar_reference_diff_data(
            start_date="1914-06-20",
            end_date="1914-06-25",
        )

        self.assertEqual(data["total_compared"], 6)
        self.assertGreaterEqual(data["mismatch_count"], 1)
        self.assertGreaterEqual(data["field_mismatch_counts"]["lunar_day"], 1)
        self.assertNotIn("day_ganzhi_hanja", data["field_mismatch_counts"])
        self.assertTrue(
            any(item["start"] == "1914-06-23" for item in data["mismatch_ranges"])
        )

    def test_markdown_report_is_diagnostic_only(self) -> None:
        data = collect_lunar_reference_diff_data(
            start_date="1956-12-30",
            end_date="1956-12-31",
        )
        report = build_markdown_report(data)

        self.assertIn("# Lunar Reference Diff Report", report)
        self.assertIn("diagnostic only", report)
        self.assertIn("does not change production primary pillars", report)
        self.assertIn("## Regenerate", report)


if __name__ == "__main__":
    unittest.main()
