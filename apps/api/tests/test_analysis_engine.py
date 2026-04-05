import unittest

from app.domain.saju.adapters.lunar_python_engine import LunarPythonSajuEngine
from app.domain.saju.services.analyze_saju import analyze_saju


class AnalysisEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = LunarPythonSajuEngine()
        self.saju_calculation = engine.calculate(
            normalized_solar_datetime="2024-02-10 10:30:00",
            gender="male",
        )

    def test_analyzes_full_visible_pillars(self) -> None:
        result = analyze_saju(
            saju_calculation=self.saju_calculation,
            visible_pillar_keys=["year", "month", "day", "time"],
        )

        self.assertEqual(
            result.visible_element_counts,
            {
                "wood": 3,
                "fire": 2,
                "earth": 3,
                "metal": 0,
                "water": 0,
            },
        )
        self.assertEqual(result.internal_grade, "B")
        self.assertEqual(result.balance_score, 35)
        self.assertEqual(result.charm_score, 52)
        self.assertEqual(result.wealth_score, 60)
        self.assertEqual(result.career_score, 78)
        self.assertEqual(result.leadership_score, 69)

    def test_analyzes_without_time_pillar_when_estimated(self) -> None:
        result = analyze_saju(
            saju_calculation=self.saju_calculation,
            visible_pillar_keys=["year", "month", "day"],
        )

        self.assertEqual(
            result.visible_element_counts,
            {
                "wood": 3,
                "fire": 1,
                "earth": 2,
                "metal": 0,
                "water": 0,
            },
        )
        self.assertEqual(result.internal_grade, "B")
        self.assertEqual(result.charm_score, 47)
        self.assertEqual(result.wealth_score, 53)


if __name__ == "__main__":
    unittest.main()
