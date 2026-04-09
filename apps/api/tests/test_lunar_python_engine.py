import unittest

from app.domain.saju.adapters.lunar_python_engine import LunarPythonSajuEngine


class LunarPythonSajuEngineTests(unittest.TestCase):
    def test_calculates_expected_pillars_and_elements(self) -> None:
        engine = LunarPythonSajuEngine()

        result = engine.calculate(
            corrected_solar_datetime="2024-02-10 10:30:00",
            gender="male",
            tzid="Asia/Seoul",
        )

        self.assertEqual(result.pillars["year"].gan_zhi, "\u7532\u8fb0")
        self.assertEqual(result.pillars["month"].gan_zhi, "\u4e19\u5bc5")
        self.assertEqual(result.pillars["day"].gan_zhi, "\u7532\u8fb0")
        self.assertEqual(result.pillars["time"].gan_zhi, "\u5df1\u5df3")
        self.assertEqual(
            result.element_counts,
            {
                "wood": 3,
                "fire": 2,
                "earth": 3,
                "metal": 0,
                "water": 0,
            },
        )
        self.assertEqual(result.ten_god_stems["time"], "\u6b63\u8d22")
        self.assertEqual(result.meta["day_master"], "\u7532")
        self.assertEqual(result.pillars["year"].twelve_fortune, "\u8870")
        self.assertEqual(result.pillars["year"].na_yin, "\u8986\u706f\u706b")
        self.assertEqual(result.pillars["year"].xun_kong, "\u5bc5\u536f")
        self.assertEqual(result.pillars["time"].branch_ten_god, "\u98df\u795e")
        self.assertEqual(
            result.pillars["time"].hidden_stems,
            ["\u4e19", "\u5e9a", "\u620a"],
        )

    def test_returns_decade_luck_cycle_metadata(self) -> None:
        engine = LunarPythonSajuEngine()

        result = engine.calculate(
            corrected_solar_datetime="2024-02-10 10:30:00",
            gender="male",
            tzid="Asia/Seoul",
        )

        self.assertEqual(len(result.luck_cycles), 10)
        self.assertEqual(result.luck_cycles[0].gan_zhi, "\u4e01\u536f")
        self.assertEqual(result.luck_cycles[0].start_year, 2032)
        self.assertEqual(result.luck_cycles[0].end_year, 2041)
        self.assertEqual(result.luck_cycles[0].start_age, 8)
        self.assertEqual(result.meta["luck_cycle_start_date"], "2024-03-05")
        self.assertEqual(result.meta["luck_cycle_direction"], "forward")
        self.assertEqual(result.meta["luck_cycle_boundary_datetime"], "2024-03-05 11:22:45")

    def test_returns_supplementary_positions_for_manse_scope(self) -> None:
        engine = LunarPythonSajuEngine()

        result = engine.calculate(
            corrected_solar_datetime="2024-02-10 10:30:00",
            gender="male",
            tzid="Asia/Seoul",
        )

        self.assertEqual(result.supplementary_positions["tai_yuan"].gan_zhi, "\u4e01\u5df3")
        self.assertEqual(result.supplementary_positions["ming_gong"].gan_zhi, "\u7532\u620c")
        self.assertEqual(result.supplementary_positions["shen_gong"].gan_zhi, "\u58ec\u7533")
        self.assertEqual(result.supplementary_positions["tai_xi"].gan_zhi, "\u5df1\u9149")

    def test_uses_late_zi_convention_for_day_pillar(self) -> None:
        engine = LunarPythonSajuEngine()

        result = engine.calculate(
            corrected_solar_datetime="1988-11-20 23:02:00",
            gender="male",
            tzid="Asia/Seoul",
        )

        self.assertEqual(result.pillars["day"].gan_zhi, "\u5e9a\u8fb0")
        self.assertEqual(result.pillars["time"].gan_zhi, "\u4e19\u5b50")

    def test_adjusts_backward_luck_cycle_age_with_korean_standard_time_boundary(self) -> None:
        engine = LunarPythonSajuEngine()

        result = engine.calculate(
            corrected_solar_datetime="1988-05-20 10:57:58",
            gender="female",
            tzid="Asia/Seoul",
        )

        self.assertEqual(result.meta["luck_cycle_direction"], "backward")
        self.assertEqual(result.meta["luck_cycle_start_date"], "1988-05-05")
        self.assertEqual(result.luck_cycles[0].start_age, 5)
        self.assertEqual(result.luck_cycles[1].start_age, 15)
        self.assertEqual(result.luck_cycles[0].month_boundary_datetime, "1988-05-05 16:01:43")
        self.assertTrue(4.9 < result.luck_cycles[0].exact_start_age_years < 5.0)

    def test_adjusts_forward_luck_cycle_age_with_korean_standard_time_boundary(self) -> None:
        engine = LunarPythonSajuEngine()

        result = engine.calculate(
            corrected_solar_datetime="1988-12-08 02:27:58",
            gender="male",
            tzid="Asia/Seoul",
        )

        self.assertEqual(result.meta["luck_cycle_direction"], "forward")
        self.assertEqual(result.meta["luck_cycle_start_date"], "1989-01-05")
        self.assertEqual(result.luck_cycles[0].start_age, 9)
        self.assertEqual(result.luck_cycles[1].start_age, 19)
        self.assertEqual(result.luck_cycles[0].month_boundary_datetime, "1989-01-05 17:45:55")
        self.assertTrue(9.5 < result.luck_cycles[0].exact_start_age_years < 9.6)
        self.assertTrue(9.4 < result.luck_cycles[0].precise_start_age_years < 9.5)


if __name__ == "__main__":
    unittest.main()
