import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.api.routes import create_saju_preview
from app.domain.saju.schemas import SajuPreviewRequest
from app.domain.saju.services.build_interpretation_payload import build_interpretation_payload
from app.domain.saju.services.format_interpretation_fallback import format_interpretation_fallback


class InterpretationFormatterTests(unittest.TestCase):
    def setUp(self) -> None:
        self._llm_provider_patch = patch(
            "app.domain.saju.services.generate_interpretation.settings.llm_provider",
            "fallback",
        )
        self._llm_provider_patch.start()
        self.addCleanup(self._llm_provider_patch.stop)

    def test_formats_korean_interpretation_from_payload(self) -> None:
        request = SimpleNamespace(
            state=SimpleNamespace(
                trace_id="fmt-ko",
                debug_requested=False,
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
            debug=False,
        )

        response = create_saju_preview(payload=payload, request=request)
        interpretation_payload = build_interpretation_payload(request=payload, response=response)
        narrative = format_interpretation_fallback(payload=interpretation_payload, locale="ko")

        self.assertEqual(narrative.locale, "ko")
        self.assertIn("서울특별시", narrative.summary)
        self.assertIn("현재 보이는 오행", narrative.summary)
        self.assertEqual(len(narrative.strengths), 2)
        self.assertEqual(len(narrative.cautions), 2)
        self.assertIn("첫 대운", narrative.action_advice)

    def test_formatter_includes_estimated_time_limitations(self) -> None:
        request = SimpleNamespace(
            state=SimpleNamespace(
                trace_id="fmt-estimated",
                debug_requested=False,
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
            debug=False,
        )

        response = create_saju_preview(payload=payload, request=request)
        interpretation_payload = build_interpretation_payload(request=payload, response=response)
        narrative = format_interpretation_fallback(payload=interpretation_payload, locale="ko")

        self.assertIn("출생시간이 미상", narrative.summary)
        self.assertIn("Birth time is unknown", interpretation_payload.limitations[0])
        self.assertIn("internal placeholder", interpretation_payload.limitations[0])
        self.assertIn("Birth time is unknown", narrative.cautions[1])


if __name__ == "__main__":
    unittest.main()
