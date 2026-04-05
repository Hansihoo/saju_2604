import unittest

from app.domain.saju.adapters.lunar_python_engine import LunarPythonSajuEngine


class LunarPythonSajuEngineTests(unittest.TestCase):
    def test_calculates_expected_pillars_and_elements(self) -> None:
        engine = LunarPythonSajuEngine()

        result = engine.calculate(
            normalized_solar_datetime="2024-02-10 10:30:00",
            gender="male",
        )

        self.assertEqual(result.pillars["year"].gan_zhi, "甲辰")
        self.assertEqual(result.pillars["month"].gan_zhi, "丙寅")
        self.assertEqual(result.pillars["day"].gan_zhi, "甲辰")
        self.assertEqual(result.pillars["time"].gan_zhi, "己巳")
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
        self.assertEqual(result.ten_god_stems["time"], "正财")
        self.assertEqual(result.meta["day_master"], "甲")

    def test_returns_decade_luck_cycle_metadata(self) -> None:
        engine = LunarPythonSajuEngine()

        result = engine.calculate(
            normalized_solar_datetime="2024-02-10 10:30:00",
            gender="male",
        )

        self.assertGreaterEqual(len(result.luck_cycles), 2)
        self.assertEqual(result.luck_cycles[1].gan_zhi, "丁卯")
        self.assertEqual(result.luck_cycles[1].start_year, 2032)
        self.assertEqual(result.luck_cycles[1].end_year, 2041)
        self.assertEqual(result.meta["luck_cycle_start_date"], "2032-02-10")


if __name__ == "__main__":
    unittest.main()
