import unittest

from app.domain.saju.schemas import SajuPreviewRequest
from app.domain.saju.services.birth_time_policy import resolve_birth_time_policy


class BirthTimePolicyTests(unittest.TestCase):
    def test_estimated_birth_time_hides_hour_pillar_outputs(self) -> None:
        policy = resolve_birth_time_policy(
            SajuPreviewRequest(
                calendar_type="solar",
                birth_date="2024-02-10",
                birth_time="00:00",
                is_birth_time_estimated=True,
                is_lunar_leap_month=False,
                gender="male",
                region_id="kr-seoul",
                debug=False,
            )
        )

        self.assertFalse(policy.hour_pillar_enabled)
        self.assertEqual(policy.effective_birth_time, "00:00")
        self.assertEqual(policy.visible_pillar_keys, ["year", "month", "day"])
        self.assertIn("time_pillar", policy.disabled_sections)

    def test_known_birth_time_keeps_full_visibility(self) -> None:
        policy = resolve_birth_time_policy(
            SajuPreviewRequest(
                calendar_type="solar",
                birth_date="2024-02-10",
                birth_time="10:30",
                is_birth_time_estimated=False,
                is_lunar_leap_month=False,
                gender="male",
                region_id="kr-seoul",
                debug=False,
            )
        )

        self.assertTrue(policy.hour_pillar_enabled)
        self.assertEqual(policy.visible_pillar_keys, ["year", "month", "day", "time"])
        self.assertEqual(policy.disabled_sections, [])


if __name__ == "__main__":
    unittest.main()
