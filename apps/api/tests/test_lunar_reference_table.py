import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from app.domain.saju.calendar_normalization import normalize_calendar
from app.domain.saju.reference_calendar import (
    get_lunar_reference_metadata,
    load_lunar_reference_table,
    lookup_lunar_reference_by_lunar_date,
    lookup_lunar_reference_by_solar_date,
)
from app.tools.build_lunar_reference_table import (
    _service_key_query_value,
    check_table,
    verify_table_with_kasi,
)


API_ROOT = Path(__file__).resolve().parents[1]


class LunarReferenceTableTests(unittest.TestCase):
    def test_kasi_service_key_query_value_handles_encoded_and_decoded_keys(self) -> None:
        self.assertEqual(_service_key_query_value("abc%2Fdef%3D"), "abc%2Fdef%3D")
        self.assertEqual(_service_key_query_value("abc/def+=="), "abc%2Fdef%2B%3D%3D")

    def test_checked_in_table_metadata_and_hash_are_valid(self) -> None:
        table = load_lunar_reference_table()
        metadata = get_lunar_reference_metadata()

        self.assertEqual(metadata["schema_version"], 2)
        self.assertEqual(metadata["table_id"], "kasi_lunar_calendar_1900_2050")
        self.assertEqual(metadata["source"]["name"], "KASI lunisolar calendar API")
        self.assertEqual(metadata["range"]["start_date"], "1900-01-01")
        self.assertEqual(metadata["range"]["end_date"], "2050-12-31")
        self.assertEqual(metadata["row_count"], 55152)
        self.assertEqual(len(table.by_solar_date), metadata["row_count"])
        self.assertEqual(len(table.by_lunar_date), metadata["row_count"])
        self.assertEqual(len(metadata["rows_sha256"]), 64)
        self.assertEqual(metadata["source"]["provider"], "Korea Astronomy and Space Science Institute")
        self.assertEqual(metadata["source"]["type"], "official_open_api")
        self.assertTrue(metadata["source"]["endpoint"].startswith("https://apis.data.go.kr/"))

    def test_reference_data_is_included_as_package_data(self) -> None:
        pyproject = (API_ROOT / "pyproject.toml").read_text(encoding="utf-8")

        self.assertIn("[tool.setuptools.package-data]", pyproject)
        self.assertIn("data/lunar_reference/*.jsonl", pyproject)
        self.assertIn("data/lunar_reference/*.json", pyproject)

    def test_table_check_command_verifies_checked_in_data(self) -> None:
        result = check_table()

        self.assertTrue(result["hash_matches_metadata"])
        self.assertTrue(result["row_count_matches_range"])
        self.assertTrue(result["range_matches_expected"])
        self.assertEqual(result["source_name"], "KASI lunisolar calendar API")

    def test_checked_in_rows_cover_range_boundaries_and_have_iljin_values(self) -> None:
        table = load_lunar_reference_table()

        first = table.by_solar_date["1900-01-01"]
        last = table.by_solar_date["2050-12-31"]

        self.assertEqual(first.lunar_date, "1899-12-01")
        self.assertEqual(first.julian_day, 2415021)
        self.assertTrue(first.day_ganzhi_hanja)
        self.assertEqual(last.lunar_date, "2050-11-18")
        self.assertEqual(last.julian_day, 2470172)
        self.assertTrue(last.day_ganzhi_hanja)
        self.assertTrue(all(record.day_ganzhi_hanja for record in table.by_solar_date.values()))

    def test_live_kasi_spot_check_helper_compares_selected_rows(self) -> None:
        generated_rows = [
            (
                json.dumps(
                    {
                        "solar_date": "2024-02-10",
                        "solar_year": 2024,
                        "solar_month": 2,
                        "solar_day": 10,
                        "lunar_date": "2024-01-01",
                        "lunar_year": 2024,
                        "lunar_month": 1,
                        "lunar_day": 1,
                        "is_lunar_leap_month": False,
                        "day_ganzhi_korean": "gapjin",
                        "day_ganzhi_hanja": "\u7532\u8fb0",
                        "julian_day": 2460351,
                    },
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8")
        ]

        with tempfile.TemporaryDirectory() as tmp:
            rows_path = Path(tmp) / "rows.jsonl"
            rows_path.write_bytes(b"".join(generated_rows))

            with patch(
                "app.tools.build_lunar_reference_table.build_rows",
                return_value=(generated_rows, {}),
            ):
                result = verify_table_with_kasi(
                    rows_path=rows_path,
                    start_date="2024-02-10",
                    end_date="2024-02-10",
                    service_key="test-key",
                )

        self.assertEqual(result["compared"], 1)
        self.assertEqual(result["mismatch_count"], 0)

    def test_lookup_known_solar_and_lunar_dates(self) -> None:
        solar_record = lookup_lunar_reference_by_solar_date(date(1914, 6, 23))
        lunar_record = lookup_lunar_reference_by_lunar_date(
            lunar_year=1914,
            lunar_month=5,
            lunar_day=30,
            is_lunar_leap_month=False,
        )
        leap_record = lookup_lunar_reference_by_lunar_date(
            lunar_year=2023,
            lunar_month=2,
            lunar_day=15,
            is_lunar_leap_month=True,
        )

        self.assertIsNotNone(solar_record)
        self.assertIsNotNone(lunar_record)
        self.assertIsNotNone(leap_record)
        self.assertEqual(solar_record, lunar_record)
        self.assertEqual(solar_record.lunar_date, "1914-05-30")
        self.assertEqual(leap_record.solar_date, "2023-04-05")
        self.assertTrue(leap_record.is_lunar_leap_month)

    def test_table_records_match_kasi_known_values_for_samples(self) -> None:
        cases = [
            (date(1914, 6, 23), "1914-05-30", False, "庚辰", 2420307),
            (date(1914, 6, 24), "1914-05-01", True, "辛巳", 2420308),
            (date(1956, 12, 31), "1956-11-30", False, "壬申", 2435839),
            (date(2023, 4, 5), "2023-02-15", True, "癸巳", 2460040),
            (date(2024, 2, 10), "2024-01-01", False, "甲辰", 2460351),
        ]

        for sample_date, lunar_date, is_leap, day_ganzhi_hanja, julian_day in cases:
            with self.subTest(sample_date=sample_date.isoformat()):
                record = lookup_lunar_reference_by_solar_date(sample_date)
                self.assertIsNotNone(record)
                self.assertEqual(record.lunar_date, lunar_date)
                self.assertEqual(record.is_lunar_leap_month, is_leap)
                self.assertEqual(record.day_ganzhi_hanja, day_ganzhi_hanja)
                self.assertEqual(record.julian_day, julian_day)

    def test_calendar_normalization_uses_reference_table_values(self) -> None:
        cases = [
            ("solar", date(1914, 6, 23), False, "1914-06-23 00:00:00", "1914-05-30 00:00:00"),
            ("lunar", date(1914, 5, 30), False, "1914-06-23 00:00:00", "1914-05-30 00:00:00"),
            ("lunar", date(2023, 2, 15), True, "2023-04-05 00:00:00", "2023-02-15 00:00:00"),
            ("solar", date(2023, 3, 22), False, "2023-03-22 00:00:00", "2023-02-01 00:00:00"),
        ]

        for calendar_type, birth_date, is_leap, expected_solar, expected_lunar in cases:
            with self.subTest(calendar_type=calendar_type, birth_date=birth_date.isoformat()):
                result = normalize_calendar(
                    calendar_type=calendar_type,
                    birth_date=birth_date,
                    birth_time="00:00",
                    is_lunar_leap_month=is_leap,
                )

                self.assertEqual(result.normalized_solar_datetime, expected_solar)
                self.assertEqual(result.normalized_lunar_datetime, expected_lunar)
                self.assertEqual(result.is_lunar_leap_month, "2023-03-22" in expected_solar or is_leap)

    def test_checked_in_rows_have_kasi_julian_day_values(self) -> None:
        generated = [
            {
                "solar_date": "2024-02-09",
                "lunar_date": "2023-12-30",
                "julian_day": 2460350,
            },
            {
                "solar_date": "2024-02-10",
                "lunar_date": "2024-01-01",
                "julian_day": 2460351,
            },
            {
                "solar_date": "2024-02-11",
                "lunar_date": "2024-01-02",
                "julian_day": 2460352,
            },
        ]
        checked_in = [
            lookup_lunar_reference_by_solar_date(date.fromisoformat(item["solar_date"]))
            for item in generated
        ]

        self.assertEqual(
            [item["lunar_date"] for item in generated],
            [record.lunar_date for record in checked_in],
        )
        self.assertEqual(
            [item["julian_day"] for item in generated],
            [record.julian_day for record in checked_in],
        )


if __name__ == "__main__":
    unittest.main()
