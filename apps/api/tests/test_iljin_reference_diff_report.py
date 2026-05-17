import unittest

from tests.generate_iljin_reference_diff_report import (
    build_markdown_report,
    collect_iljin_reference_diff_data,
)


class IljinReferenceDiffReportTests(unittest.TestCase):
    def test_small_range_matches_kasi_iljin_values(self) -> None:
        data = collect_iljin_reference_diff_data(
            start_date="2024-02-09",
            end_date="2024-02-11",
        )

        self.assertEqual(data["total_compared"], 3)
        self.assertEqual(data["mismatch_count"], 0)
        self.assertEqual(data["mismatch_year_counts"], {})

    def test_markdown_report_documents_table_backed_source(self) -> None:
        data = collect_iljin_reference_diff_data(
            start_date="2024-02-10",
            end_date="2024-02-10",
        )
        report = build_markdown_report(data)

        self.assertIn("# KASI Iljin Reference Diff Report", report)
        self.assertIn("table-backed primary day-pillar gan-zhi source", report)
        self.assertIn("## Regenerate", report)


if __name__ == "__main__":
    unittest.main()
