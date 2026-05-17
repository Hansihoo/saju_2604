import json
import unittest
from dataclasses import asdict
from datetime import date, datetime

from app.domain.saju.time_correction import (
    TimeCorrectionError,
    apply_regional_solar_correction,
    build_birth_time_context,
    calculate_daylight_saving_offset_minutes,
    normalize_birth_datetime,
)


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

    def test_applies_regional_solar_correction_using_longitude_offset(self) -> None:
        result = apply_regional_solar_correction(
            normalized_solar_datetime="2024-02-10 10:30:00",
            longitude=126.991824,
            regional_time_offset_minutes=-32.033,
            daylight_saving_offset_minutes=0,
            correction_basis="광역자치단체 중심점",
        )

        self.assertEqual(result.source_solar_datetime, "2024-02-10 10:30:00")
        self.assertEqual(result.corrected_solar_datetime, "2024-02-10 09:57:58")
        self.assertEqual(result.longitude, 126.991824)
        self.assertEqual(result.regional_time_offset_minutes, -32.033)

    def test_calculates_dst_offset_for_1988_seoul(self) -> None:
        result = calculate_daylight_saving_offset_minutes(
            tzid="Asia/Seoul",
            offset_minutes=600,
        )

        self.assertEqual(result, -60)

    def test_applies_dst_before_regional_solar_correction(self) -> None:
        result = apply_regional_solar_correction(
            normalized_solar_datetime="1988-05-20 12:30:00",
            longitude=126.991824,
            regional_time_offset_minutes=-32.033,
            daylight_saving_offset_minutes=-60,
            correction_basis="standard-meridian-longitude",
        )

        self.assertEqual(result.corrected_solar_datetime, "1988-05-20 10:57:58")
        self.assertEqual(result.daylight_saving_offset_minutes, -60)

    def test_birth_time_context_separates_standard_and_mean_solar_time(self) -> None:
        time_correction = normalize_birth_datetime(
            birth_date=date(2024, 2, 10),
            birth_time="10:30",
            tzid="Asia/Seoul",
        )
        regional_solar_correction = apply_regional_solar_correction(
            normalized_solar_datetime="2024-02-10 10:30:00",
            longitude=126.991824,
            regional_time_offset_minutes=-32.033,
            daylight_saving_offset_minutes=0,
            correction_basis="standard-meridian-longitude",
        )

        context = build_birth_time_context(
            time_correction=time_correction,
            normalized_solar_datetime="2024-02-10 10:30:00",
            regional_solar_correction=regional_solar_correction,
        )

        self.assertEqual(context.standard_local_datetime, "2024-02-10 10:30:00")
        self.assertEqual(context.mean_solar_datetime, "2024-02-10 09:57:58")
        standard_local = datetime.strptime(context.standard_local_datetime, "%Y-%m-%d %H:%M:%S")
        mean_solar = datetime.strptime(context.mean_solar_datetime, "%Y-%m-%d %H:%M:%S")
        self.assertAlmostEqual((mean_solar - standard_local).total_seconds() / 60, -32.033, places=3)
        self.assertEqual(context.corrected_solar_datetime, regional_solar_correction.corrected_solar_datetime)
        self.assertEqual(
            context.legacy_corrected_solar_datetime,
            regional_solar_correction.corrected_solar_datetime,
        )
        self.assertEqual(context.dst_offset_minutes, 0)
        self.assertEqual(context.warnings, [])

    def test_birth_time_context_separates_dst_adjusted_standard_time(self) -> None:
        time_correction = normalize_birth_datetime(
            birth_date=date(1988, 5, 20),
            birth_time="12:30",
            tzid="Asia/Seoul",
        )
        daylight_saving_offset_minutes = calculate_daylight_saving_offset_minutes(
            tzid="Asia/Seoul",
            offset_minutes=time_correction.offset_minutes,
        )
        regional_solar_correction = apply_regional_solar_correction(
            normalized_solar_datetime="1988-05-20 12:30:00",
            longitude=126.991824,
            regional_time_offset_minutes=-32.033,
            daylight_saving_offset_minutes=daylight_saving_offset_minutes,
            correction_basis="standard-meridian-longitude",
        )

        context = build_birth_time_context(
            time_correction=time_correction,
            normalized_solar_datetime="1988-05-20 12:30:00",
            regional_solar_correction=regional_solar_correction,
        )

        self.assertEqual(context.normalized_local_datetime, "1988-05-20T12:30:00+10:00")
        self.assertEqual(context.normalized_solar_datetime, "1988-05-20 12:30:00")
        self.assertEqual(context.standard_local_datetime, "1988-05-20 11:30:00")
        self.assertNotEqual(context.standard_local_datetime, context.normalized_solar_datetime)
        self.assertEqual(context.mean_solar_datetime, "1988-05-20 10:57:58")
        self.assertEqual(context.corrected_solar_datetime, "1988-05-20 10:57:58")
        self.assertEqual(context.dst_offset_minutes, 60)
        self.assertEqual(context.daylight_saving_offset_minutes, -60)
        self.assertIn("daylight_saving_adjustment_applied", context.warnings)

    def test_birth_time_context_is_json_serializable(self) -> None:
        time_correction = normalize_birth_datetime(
            birth_date=date(2024, 2, 10),
            birth_time="10:30",
            tzid="Asia/Seoul",
        )
        regional_solar_correction = apply_regional_solar_correction(
            normalized_solar_datetime="2024-02-10 10:30:00",
            longitude=126.991824,
            regional_time_offset_minutes=-32.033,
            daylight_saving_offset_minutes=0,
            correction_basis="standard-meridian-longitude",
        )
        context = build_birth_time_context(
            time_correction=time_correction,
            normalized_solar_datetime="2024-02-10 10:30:00",
            regional_solar_correction=regional_solar_correction,
        )

        json.dumps(asdict(context))


if __name__ == "__main__":
    unittest.main()
