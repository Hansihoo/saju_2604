import unittest
from datetime import datetime
from unittest.mock import patch

from app.domain.saju.services.day_pillar_reference import resolve_day_pillar_reference


class DayPillarReferenceTests(unittest.TestCase):
    def test_sect1_uses_next_reference_date_after_23(self) -> None:
        reference = resolve_day_pillar_reference(
            input_dt=datetime(1988, 11, 20, 23, 0, 0),
            sect=1,
            lunar_python_gan_zhi="\u5e9a\u8fb0",
        )

        self.assertEqual(reference.source, "kasi_lunar_reference")
        self.assertEqual(reference.reference_date, "1988-11-21")
        self.assertEqual(reference.civil_date, "1988-11-20")
        self.assertEqual(reference.day_pillar_basis_date, "1988-11-21")
        self.assertEqual(reference.iljin_query_date, "1988-11-21")
        self.assertEqual(reference.gan_zhi, "\u5e9a\u8fb0")
        self.assertEqual(reference.matched_lunar_python, "true")

    def test_sect1_uses_current_reference_date_before_23(self) -> None:
        reference = resolve_day_pillar_reference(
            input_dt=datetime(1988, 11, 20, 22, 59, 0),
            sect=1,
            lunar_python_gan_zhi="\u5df1\u536f",
        )

        self.assertEqual(reference.iljin_query_date, "1988-11-20")
        self.assertEqual(reference.gan_zhi, "\u5df1\u536f")

    def test_sect1_uses_next_reference_date_at_2330(self) -> None:
        reference = resolve_day_pillar_reference(
            input_dt=datetime(1988, 11, 20, 23, 30, 0),
            sect=1,
            lunar_python_gan_zhi="\u5e9a\u8fb0",
        )

        self.assertEqual(reference.iljin_query_date, "1988-11-21")
        self.assertEqual(reference.gan_zhi, "\u5e9a\u8fb0")

    def test_sect1_uses_current_reference_date_after_civil_midnight(self) -> None:
        reference = resolve_day_pillar_reference(
            input_dt=datetime(1988, 11, 21, 0, 30, 0),
            sect=1,
            lunar_python_gan_zhi="\u5e9a\u8fb0",
        )

        self.assertEqual(reference.iljin_query_date, "1988-11-21")
        self.assertEqual(reference.gan_zhi, "\u5e9a\u8fb0")

    def test_sect1_uses_following_reference_date_next_day_after_23(self) -> None:
        reference = resolve_day_pillar_reference(
            input_dt=datetime(1988, 11, 21, 23, 0, 0),
            sect=1,
            lunar_python_gan_zhi="\u8f9b\u5df3",
        )

        self.assertEqual(reference.iljin_query_date, "1988-11-22")
        self.assertEqual(reference.gan_zhi, "\u8f9b\u5df3")

    def test_sect2_uses_same_reference_date_at_23(self) -> None:
        reference = resolve_day_pillar_reference(
            input_dt=datetime(1988, 11, 20, 23, 0, 0),
            sect=2,
            lunar_python_gan_zhi="\u5df1\u536f",
        )

        self.assertEqual(reference.source, "kasi_lunar_reference")
        self.assertEqual(reference.reference_date, "1988-11-20")
        self.assertEqual(reference.iljin_query_date, "1988-11-20")
        self.assertEqual(reference.gan_zhi, "\u5df1\u536f")
        self.assertEqual(reference.matched_lunar_python, "true")

    def test_falls_back_to_lunar_python_when_reference_is_missing(self) -> None:
        with patch(
            "app.domain.saju.services.day_pillar_reference.lookup_lunar_reference_by_solar_date",
            return_value=None,
        ):
            reference = resolve_day_pillar_reference(
                input_dt=datetime(2024, 2, 10, 10, 30, 0),
                sect=1,
                lunar_python_gan_zhi="\u7532\u8fb0",
            )

        self.assertEqual(reference.source, "lunar_python_fallback")
        self.assertEqual(reference.reference_date, "")
        self.assertEqual(reference.iljin_query_date, "2024-02-10")
        self.assertEqual(reference.gan_zhi, "\u7532\u8fb0")
        self.assertEqual(reference.stem, "\u7532")
        self.assertEqual(reference.branch, "\u8fb0")
        self.assertEqual(reference.matched_lunar_python, "")


if __name__ == "__main__":
    unittest.main()
