import unittest
from datetime import datetime, timedelta

from app.domain.saju.services.solar_term_boundaries import (
    find_adjacent_jie_boundary,
    find_jie_inside_interval,
    nearest_skyfield_solar_term_boundary,
    nearest_solar_term_boundary,
)


class SolarTermBoundaryProviderTests(unittest.TestCase):
    def test_verified_reference_row_is_used_when_available(self) -> None:
        boundary = nearest_solar_term_boundary(
            "2024-02-04 16:58:00",
            timezone_id="Asia/Seoul",
        )

        self.assertIsNotNone(boundary)
        assert boundary is not None
        self.assertEqual(boundary.provider, "solar_term_reference_table")
        self.assertTrue(boundary.used_reference)
        self.assertEqual(boundary.datetime_text, "2024-02-04 17:27:00")
        self.assertEqual(boundary.relation, "before")
        self.assertEqual(boundary.delta_seconds, 29 * 60)
        self.assertEqual(boundary.reference["table_id"], "solar_terms_extended_1946_2027")
        self.assertEqual(boundary.reference["source_role"], "official_reference_table")

    def test_skyfield_fallback_is_used_for_unverified_year(self) -> None:
        boundary = nearest_solar_term_boundary(
            "1988-02-04 23:00:00",
            timezone_id="Asia/Seoul",
        )

        self.assertIsNotNone(boundary)
        assert boundary is not None
        self.assertEqual(boundary.provider, "skyfield")
        self.assertFalse(boundary.used_reference)
        self.assertEqual(boundary.fallback_reason, "verified_reference_not_available_for_year")
        self.assertEqual(boundary.datetime_text, "1988-02-04 23:42:49")
        self.assertEqual(boundary.reference["term_id"], "ipchun")
        self.assertEqual(boundary.reference["ephemeris"], "de440s.bsp")

    def test_skyfield_fallback_is_used_for_non_korean_timezone(self) -> None:
        boundary = nearest_solar_term_boundary(
            "2024-02-04 16:58:00",
            timezone_id="America/New_York",
        )

        self.assertIsNotNone(boundary)
        assert boundary is not None
        self.assertEqual(boundary.provider, "skyfield")
        self.assertFalse(boundary.used_reference)
        self.assertEqual(boundary.fallback_reason, "reference_timezone_not_supported")
        self.assertEqual(boundary.reference["term_id"], "ipchun")
        self.assertEqual(boundary.reference["timezone_id"], "America/New_York")

    def test_interval_lookup_uses_reference_when_available(self) -> None:
        boundary = find_jie_inside_interval(
            datetime(2024, 3, 5, 0, 0, 0),
            datetime(2024, 3, 5, 23, 59, 59),
            timezone_id="Asia/Seoul",
        )

        self.assertIsNotNone(boundary)
        assert boundary is not None
        self.assertEqual(boundary.provider, "solar_term_reference_table")
        self.assertTrue(boundary.used_reference)
        self.assertEqual(boundary.datetime_text, "2024-03-05 11:23:00")
        self.assertEqual(boundary.reference["source_role"], "official_reference_table")

    def test_interval_lookup_does_not_fallback_when_verified_reference_has_no_boundary(self) -> None:
        boundary = find_jie_inside_interval(
            datetime(2024, 2, 10, 0, 0, 0),
            datetime(2024, 2, 10, 23, 59, 59),
            timezone_id="Asia/Seoul",
        )

        self.assertIsNone(boundary)

    def test_adjacent_boundary_uses_skyfield_for_unverified_luck_cycle_boundary(self) -> None:
        boundary = find_adjacent_jie_boundary(
            datetime(1996, 6, 19, 14, 31, 0),
            "backward",
            timezone_id="Asia/Seoul",
        )

        self.assertIsNotNone(boundary)
        assert boundary is not None
        self.assertEqual(boundary.provider, "skyfield")
        self.assertFalse(boundary.used_reference)
        self.assertEqual(boundary.datetime_text, "1996-06-05 18:40:47")
        self.assertEqual(boundary.reference["term_id"], "mangjong")

    def test_adjacent_boundary_prefers_verified_reference_when_available(self) -> None:
        boundary = find_adjacent_jie_boundary(
            datetime(2024, 2, 10, 9, 57, 58),
            "forward",
            timezone_id="Asia/Seoul",
        )

        self.assertIsNotNone(boundary)
        assert boundary is not None
        self.assertEqual(boundary.provider, "solar_term_reference_table")
        self.assertTrue(boundary.used_reference)
        self.assertEqual(boundary.datetime_text, "2024-03-05 11:23:00")
        self.assertEqual(boundary.reference["term_id"], "gyeongchip")

    def test_reference_term_id_drives_jie_classification_for_sohan(self) -> None:
        boundary = find_adjacent_jie_boundary(
            datetime(2024, 2, 4, 16, 27, 58),
            "backward",
            timezone_id="Asia/Seoul",
        )

        self.assertIsNotNone(boundary)
        assert boundary is not None
        self.assertEqual(boundary.provider, "solar_term_reference_table")
        self.assertEqual(boundary.datetime_text, "2024-01-06 05:49:00")
        self.assertEqual(boundary.reference["term_id"], "sohan")
        self.assertEqual(boundary.reference["term_type"], "jeolgi")
        self.assertEqual(boundary.reference["source_term_type"], "junggi")

    def test_verified_reference_boundary_threshold_deltas_for_common_jie(self) -> None:
        cases = [
            ("sohan", datetime(2024, 1, 6, 5, 49, 0), "2024-01-06 05:49:00"),
            ("ipchun", datetime(2024, 2, 4, 17, 27, 0), "2024-02-04 17:27:00"),
            ("gyeongchip", datetime(2024, 3, 5, 11, 23, 0), "2024-03-05 11:23:00"),
            ("cheongmyeong", datetime(2024, 4, 4, 16, 2, 0), "2024-04-04 16:02:00"),
            ("ipha", datetime(2024, 5, 5, 9, 10, 0), "2024-05-05 09:10:00"),
        ]
        offsets = [
            (-30, "before", 30 * 60),
            (30, "after", 30 * 60),
            (-120, "before", 2 * 60 * 60),
            (120, "after", 2 * 60 * 60),
            (-1440, "before", 24 * 60 * 60),
            (1440, "after", 24 * 60 * 60),
        ]

        for term_id, boundary_dt, expected_datetime in cases:
            for offset_minutes, relation, expected_delta in offsets:
                with self.subTest(term_id=term_id, offset_minutes=offset_minutes):
                    boundary = nearest_solar_term_boundary(
                        (boundary_dt + timedelta(minutes=offset_minutes)).strftime("%Y-%m-%d %H:%M:%S"),
                        timezone_id="Asia/Seoul",
                    )

                    self.assertIsNotNone(boundary)
                    assert boundary is not None
                    self.assertEqual(boundary.provider, "solar_term_reference_table")
                    self.assertTrue(boundary.used_reference)
                    self.assertEqual(boundary.reference["term_id"], term_id)
                    self.assertEqual(boundary.datetime_text, expected_datetime)
                    self.assertEqual(boundary.relation, relation)
                    self.assertEqual(boundary.delta_seconds, expected_delta)

    def test_skyfield_matches_verified_reference_rows_within_one_minute(self) -> None:
        cases = [
            ("sohan", datetime(2024, 1, 6, 5, 49, 0)),
            ("ipchun", datetime(2024, 2, 4, 17, 27, 0)),
            ("gyeongchip", datetime(2024, 3, 5, 11, 23, 0)),
            ("cheongmyeong", datetime(2024, 4, 4, 16, 2, 0)),
            ("ipha", datetime(2024, 5, 5, 9, 10, 0)),
        ]

        for term_id, reference_dt in cases:
            with self.subTest(term_id=term_id):
                boundary = nearest_skyfield_solar_term_boundary(
                    reference_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    timezone_id="Asia/Seoul",
                )

                self.assertIsNotNone(boundary)
                assert boundary is not None
                self.assertEqual(boundary.provider, "skyfield")
                self.assertEqual(boundary.reference["term_id"], term_id)
                self.assertLessEqual(boundary.delta_seconds, 60)


if __name__ == "__main__":
    unittest.main()
