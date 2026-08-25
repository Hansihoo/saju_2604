import unittest
from datetime import datetime

from app.domain.saju.schemas import SajuPreviewRequest
from app.domain.saju.services.build_period_flows import build_period_flows
from app.domain.saju.services.calculate_saju import calculate_saju
from app.domain.saju.services.region_catalog import find_region_by_id


class PeriodFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.region = find_region_by_id("kr-seoul")
        self.payload = SajuPreviewRequest(
            birth_date="1990-01-01",
            birth_time="10:30",
            gender="male",
            region_id="kr-seoul",
            debug=False,
        )
        self.calculation = calculate_saju(
            corrected_solar_datetime="1990-01-01 10:20:00",
            gender="male",
            tzid="Asia/Seoul",
        )

    def test_daily_and_monthly_flow_use_local_calendar_and_solar_term_facts(self) -> None:
        flows = build_period_flows(
            payload=self.payload,
            region=self.region,
            saju_calculation=self.calculation,
            as_of=datetime(2026, 8, 25, 12, 0),
        )

        self.assertEqual(flows.timezone_id, "Asia/Seoul")
        self.assertEqual(flows.today.period_start, "2026-08-25")
        self.assertEqual(flows.today.target_gan_zhi, "辛未")
        self.assertEqual(flows.today.evidence[0].source, "kasi_lunar_reference")
        self.assertEqual(flows.month.period_label, "2026년 8월")
        self.assertEqual(flows.month.target_gan_zhi, "丙申")
        self.assertEqual(flows.month.evidence[0].value, "입추")
        self.assertNotIn("일진", flows.today.summary)
        self.assertNotIn("십성", flows.today.summary)
        self.assertNotIn("절기", flows.month.summary)
        self.assertNotIn("월주", flows.month.summary)
        self.assertTrue(flows.today.notes)
        self.assertTrue(all("점수" not in action for action in flows.today.actions))

    def test_month_flow_changes_at_exact_solar_term_boundary(self) -> None:
        before = build_period_flows(
            payload=self.payload,
            region=self.region,
            saju_calculation=self.calculation,
            as_of=datetime(2026, 9, 7, 23, 40),
        )
        after = build_period_flows(
            payload=self.payload,
            region=self.region,
            saju_calculation=self.calculation,
            as_of=datetime(2026, 9, 7, 23, 42),
        )

        self.assertEqual(before.month.evidence[0].value, "입추")
        self.assertEqual(after.month.evidence[0].value, "백로")
        self.assertNotEqual(before.month.target_gan_zhi, after.month.target_gan_zhi)

    def test_estimated_birth_time_does_not_show_luck_cycle_connection(self) -> None:
        estimated_payload = self.payload.copy(
            update={"is_birth_time_estimated": True, "birth_time": "00:00"}
        )

        flows = build_period_flows(
            payload=estimated_payload,
            region=self.region,
            saju_calculation=self.calculation,
            as_of=datetime(2026, 8, 25, 12, 0),
        )

        self.assertIsNone(flows.month.current_luck_cycle)
        self.assertTrue(any("출생시간 미상" in note for note in flows.month.notes))


if __name__ == "__main__":
    unittest.main()
