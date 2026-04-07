import unittest

from app.domain.saju.adapters.lunar_python_engine import LunarPythonSajuEngine


class LunarPythonSajuEngineTests(unittest.TestCase):
    def test_calculates_expected_pillars_and_elements(self) -> None:
        engine = LunarPythonSajuEngine()

        result = engine.calculate(
            corrected_solar_datetime="2024-02-10 10:30:00",
            gender="male",
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
        )

        self.assertGreaterEqual(len(result.luck_cycles), 2)
        self.assertEqual(result.luck_cycles[1].gan_zhi, "\u4e01\u536f")
        self.assertEqual(result.luck_cycles[1].start_year, 2032)
        self.assertEqual(result.luck_cycles[1].end_year, 2041)
        self.assertEqual(result.meta["luck_cycle_start_date"], "2032-02-10")

    def test_returns_supplementary_positions_for_manse_scope(self) -> None:
        engine = LunarPythonSajuEngine()

        result = engine.calculate(
            corrected_solar_datetime="2024-02-10 10:30:00",
            gender="male",
        )

        self.assertEqual(result.supplementary_positions["tai_yuan"].gan_zhi, "\u4e01\u5df3")
        self.assertEqual(result.supplementary_positions["ming_gong"].gan_zhi, "\u7532\u620c")
        self.assertEqual(result.supplementary_positions["shen_gong"].gan_zhi, "\u58ec\u7533")
        self.assertEqual(result.supplementary_positions["tai_xi"].gan_zhi, "\u5df1\u9149")


if __name__ == "__main__":
    unittest.main()
