import unittest
from types import SimpleNamespace

from app.api.routes import create_saju_preview
from app.domain.saju.schemas import SajuPreviewRequest
from app.domain.saju.services.build_interpretation_payload import build_interpretation_payload


class InterpretationPayloadTests(unittest.TestCase):
    def test_builds_facts_only_payload_from_preview_response(self) -> None:
        request = SimpleNamespace(
            state=SimpleNamespace(
                trace_id="test-interpretation-payload",
                debug_requested=False,
            )
        )
        preview_request = SajuPreviewRequest(
            calendar_type="solar",
            birth_date="2024-02-10",
            birth_time="10:30",
            is_birth_time_estimated=False,
            is_lunar_leap_month=False,
            gender="male",
            region_id="kr-seoul",
            debug=False,
        )

        preview_response = create_saju_preview(payload=preview_request, request=request)
        interpretation_payload = build_interpretation_payload(
            request=preview_request,
            response=preview_response,
        )

        self.assertEqual(interpretation_payload.schema_version, "m2-preview-v1")
        self.assertTrue(interpretation_payload.facts_only)
        self.assertEqual(
            interpretation_payload.output_sections,
            ["summary", "strengths", "cautions", "love", "career", "wealth", "action_advice"],
        )
        self.assertEqual(interpretation_payload.profile.region_display_name, "서울특별시")
        self.assertEqual(interpretation_payload.time_context.corrected_solar_datetime, "2024-02-10 09:57:58")
        self.assertEqual(
            [pillar.gan_zhi for pillar in interpretation_payload.visible_pillars],
            ["甲辰", "丙寅", "甲辰", "己巳"],
        )
        self.assertEqual(interpretation_payload.day_master, "甲")
        self.assertEqual(interpretation_payload.element_counts["wood"], 3)
        self.assertEqual(interpretation_payload.signals.internal_grade, "B")
        self.assertEqual(interpretation_payload.signals.missing_elements, ["metal", "water"])
        self.assertEqual(interpretation_payload.luck_cycles[0].gan_zhi, "丁卯")
        self.assertEqual(interpretation_payload.supplementary_positions[0].gan_zhi, "丁巳")
        self.assertEqual(
            interpretation_payload.narrative_rules[0],
            "Use only the provided facts and signals.",
        )

    def test_payload_preserves_estimated_time_limitations(self) -> None:
        request = SimpleNamespace(
            state=SimpleNamespace(
                trace_id="test-interpretation-payload-estimated",
                debug_requested=False,
            )
        )
        preview_request = SajuPreviewRequest(
            calendar_type="solar",
            birth_date="2024-02-10",
            birth_time="00:00",
            is_birth_time_estimated=True,
            is_lunar_leap_month=False,
            gender="male",
            region_id="kr-seoul",
            debug=False,
        )

        preview_response = create_saju_preview(payload=preview_request, request=request)
        interpretation_payload = build_interpretation_payload(
            request=preview_request,
            response=preview_response,
        )

        self.assertTrue(interpretation_payload.profile.is_birth_time_estimated)
        self.assertIn("time_pillar", interpretation_payload.disabled_sections)
        self.assertEqual(interpretation_payload.luck_cycles, [])
        self.assertTrue(any("estimated" in limitation.lower() for limitation in interpretation_payload.limitations))


if __name__ == "__main__":
    unittest.main()
