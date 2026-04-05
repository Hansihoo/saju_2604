import unittest
from types import SimpleNamespace

from app.api.routes import create_saju_preview
from app.domain.saju.schemas import SajuPreviewRequest


class SajuPreviewPipelineTests(unittest.TestCase):
    def test_preview_pipeline_includes_real_saju_calculation_stage(self) -> None:
        request = SimpleNamespace(
            state=SimpleNamespace(
                trace_id="test-trace",
                debug_requested=True,
            )
        )
        payload = SajuPreviewRequest(
            calendar_type="solar",
            birth_date="2024-02-10",
            birth_time="10:30",
            is_birth_time_estimated=False,
            is_lunar_leap_month=False,
            gender="male",
            region_id="kr-seoul",
            debug=True,
        )

        response = create_saju_preview(payload=payload, request=request)

        self.assertEqual(response.pipeline_status.saju_calculation, "passed")
        self.assertEqual(response.result.evidence_sections["elements"].status, "ready")
        self.assertEqual(response.result.evidence_sections["ten_gods"].status, "ready")
        self.assertEqual(response.debug_trace.checkpoints[4].stage, "saju_calculation")
        self.assertEqual(response.debug_trace.checkpoints[4].status, "passed")
        self.assertEqual(response.debug_trace.checkpoints[5].stage, "analysis_engine")
        self.assertEqual(response.debug_trace.checkpoints[5].status, "passed")
        self.assertIn("Internal grade", response.debug_trace.checkpoints[5].note)
        self.assertIn("甲辰", response.debug_trace.checkpoints[4].note)

    def test_estimated_birth_time_hides_hour_pillar_outputs(self) -> None:
        request = SimpleNamespace(
            state=SimpleNamespace(
                trace_id="test-trace-estimated",
                debug_requested=True,
            )
        )
        payload = SajuPreviewRequest(
            calendar_type="solar",
            birth_date="2024-02-10",
            birth_time="00:00",
            is_birth_time_estimated=True,
            is_lunar_leap_month=False,
            gender="male",
            region_id="kr-seoul",
            debug=True,
        )

        response = create_saju_preview(payload=payload, request=request)

        self.assertFalse(response.result.hour_pillar_enabled)
        self.assertIn("time_pillar", response.result.disabled_sections)
        self.assertEqual(response.result.evidence_sections["luck_cycles"].status, "disabled")
        self.assertEqual(response.pipeline_status.analysis_engine, "passed")
        self.assertIn("hidden by policy", response.debug_trace.checkpoints[4].note)


if __name__ == "__main__":
    unittest.main()
