import json
import tempfile
import unittest
from pathlib import Path

from app.tools import build_solar_term_reference_table as solar_terms


ROWS_PATH = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "domain"
    / "saju"
    / "data"
    / "solar_terms_reference"
    / "kasi_solar_terms_common_years.jsonl"
)


def _load_rows():
    return [json.loads(line) for line in ROWS_PATH.read_text(encoding="utf-8").splitlines()]


def _fake_source_text(year: int) -> str:
    lines = ["24기", "명칭    월   일    시   분"]
    for _term_id, name, index, _term_type in solar_terms.SOLAR_TERMS:
        month = (index // 2) + 1
        day = min(index + 1, 28)
        lines.append(f"{name} {month:2d} {day:2d} {index % 24:2d} {index % 60:2d}")
    return "\n".join(lines)


class SolarTermReferenceTableTests(unittest.TestCase):
    def test_checked_in_solar_term_table_integrity(self) -> None:
        result = solar_terms.check_table()

        self.assertEqual(result["table_id"], "kasi_solar_terms_common_years")
        self.assertEqual(result["row_count"], 408)
        self.assertTrue(result["hash_matches_metadata"])
        self.assertEqual(
            result["completed_years"],
            [2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026, 2027],
        )

    def test_checked_in_table_contains_kasi_2024_boundary_values(self) -> None:
        rows = {
            (row["year"], row["term_id"]): row
            for row in _load_rows()
        }

        self.assertEqual(rows[(2017, "ipchun")]["solar_term_datetime"], "2017-02-04T00:34:00+09:00")
        self.assertEqual(rows[(2018, "ipchun")]["solar_term_datetime"], "2018-02-04T06:28:00+09:00")
        self.assertEqual(rows[(2019, "ipchun")]["solar_term_datetime"], "2019-02-04T12:14:00+09:00")
        self.assertEqual(rows[(2019, "daehan")]["solar_term_datetime"], "2019-01-20T18:00:00+09:00")
        self.assertEqual(rows[(2020, "ipchun")]["solar_term_datetime"], "2020-02-04T18:03:00+09:00")
        self.assertEqual(rows[(2020, "gyeongchip")]["solar_term_datetime"], "2020-03-05T11:57:00+09:00")
        self.assertEqual(rows[(2020, "cheongmyeong")]["solar_term_datetime"], "2020-04-04T16:38:00+09:00")
        self.assertEqual(rows[(2020, "ipha")]["solar_term_datetime"], "2020-05-05T09:51:00+09:00")
        self.assertEqual(rows[(2024, "ipchun")]["solar_term_datetime"], "2024-02-04T17:27:00+09:00")
        self.assertEqual(rows[(2024, "gyeongchip")]["solar_term_datetime"], "2024-03-05T11:23:00+09:00")
        self.assertEqual(rows[(2024, "cheongmyeong")]["solar_term_datetime"], "2024-04-04T16:02:00+09:00")
        self.assertEqual(rows[(2024, "ipha")]["solar_term_datetime"], "2024-05-05T09:10:00+09:00")

    def test_collector_can_resume_after_limited_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)

            def fake_fetcher(year: int) -> solar_terms.SourcePayload:
                return solar_terms.SourcePayload(
                    year=year,
                    text=_fake_source_text(year),
                    page_url=f"https://example.test/{year}",
                    source_method="test_fixture",
                )

            first = solar_terms.collect_years(
                years=[2024, 2025],
                limit=1,
                rows_path=base / "rows.jsonl",
                meta_path=base / "meta.json",
                manifest_path=base / "manifest.json",
                log_path=base / "collection.log.jsonl",
                fetcher=fake_fetcher,
            )
            self.assertEqual(first["completed_years"], [2024])
            self.assertEqual(first["pending_years"], [2025])

            second = solar_terms.collect_years(
                years=[2024, 2025],
                rows_path=base / "rows.jsonl",
                meta_path=base / "meta.json",
                manifest_path=base / "manifest.json",
                log_path=base / "collection.log.jsonl",
                fetcher=fake_fetcher,
            )
            self.assertEqual(second["completed_years"], [2024, 2025])
            self.assertEqual(second["pending_years"], [])

            events = [
                json.loads(line)["event"]
                for line in (base / "collection.log.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertIn("year_skipped", events)
            self.assertEqual(events.count("year_success"), 2)


if __name__ == "__main__":
    unittest.main()
