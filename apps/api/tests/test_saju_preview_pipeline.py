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
        self.assertEqual(response.pipeline_status.regional_solar_correction, "passed")
        self.assertEqual(response.result.evidence_sections["elements"].status, "ready")
        self.assertEqual(response.result.evidence_sections["ten_gods"].status, "ready")
        self.assertEqual(response.debug_trace.checkpoints[4].stage, "regional_solar_correction")
        self.assertEqual(response.debug_trace.checkpoints[4].status, "passed")
        self.assertEqual(response.debug_trace.checkpoints[5].stage, "saju_calculation")
        self.assertEqual(response.debug_trace.checkpoints[5].status, "passed")
        self.assertEqual(response.debug_trace.checkpoints[6].stage, "analysis_engine")
        self.assertEqual(response.debug_trace.checkpoints[6].status, "passed")
        self.assertIn("Internal grade", response.debug_trace.checkpoints[6].note)
        self.assertIn("\u7532\u8fb0", response.debug_trace.checkpoints[5].note)
        self.assertEqual(response.region.longitude, 126.991824)
        self.assertEqual(response.regional_solar_correction.corrected_solar_datetime, "2024-02-10 09:57:58")

    def test_preview_pipeline_includes_core_manse_data(self) -> None:
        request = SimpleNamespace(
            state=SimpleNamespace(
                trace_id="test-trace-manse",
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

        self.assertEqual(response.manse.meta.day_master, "\u7532")
        self.assertEqual(response.manse.meta.schema_version, "v1")
        self.assertTrue(response.manse.meta.hour_pillar_enabled)
        self.assertEqual(response.manse.elements.wood, 3)
        self.assertEqual(response.manse.pillars.time.twelve_fortune, "\u75c5")
        self.assertEqual(response.manse.pillars.day.twelve_shinsal, "\ud654\uac1c")
        self.assertEqual(response.manse.table_rows[0].label, "\ucc9c\uac04")
        self.assertEqual(response.manse.table_rows[4].label, "\uc9c0\uc7a5\uac04")
        self.assertEqual(response.manse.table_rows[6].label, "12\uc2e0\uc0b4")
        self.assertEqual(
            response.manse.supplementary_positions.tai_yuan.gan_zhi,
            "\u4e01\u5df3",
        )
        self.assertGreaterEqual(len(response.manse.luck_cycles), 2)

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
        self.assertIn("hidden by policy", response.debug_trace.checkpoints[5].note)
        self.assertFalse(response.manse.meta.hour_pillar_enabled)
        self.assertFalse(response.manse.pillars.time.enabled)
        self.assertEqual(response.manse.table_rows[0].time, "")
        self.assertEqual(response.manse.table_rows[6].time, "")
        self.assertEqual(response.manse.luck_cycles, [])
        self.assertEqual(
            response.manse.notes,
            ["\ucd9c\uc0dd\uc2dc\uac04 \ubbf8\uc0c1\uc73c\ub85c \uc2dc\uc8fc\uc640 \uc2dc\uc8fc \uae30\ubc18 \ub300\uc6b4 \uc815\ubcf4\ub294 \ube44\ud65c\uc131\ud654\ub418\uc5c8\uc2b5\ub2c8\ub2e4."],
        )


if __name__ == "__main__":
    unittest.main()
