import unittest

from tests.generate_canonical_year_month_diff_report import (
    build_markdown_report,
    collect_canonical_year_month_diff_data,
)


class CanonicalYearMonthDiffReportTests(unittest.TestCase):
    def test_report_collects_shadow_diffs_without_primary_application(self) -> None:
        data = collect_canonical_year_month_diff_data(limit=3)

        self.assertEqual(data["stats"]["total_case_count"], 3)
        self.assertIn("year_pillar_changed_count", data["stats"])
        self.assertIn("month_pillar_changed_count", data["stats"])
        self.assertEqual(data["stats"]["applied_to_primary_count"], 0)

    def test_markdown_report_keeps_manual_review_conclusion(self) -> None:
        data = collect_canonical_year_month_diff_data(limit=1)
        report = build_markdown_report(data)

        self.assertIn("Conclusion: Manual review required", report)
        self.assertIn("default primary remains legacy", report)
        self.assertIn("## Regenerate", report)


if __name__ == "__main__":
    unittest.main()
