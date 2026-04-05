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


if __name__ == "__main__":
    unittest.main()
