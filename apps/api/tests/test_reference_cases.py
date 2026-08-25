import json
import unittest
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from app.domain.saju.adapters.lunar_python_engine import LunarPythonSajuEngine
from app.domain.saju.calendar_normalization import normalize_calendar
from app.domain.saju.reference_calendar import lookup_lunar_reference_by_solar_date
from app.domain.saju.time_correction import (
    TimeCorrectionError,
    calculate_daylight_saving_offset_minutes,
    normalize_birth_datetime,
)
from app.domain.saju.services.solar_term_boundaries import nearest_skyfield_solar_term_boundary


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "reference_cases"
SOLAR_TERM_ROWS_PATH = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "domain"
    / "saju"
    / "data"
    / "solar_terms_reference"
    / "kasi_solar_terms_common_years.jsonl"
)
REFERENCE_FIXTURE_NAMES = [
    "lunar_solar_reference_cases.json",
    "solar_term_reference_cases.json",
    "timezone_dst_reference_cases.json",
    "midnight_boundary_cases.json",
]
REQUIRED_CASE_FIELDS = {
    "case_id",
    "description",
    "input",
    "expected",
    "source",
    "tolerance",
    "notes",
}


def _load_fixture(filename: str) -> Dict[str, Any]:
    return json.loads((FIXTURE_DIR / filename).read_text(encoding="utf-8"))


def _iter_reference_cases() -> Iterable[Tuple[str, Dict[str, Any]]]:
    for filename in REFERENCE_FIXTURE_NAMES:
        fixture = _load_fixture(filename)
        for case in fixture["cases"]:
            yield filename, case


def _is_pending_reference(case: Dict[str, Any]) -> bool:
    return case["expected"].get("status") == "pending_reference"


def _parse_date(value: str) -> date:
    year, month, day = [int(part) for part in value.split("-")]
    return date(year, month, day)


def _load_solar_term_rows() -> Dict[Tuple[int, str], Dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in SOLAR_TERM_ROWS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {
        (int(row["year"]), row["term_id"]): row
        for row in rows
    }


class ReferenceFixtureSchemaTests(unittest.TestCase):
    def test_reference_fixture_files_exist_and_use_required_schema(self) -> None:
        for filename in REFERENCE_FIXTURE_NAMES:
            with self.subTest(filename=filename):
                fixture_path = FIXTURE_DIR / filename
                self.assertTrue(fixture_path.exists(), filename)
                fixture = _load_fixture(filename)
                self.assertEqual(fixture["schema_version"], 1)
                self.assertEqual(fixture["category"], filename.replace(".json", ""))
                self.assertGreater(len(fixture["cases"]), 0)

                for case in fixture["cases"]:
                    self.assertTrue(REQUIRED_CASE_FIELDS.issubset(case.keys()))
                    self.assertTrue(case["case_id"])
                    self.assertTrue(case["expected"])
                    self.assertIn("type", case["source"])

    def test_reference_cases_have_no_unresolved_pending_rows(self) -> None:
        cases = list(_iter_reference_cases())
        hard_cases = [case for _filename, case in cases if not _is_pending_reference(case)]
        pending_cases = [case for _filename, case in cases if _is_pending_reference(case)]

        self.assertGreaterEqual(len(hard_cases), 1)
        self.assertEqual(pending_cases, [])


class HardReferenceTests(unittest.TestCase):
    def test_hard_reference_tests_compare_lunar_solar_cases(self) -> None:
        fixture = _load_fixture("lunar_solar_reference_cases.json")
        hard_cases = [case for case in fixture["cases"] if not _is_pending_reference(case)]
        self.assertGreaterEqual(len(hard_cases), 7)

        for case in hard_cases:
            with self.subTest(case_id=case["case_id"]):
                input_data = case["input"]
                expected = case["expected"]
                result = normalize_calendar(
                    calendar_type=input_data["calendar_type"],
                    birth_date=_parse_date(input_data["birth_date"]),
                    birth_time=input_data["birth_time"],
                    is_lunar_leap_month=input_data.get("is_lunar_leap_month", False),
                )

                actual = {
                    "normalized_solar_datetime": result.normalized_solar_datetime,
                    "normalized_lunar_datetime": result.normalized_lunar_datetime,
                    "lunar_year": result.lunar_year,
                    "lunar_month": result.lunar_month,
                    "lunar_day": result.lunar_day,
                    "is_lunar_leap_month": result.is_lunar_leap_month,
                }
                expected_subset = {
                    key: expected[key]
                    for key in actual.keys()
                }
                self.assertEqual(actual, expected_subset)

                record = lookup_lunar_reference_by_solar_date(
                    date(result.solar_year, result.solar_month, result.solar_day)
                )
                self.assertIsNotNone(record)
                self.assertEqual(record.day_ganzhi_hanja, expected["iljin"])

    def test_hard_reference_tests_compare_timezone_dst_cases(self) -> None:
        fixture = _load_fixture("timezone_dst_reference_cases.json")
        hard_cases = [case for case in fixture["cases"] if not _is_pending_reference(case)]
        self.assertGreaterEqual(len(hard_cases), 4)

        for case in hard_cases:
            with self.subTest(case_id=case["case_id"]):
                input_data = case["input"]
                expected = case["expected"]
                self.assertEqual(input_data["operation"], "normalize_birth_datetime")

                if "error_code" in expected:
                    with self.assertRaises(TimeCorrectionError) as context:
                        normalize_birth_datetime(
                            birth_date=_parse_date(input_data["birth_date"]),
                            birth_time=input_data["birth_time"],
                            tzid=input_data["tzid"],
                        )
                    self.assertEqual(context.exception.error_code, expected["error_code"])
                    continue

                result = normalize_birth_datetime(
                    birth_date=_parse_date(input_data["birth_date"]),
                    birth_time=input_data["birth_time"],
                    tzid=input_data["tzid"],
                )
                actual = {
                    "normalized_local_datetime": result.normalized_local_datetime,
                    "normalized_utc_datetime": result.normalized_utc_datetime,
                    "offset_minutes": result.offset_minutes,
                    "ambiguous": result.ambiguous,
                    "fold": result.fold,
                }
                if "daylight_saving_offset_minutes" in expected:
                    actual["daylight_saving_offset_minutes"] = calculate_daylight_saving_offset_minutes(
                        tzid=input_data["tzid"],
                        offset_minutes=result.offset_minutes,
                    )

                self.assertEqual(actual, expected)

    def test_hard_reference_tests_compare_midnight_boundary_cases(self) -> None:
        fixture = _load_fixture("midnight_boundary_cases.json")
        hard_cases = [case for case in fixture["cases"] if not _is_pending_reference(case)]
        self.assertGreaterEqual(len(hard_cases), 4)
        engine = LunarPythonSajuEngine()

        for case in hard_cases:
            with self.subTest(case_id=case["case_id"]):
                input_data = case["input"]
                expected = case["expected"]
                self.assertEqual(input_data["operation"], "calculate_saju")
                self.assertEqual(expected["primary_midnight_rule"], "sect1_23_changes_day")

                result = engine.calculate(
                    corrected_solar_datetime=input_data["corrected_solar_datetime"],
                    gender=input_data["gender"],
                    tzid=input_data["tzid"],
                )
                actual_pillars = {
                    "year": result.pillars["year"].gan_zhi,
                    "month": result.pillars["month"].gan_zhi,
                    "day": result.pillars["day"].gan_zhi,
                    "time": result.pillars["time"].gan_zhi,
                }

                self.assertEqual(actual_pillars, expected["pillars"])

    def test_hard_reference_tests_compare_solar_term_cases(self) -> None:
        fixture = _load_fixture("solar_term_reference_cases.json")
        hard_cases = [
            case
            for case in fixture["cases"]
            if not _is_pending_reference(case)
            and case["source"]["type"] != "skyfield_de440s_ephemeris"
        ]
        self.assertGreaterEqual(len(hard_cases), 10)
        rows = _load_solar_term_rows()

        for case in hard_cases:
            with self.subTest(case_id=case["case_id"]):
                input_data = case["input"]
                expected = case["expected"]
                year = int(input_data["date"].split("-", 1)[0])
                row = rows[(year, input_data["solar_term"])]

                self.assertEqual(row["solar_term_datetime"], expected["solar_term_datetime"])
                self.assertEqual(row["timezone_id"], input_data["timezone"])
                self.assertEqual(row["source"]["type"], case["source"]["type"])


class PendingReferenceReportTests(unittest.TestCase):
    def test_pending_reference_report_has_no_collection_backlog(self) -> None:
        pending_cases: List[Dict[str, str]] = []
        for filename, case in _iter_reference_cases():
            if _is_pending_reference(case):
                pending_cases.append(
                    {
                        "fixture": filename,
                        "case_id": case["case_id"],
                        "source": case["source"]["name"],
                        "needed_fields": ",".join(case["expected"].get("needed_fields", [])),
                    }
                )

        self.assertEqual(pending_cases, [])
        print("PENDING_REFERENCE_REPORT " + json.dumps(pending_cases, ensure_ascii=False, sort_keys=True))


class IndependentSolarTermReferenceTests(unittest.TestCase):
    def test_skyfield_reference_cases_match_the_checked_in_values(self) -> None:
        fixture = _load_fixture("solar_term_reference_cases.json")
        cases = [
            case
            for case in fixture["cases"]
            if case["source"]["type"] == "skyfield_de440s_ephemeris"
        ]
        self.assertEqual(len(cases), 2)

        for case in cases:
            with self.subTest(case_id=case["case_id"]):
                input_data = case["input"]
                expected = case["expected"]
                boundary = nearest_skyfield_solar_term_boundary(
                    input_data["input_datetime"].replace("T", " ").split("+", 1)[0],
                    timezone_id=input_data["timezone"],
                )

                self.assertIsNotNone(boundary)
                assert boundary is not None
                self.assertEqual(boundary.provider, "skyfield")
                self.assertEqual(boundary.reference["term_id"], input_data["solar_term"])
                self.assertEqual(
                    boundary.datetime_text,
                    expected["nearest_solar_term_datetime"].replace("T", " ").split("+", 1)[0],
                )
                self.assertEqual(boundary.delta_seconds, expected["delta_seconds"])
                self.assertEqual(boundary.relation, expected["relation"])


if __name__ == "__main__":
    unittest.main()
