import json
import unittest
from pathlib import Path

from app.tools import build_extended_solar_term_reference_table as extended_terms


ROWS_PATH = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "domain"
    / "saju"
    / "data"
    / "solar_terms_reference"
    / "solar_terms_extended_1946_2027.jsonl"
)


def _load_rows():
    return [json.loads(line) for line in ROWS_PATH.read_text(encoding="utf-8").splitlines()]


class ExtendedSolarTermReferenceTableTests(unittest.TestCase):
    def test_checked_in_extended_table_integrity(self) -> None:
        result = extended_terms.check_table()

        self.assertEqual(result["table_id"], "solar_terms_extended_1946_2027")
        self.assertEqual(result["row_count"], 1966)
        self.assertTrue(result["hash_matches_metadata"])
        self.assertEqual(result["partial_years"], [1946])
        self.assertEqual(result["missing_terms_by_year"], {"1946": ["sohan", "daehan"]})
        self.assertEqual(result["complete_years"][0], 1947)
        self.assertEqual(result["complete_years"][-1], 2027)

    def test_extended_table_has_age_80_boundary_values(self) -> None:
        rows = {
            (row["year"], row["term_id"]): row
            for row in _load_rows()
        }

        self.assertNotIn((1946, "sohan"), rows)
        self.assertNotIn((1946, "daehan"), rows)
        self.assertEqual(rows[(1946, "ipchun")]["solar_term_datetime"], "1946-02-04T19:04:00+09:00")
        self.assertEqual(rows[(1947, "sohan")]["solar_term_datetime"], "1947-01-06T13:07:00+09:00")
        self.assertEqual(rows[(1950, "ipchun")]["solar_term_datetime"], "1950-02-04T18:22:00+09:00")

    def test_extended_table_overrides_known_2011_archive_misalignment(self) -> None:
        rows = {
            (row["year"], row["term_id"]): row
            for row in _load_rows()
        }

        self.assertEqual(rows[(2011, "ipchun")]["solar_term_datetime"], "2011-02-04T13:33:00+09:00")
        self.assertEqual(rows[(2011, "ipchun")]["source"]["source_method"], "bebeyam_html_transcription")
        self.assertEqual(
            rows[(2011, "ipchun")]["source"]["validation"]["comparison_source"],
            "uncle_tools_nasa_de441",
        )

    def test_official_common_rows_are_preserved_after_2012(self) -> None:
        rows = {
            (row["year"], row["term_id"]): row
            for row in _load_rows()
        }

        self.assertEqual(rows[(2015, "haji")]["solar_term_datetime"], "2015-06-22T01:38:00+09:00")
        self.assertEqual(rows[(2015, "haji")]["source_role"], "official_reference_table")
        self.assertEqual(rows[(2024, "ipchun")]["solar_term_datetime"], "2024-02-04T17:27:00+09:00")
        self.assertEqual(rows[(2024, "ipchun")]["source_role"], "official_reference_table")


if __name__ == "__main__":
    unittest.main()
