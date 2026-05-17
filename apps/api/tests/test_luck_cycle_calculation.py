from datetime import datetime
import unittest

from app.domain.saju.services.calculate_luck_cycles import (
    calculate_luck_cycles,
    get_luck_direction,
)


class LuckCycleCalculationTests(unittest.TestCase):
    def test_direction_uses_gender_and_year_stem_yin_yang_rule(self) -> None:
        self.assertEqual(get_luck_direction("\u4e19", "female"), "backward")
        self.assertEqual(get_luck_direction("\u4e19", "male"), "forward")
        self.assertEqual(get_luck_direction("\u4e01", "female"), "forward")
        self.assertEqual(get_luck_direction("\u4e01", "male"), "backward")

    def test_matches_required_backward_luck_cycle_flow(self) -> None:
        cycles = calculate_luck_cycles(
            gender="female",
            normalized_birth_dt=datetime.strptime("1996-06-19 14:31:00", "%Y-%m-%d %H:%M:%S"),
            year_pillar="\u4e19\u5b50",
            month_pillar="\u7532\u5348",
            day_pillar="\u4e01\u4ea5",
            cycle_count=10,
            target_standard_offset_minutes=540,
        )

        self.assertEqual(cycles[0].direction, "backward")
        self.assertTrue(4.5 < cycles[0].exact_start_age_years < 4.7)
        self.assertEqual(cycles[0].start_age_years, 4)
        self.assertEqual(cycles[0].start_age_months, 6)
        self.assertEqual(cycles[0].start_age_total_months, 54)
        self.assertEqual(cycles[0].change_age_years, 14)
        self.assertEqual(cycles[0].change_age_months, 6)
        self.assertEqual(cycles[0].month_boundary_datetime, "1996-06-05 18:40:47")
        self.assertEqual(
            [(cycle.start_age, cycle.gan_zhi) for cycle in cycles],
            [
                (5, "\u7678\u5df3"),
                (15, "\u58ec\u8fb0"),
                (25, "\u8f9b\u536f"),
                (35, "\u5e9a\u5bc5"),
                (45, "\u5df1\u4e11"),
                (55, "\u620a\u5b50"),
                (65, "\u4e01\u4ea5"),
                (75, "\u4e19\u620c"),
                (85, "\u4e59\u9149"),
                (95, "\u7532\u7533"),
            ],
        )

    def test_forward_flow_starts_from_next_month_pillar(self) -> None:
        cycles = calculate_luck_cycles(
            gender="male",
            normalized_birth_dt=datetime.strptime("2024-02-10 09:57:58", "%Y-%m-%d %H:%M:%S"),
            year_pillar="\u7532\u8fb0",
            month_pillar="\u4e19\u5bc5",
            day_pillar="\u7532\u8fb0",
            cycle_count=3,
            target_standard_offset_minutes=540,
        )

        self.assertEqual(cycles[0].direction, "forward")
        self.assertEqual(cycles[0].gan_zhi, "\u4e01\u536f")
        self.assertEqual(cycles[0].start_age, 8)
        self.assertEqual(cycles[0].start_age_years, 7)
        self.assertEqual(cycles[0].start_age_months, 10)
        self.assertEqual(cycles[0].start_age_total_months, 94)
        self.assertEqual(cycles[1].gan_zhi, "\u620a\u8fb0")
        self.assertEqual(cycles[2].gan_zhi, "\u5df1\u5df3")


if __name__ == "__main__":
    unittest.main()
