import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from app.api.routes import create_saju_preview
from app.domain.saju.pydantic_compat import model_to_dict
from app.domain.saju.schemas import SajuPreviewRequest
from app.domain.saju.services.build_interpretation_payload import build_interpretation_payload


class InterpretationPayloadTests(unittest.TestCase):
    def setUp(self) -> None:
        self._llm_provider_patch = patch(
            "app.domain.saju.services.generate_interpretation.settings.llm_provider",
            "fallback",
        )
        self._llm_provider_patch.start()
        self.addCleanup(self._llm_provider_patch.stop)

    def test_builds_current_flow_and_domain_facts(self) -> None:
        request = SimpleNamespace(
            state=SimpleNamespace(
                trace_id="test-interpretation-payload",
                debug_requested=False,
            )
        )
        preview_request = SajuPreviewRequest(
            locale="ko",
            calendar_type="solar",
            birth_date="1996-06-19",
            birth_time="15:03",
            is_birth_time_estimated=False,
            is_lunar_leap_month=False,
            gender="female",
            region_id="kr-seoul-special",
            debug=False,
        )

        with patch(
            "app.domain.saju.services.build_interpretation_payload._local_today",
            return_value=date(2026, 4, 15),
        ):
            preview_response = create_saju_preview(payload=preview_request, request=request)
            interpretation_payload = build_interpretation_payload(
                request=preview_request,
                response=preview_response,
            )

        self.assertEqual(interpretation_payload.schema_version, "m2-preview-v2")
        self.assertTrue(interpretation_payload.facts_only)
        self.assertEqual(
            interpretation_payload.output_sections,
            ["core_analysis", "love", "career", "wealth", "luck_flow"],
        )
        self.assertEqual(interpretation_payload.profile.locale, "ko")
        self.assertEqual(interpretation_payload.day_master, "정")
        self.assertTrue(all(pillar.display_gan_zhi for pillar in interpretation_payload.visible_pillars))
        self.assertIsNotNone(interpretation_payload.current_flow.active_luck_cycle)
        self.assertEqual(interpretation_payload.current_flow.active_luck_cycle.display_gan_zhi, "신묘")
        self.assertEqual(interpretation_payload.current_flow.next_luck_cycle.display_gan_zhi, "경인")
        self.assertTrue(interpretation_payload.luck_cycle_analysis)
        self.assertTrue(interpretation_payload.luck_flow_facts.current_luck_cycle)
        self.assertTrue(interpretation_payload.luck_flow_facts.current_phase_label)
        self.assertTrue(interpretation_payload.luck_flow_facts.favorable_periods)
        self.assertTrue(interpretation_payload.luck_flow_facts.now_action_tags)
        self.assertEqual(interpretation_payload.love_facts.partner_star_label, "관성")
        self.assertTrue(interpretation_payload.love_facts.active_star_labels)
        self.assertEqual(interpretation_payload.career_facts.month_pillar_label, "월주")
        self.assertTrue(interpretation_payload.career_facts.key_ten_gods)
        self.assertTrue(interpretation_payload.wealth_facts.key_ten_gods)
        serialized_payload = model_to_dict(interpretation_payload)
        for internal_field in (
            "balance_score",
            "charm_score",
            "wealth_score",
            "career_score",
            "leadership_score",
            "internal_grade",
        ):
            self.assertNotIn(internal_field, serialized_payload)
        self.assertIn(
            "Use current_flow for current-period commentary in love, career, wealth, and luck-flow sections.",
            interpretation_payload.narrative_rules,
        )

    def test_english_payload_uses_english_display_fields(self) -> None:
        request = SimpleNamespace(
            state=SimpleNamespace(
                trace_id="test-interpretation-payload-en",
                debug_requested=False,
            )
        )
        preview_request = SajuPreviewRequest(
            locale="en",
            calendar_type="solar",
            birth_date="1996-06-19",
            birth_time="15:03",
            is_birth_time_estimated=False,
            is_lunar_leap_month=False,
            gender="female",
            region_id="kr-seoul-special",
            debug=False,
        )

        with patch(
            "app.domain.saju.services.build_interpretation_payload._local_today",
            return_value=date(2026, 4, 15),
        ):
            preview_response = create_saju_preview(payload=preview_request, request=request)
            interpretation_payload = build_interpretation_payload(
                request=preview_request,
                response=preview_response,
            )

        self.assertEqual(interpretation_payload.profile.locale, "en")
        self.assertEqual(interpretation_payload.day_master, "Jeong")
        self.assertIn("South Korea", interpretation_payload.profile.region_display_name)
        self.assertTrue(all("-" in pillar.display_gan_zhi for pillar in interpretation_payload.visible_pillars))
        self.assertEqual(interpretation_payload.love_facts.partner_star_label, "Officer star")
        self.assertIn("Officer stars", [item.label for item in interpretation_payload.career_facts.key_ten_gods])
        self.assertTrue(interpretation_payload.luck_flow_facts.current_phase_label)
        self.assertTrue(interpretation_payload.luck_flow_facts.favorable_periods)


if __name__ == "__main__":
    unittest.main()
