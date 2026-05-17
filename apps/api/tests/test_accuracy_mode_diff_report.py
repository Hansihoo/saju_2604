import unittest

from app.domain.saju.schemas import SajuPreviewRequest
from tests.generate_accuracy_mode_diff_report import (
    ACCURACY_MODES,
    build_markdown_report,
    collect_accuracy_mode_diff_data,
)


class AccuracyModeDiffReportTests(unittest.TestCase):
    def test_report_utility_collects_mode_diffs_without_changing_default(self) -> None:
        data = collect_accuracy_mode_diff_data(limit=3)

        self.assertEqual(ACCURACY_MODES, ("legacy", "standard_time", "mean_solar_time", "compare"))
        self.assertEqual(data["stats"]["total_case_count"], 3)
        self.assertIn("hour_pillar_change_count", data["stats"])
        self.assertIn("critical_flag_count", data["stats"])
        self.assertIn("flag_code_counts", data["stats"])
        self.assertIn("standard_time_changed_case_count", data["stats"])
        self.assertIn("first_luck_cycle_start_age_month_change_count", data["stats"])
        self.assertEqual(
            SajuPreviewRequest(
                calendar_type="solar",
                birth_date="2024-02-10",
                birth_time="10:30",
                is_birth_time_estimated=False,
                is_lunar_leap_month=False,
                gender="male",
                region_id="kr-seoul",
                debug=False,
            ).accuracy_mode,
            "legacy",
        )

    def test_markdown_report_keeps_manual_review_conclusion(self) -> None:
        data = collect_accuracy_mode_diff_data(limit=1)
        report = build_markdown_report(data)

        self.assertIn("Conclusion: Manual review required", report)
        self.assertIn("Default primary remains: `legacy`", report)
        self.assertIn("## Flag Counts", report)
        self.assertIn("## Regenerate", report)


if __name__ == "__main__":
    unittest.main()
