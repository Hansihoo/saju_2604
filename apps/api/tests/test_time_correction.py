import unittest
from datetime import date

from app.domain.saju.time_correction import TimeCorrectionError, normalize_birth_datetime


class TimeCorrectionTests(unittest.TestCase):
    def test_normalizes_regular_asia_seoul_time(self) -> None:
        result = normalize_birth_datetime(
            birth_date=date(1994, 10, 13),
            birth_time="08:30",
            tzid="Asia/Seoul",
        )

        self.assertEqual(result.normalized_local_datetime, "1994-10-13T08:30:00+09:00")
        self.assertEqual(result.normalized_utc_datetime, "1994-10-12T23:30:00+00:00")
        self.assertEqual(result.offset_minutes, 540)
        self.assertFalse(result.ambiguous)
        self.assertEqual(result.fold, 0)

    def test_rejects_non_existent_local_time(self) -> None:
        with self.assertRaises(TimeCorrectionError) as context:
            normalize_birth_datetime(
                birth_date=date(2024, 3, 10),
                birth_time="02:30",
                tzid="America/New_York",
            )

        self.assertEqual(context.exception.error_code, "NON_EXISTENT_LOCAL_TIME")

    def test_marks_ambiguous_local_time(self) -> None:
        result = normalize_birth_datetime(
            birth_date=date(2024, 11, 3),
            birth_time="01:30",
            tzid="America/New_York",
        )

        self.assertTrue(result.ambiguous)
        self.assertEqual(result.fold, 1)
        self.assertEqual(result.normalized_local_datetime, "2024-11-03T01:30:00-05:00")
        self.assertEqual(result.normalized_utc_datetime, "2024-11-03T06:30:00+00:00")


if __name__ == "__main__":
    unittest.main()
