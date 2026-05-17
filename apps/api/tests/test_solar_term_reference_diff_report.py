import unittest

from tests.generate_solar_term_reference_diff_report import (
    build_markdown_report,
    collect_solar_term_reference_diff_data,
)


class SolarTermReferenceDiffReportTests(unittest.TestCase):
    def test_2024_verified_rows_show_lunar_python_timestamp_offset(self) -> None:
        data = collect_solar_term_reference_diff_data(
            start_year=2024,
            end_year=2024,
            jeolgi_only=True,
        )

        self.assertEqual(data["total_compared"], 11)
        self.assertGreaterEqual(data["max_abs_delta_seconds"], 3500)
        within_two_hours = (
            data["delta_bucket_counts"].get("<=1m", 0)
            + data["delta_bucket_counts"].get("<=30m", 0)
            + data["delta_bucket_counts"].get("<=1h", 0)
            + data["delta_bucket_counts"].get("<=2h", 0)
        )
        self.assertGreaterEqual(within_two_hours, 11)

    def test_markdown_report_is_diagnostic_only(self) -> None:
        data = collect_solar_term_reference_diff_data(
            start_year=2024,
            end_year=2024,
            jeolgi_only=True,
        )
        report = build_markdown_report(data)

        self.assertIn("# Solar-Term Reference Diff Report", report)
        self.assertIn("diagnostic only", report)
        self.assertIn("does not change primary pillars", report)
        self.assertIn("## Regenerate", report)


if __name__ == "__main__":
    unittest.main()
