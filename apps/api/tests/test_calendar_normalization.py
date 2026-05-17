import unittest
from datetime import date

from app.domain.saju.calendar_normalization import normalize_calendar


class CalendarNormalizationTests(unittest.TestCase):
    def test_keeps_solar_input_as_same_solar_datetime(self) -> None:
        result = normalize_calendar(
            calendar_type="solar",
            birth_date=date(2024, 2, 10),
            birth_time="10:30",
            is_lunar_leap_month=False,
        )

        self.assertEqual(result.normalized_solar_datetime, "2024-02-10 10:30:00")
        self.assertEqual(result.normalized_lunar_datetime, "2024-01-01 10:30:00")
        self.assertEqual(result.lunar_month, 1)
        self.assertEqual(result.lunar_day, 1)

    def test_normalizes_lunar_input_to_matching_solar_datetime(self) -> None:
        result = normalize_calendar(
            calendar_type="lunar",
            birth_date=date(2024, 1, 1),
            birth_time="10:30",
            is_lunar_leap_month=False,
        )

        self.assertEqual(result.normalized_solar_datetime, "2024-02-10 10:30:00")
        self.assertEqual(result.normalized_lunar_datetime, "2024-01-01 10:30:00")
        self.assertEqual(result.solar_month, 2)
        self.assertEqual(result.solar_day, 10)

    def test_uses_kasi_reference_for_known_1914_boundary(self) -> None:
        result = normalize_calendar(
            calendar_type="solar",
            birth_date=date(1914, 6, 23),
            birth_time="00:00",
            is_lunar_leap_month=False,
        )

        self.assertEqual(result.normalized_lunar_datetime, "1914-05-30 00:00:00")
        self.assertFalse(result.is_lunar_leap_month)
        self.assertEqual(result.lunar_month, 5)
        self.assertEqual(result.lunar_day, 30)

    def test_solar_input_reports_actual_lunar_leap_month(self) -> None:
        result = normalize_calendar(
            calendar_type="solar",
            birth_date=date(2023, 3, 22),
            birth_time="00:00",
            is_lunar_leap_month=False,
        )

        self.assertEqual(result.normalized_lunar_datetime, "2023-02-01 00:00:00")
        self.assertTrue(result.is_lunar_leap_month)

    def test_normalizes_1956_year_end_date_from_reference_data(self) -> None:
        result = normalize_calendar(
            calendar_type="solar",
            birth_date=date(1956, 12, 31),
            birth_time="00:00",
            is_lunar_leap_month=False,
        )

        self.assertEqual(result.normalized_lunar_datetime, "1956-11-30 00:00:00")

    def test_lunar_1956_year_end_round_trips_to_solar_date(self) -> None:
        result = normalize_calendar(
            calendar_type="lunar",
            birth_date=date(1956, 11, 30),
            birth_time="00:00",
            is_lunar_leap_month=False,
        )

        self.assertEqual(result.normalized_solar_datetime, "1956-12-31 00:00:00")

    def test_normalizes_leap_lunar_month_input(self) -> None:
        result = normalize_calendar(
            calendar_type="lunar",
            birth_date=date(2023, 2, 15),
            birth_time="10:30",
            is_lunar_leap_month=True,
        )

        self.assertEqual(result.normalized_solar_datetime, "2023-04-05 10:30:00")
        self.assertEqual(result.normalized_lunar_datetime, "2023-02-15 10:30:00")
        self.assertTrue(result.is_lunar_leap_month)

    def test_kasi_reference_round_trip_cases(self) -> None:
        cases = [
            {
                "calendar_type": "solar",
                "birth_date": date(1914, 6, 23),
                "birth_time": "00:00",
                "is_lunar_leap_month": False,
                "expected_solar": "1914-06-23 00:00:00",
                "expected_lunar": "1914-05-30 00:00:00",
                "expected_leap": False,
            },
            {
                "calendar_type": "lunar",
                "birth_date": date(1914, 5, 30),
                "birth_time": "00:00",
                "is_lunar_leap_month": False,
                "expected_solar": "1914-06-23 00:00:00",
                "expected_lunar": "1914-05-30 00:00:00",
                "expected_leap": False,
            },
            {
                "calendar_type": "solar",
                "birth_date": date(1956, 12, 31),
                "birth_time": "00:00",
                "is_lunar_leap_month": False,
                "expected_solar": "1956-12-31 00:00:00",
                "expected_lunar": "1956-11-30 00:00:00",
                "expected_leap": False,
            },
            {
                "calendar_type": "lunar",
                "birth_date": date(2023, 2, 15),
                "birth_time": "10:30",
                "is_lunar_leap_month": True,
                "expected_solar": "2023-04-05 10:30:00",
                "expected_lunar": "2023-02-15 10:30:00",
                "expected_leap": True,
            },
        ]

        for case in cases:
            with self.subTest(case=case):
                result = normalize_calendar(
                    calendar_type=case["calendar_type"],
                    birth_date=case["birth_date"],
                    birth_time=case["birth_time"],
                    is_lunar_leap_month=case["is_lunar_leap_month"],
                )

                self.assertEqual(result.normalized_solar_datetime, case["expected_solar"])
                self.assertEqual(result.normalized_lunar_datetime, case["expected_lunar"])
                self.assertEqual(result.is_lunar_leap_month, case["expected_leap"])


if __name__ == "__main__":
    unittest.main()
