import unittest
from datetime import date

from app.domain.saju.time_correction import normalize_birth_datetime


GOLDEN_SAMPLES = [
    {
        "name": "seoul-modern-standard-time",
        "birth_date": date(1994, 10, 13),
        "birth_time": "08:30",
        "tzid": "Asia/Seoul",
        "expected_local": "1994-10-13T08:30:00+09:00",
        "expected_utc": "1994-10-12T23:30:00+00:00",
        "expected_offset_minutes": 540,
    },
    {
        "name": "seoul-historical-dst-sample",
        "birth_date": date(1988, 5, 10),
        "birth_time": "12:00",
        "tzid": "Asia/Seoul",
        "expected_local": "1988-05-10T12:00:00+10:00",
        "expected_utc": "1988-05-10T02:00:00+00:00",
        "expected_offset_minutes": 600,
    },
]


class TimeCorrectionGoldenTests(unittest.TestCase):
    def test_golden_samples(self) -> None:
        for sample in GOLDEN_SAMPLES:
            with self.subTest(sample=sample["name"]):
                result = normalize_birth_datetime(
                    birth_date=sample["birth_date"],
                    birth_time=sample["birth_time"],
                    tzid=sample["tzid"],
                )

                self.assertEqual(result.normalized_local_datetime, sample["expected_local"])
                self.assertEqual(result.normalized_utc_datetime, sample["expected_utc"])
                self.assertEqual(result.offset_minutes, sample["expected_offset_minutes"])


if __name__ == "__main__":
    unittest.main()
