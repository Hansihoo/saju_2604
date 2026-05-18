import unittest
from unittest.mock import patch

from app.domain.saju.interpretation import InterpretationDiagnostics
from app.domain.saju.prompts.free_preview_report import get_free_preview_report_prompt
from app.domain.saju.services.generate_free_preview import (
    _validate_free_preview_report,
    build_fallback_free_preview_report,
    generate_free_preview_report,
)
from tests.test_generate_interpretation import make_payload


def _combined_user_text(report) -> str:
    chunks = [report.headline, *report.hero_overview]
    for diagnosis in report.core_diagnoses:
        chunks.extend([diagnosis.title, diagnosis.body])
    for card in report.cards:
        chunks.extend(
            [
                card.title,
                card.subtitle,
                *card.chips,
                *card.preview_paragraphs,
                card.user_takeaway,
                card.next_question,
                card.basis_line,
            ]
        )
    return "\n".join(chunks)


class GenerateFreePreviewTests(unittest.TestCase):
    def test_fallback_free_preview_satisfies_schema_and_validation(self) -> None:
        payload = make_payload()
        report = build_fallback_free_preview_report(payload)

        self.assertEqual(report.schema_version, "free-preview-v1")
        self.assertEqual(report.provider, "fallback")
        self.assertEqual(report.prompt_version, "saju-free-preview-v1")
        self.assertEqual(len(report.hero_overview), 9)
        self.assertEqual(
            [item.key for item in report.core_diagnoses],
            ["strongest_point", "repeating_pattern", "current_task"],
        )
        self.assertEqual(
            [card.key for card in report.cards],
            ["core", "work_money", "love", "luck_flow"],
        )
        self.assertEqual(_validate_free_preview_report(report, payload), [])

    def test_fallback_cards_are_substantial_and_structured(self) -> None:
        report = build_fallback_free_preview_report(make_payload())

        for card in report.cards:
            preview_text = "\n".join(card.preview_paragraphs)
            self.assertGreaterEqual(len(preview_text), 480)
            self.assertGreaterEqual(len(card.chips), 3)
            self.assertGreaterEqual(len(card.preview_paragraphs), 3)
            self.assertTrue(card.user_takeaway)
            self.assertTrue(card.next_question)
            self.assertTrue(card.basis_line)

    def test_fallback_does_not_expose_internal_values_or_hanja(self) -> None:
        report = build_fallback_free_preview_report(make_payload())
        combined = _combined_user_text(report)

        for forbidden in (
            "balance_score",
            "internal_grade",
            "evidence_id",
            "raw evidence",
            "score:",
            "점수:",
            "등급:",
            "100%",
            "甲",
            "乙",
            "丙",
            "丁",
        ):
            self.assertNotIn(forbidden, combined)

    def test_prompt_spec_describes_free_preview_shape(self) -> None:
        prompt = get_free_preview_report_prompt()

        self.assertEqual(prompt.version, "saju-free-preview-v1")
        self.assertIn("FreePreviewReport", prompt.repair_prompt)
        self.assertIn("hero_overview", prompt.developer_prompt)
        self.assertIn("work_money", prompt.developer_prompt)
        self.assertIn("Korean Hangul only", prompt.developer_prompt)
        self.assertIn("무조건", prompt.validation_banned_phrases)

    def test_validator_blocks_generic_headline(self) -> None:
        payload = make_payload()
        report = build_fallback_free_preview_report(payload)
        report.headline = "핵심 요약"

        issues = _validate_free_preview_report(report, payload)

        self.assertIn("headline:generic", issues)

    def test_validator_blocks_internal_values(self) -> None:
        payload = make_payload()
        report = build_fallback_free_preview_report(payload)
        report.cards[0].preview_paragraphs[0] += " balance_score: 57 internal_grade: B evidence_id: debug"

        issues = _validate_free_preview_report(report, payload)

        self.assertIn("internal_value_exposed_in_user_text", issues)

    def test_validator_blocks_banned_phrases(self) -> None:
        payload = make_payload()
        report = build_fallback_free_preview_report(payload)
        report.cards[2].preview_paragraphs[0] += " 이 관계는 반드시 결혼한다."

        issues = _validate_free_preview_report(report, payload)

        self.assertIn("banned_phrase:반드시", issues)
        self.assertIn("banned_phrase:결혼한다", issues)

    def test_validator_blocks_hanja_in_korean_output(self) -> None:
        payload = make_payload(locale="ko")
        report = build_fallback_free_preview_report(payload)
        report.hero_overview[0] += " 甲"

        issues = _validate_free_preview_report(report, payload)

        self.assertIn("language:contains_hanja", issues)

    def test_validator_blocks_short_card_preview(self) -> None:
        payload = make_payload()
        report = build_fallback_free_preview_report(payload)
        report.cards[0].preview_paragraphs = ["짧은 문단입니다.", "짧습니다.", "짧습니다."]

        issues = _validate_free_preview_report(report, payload)

        self.assertIn("cards.core:preview_too_short", issues)

    def test_fallback_provider_does_not_call_openai_path(self) -> None:
        payload = make_payload()
        with patch(
            "app.domain.saju.services.generate_free_preview.settings.llm_provider",
            "fallback",
        ), patch(
            "app.domain.saju.services.generate_free_preview._call_openai_free_preview",
            side_effect=AssertionError("OpenAI path must not be called in fallback mode"),
        ):
            report = generate_free_preview_report(
                payload=payload,
                trace_id="test-free-preview-no-openai",
                service_name="suju-insight",
            )

        self.assertEqual(report.provider, "fallback")
        self.assertIsNotNone(report.diagnostics)
        self.assertEqual(report.diagnostics.fallback_reason, "provider_not_openai")

    def test_generate_free_preview_falls_back_when_validation_fails(self) -> None:
        payload = make_payload()
        invalid_report = build_fallback_free_preview_report(payload)
        invalid_report.headline = "핵심 요약"

        with patch(
            "app.domain.saju.services.generate_free_preview._call_openai_free_preview",
            return_value=(
                invalid_report,
                InterpretationDiagnostics(
                    configured_provider="openai",
                    final_provider="openai",
                    model="gpt-5.4-mini",
                    prompt_version="saju-free-preview-v1",
                    payload_chars=123,
                    duration_ms=999,
                    final_response_id="resp_test",
                    attempts=[],
                ),
            ),
        ), patch(
            "app.domain.saju.services.generate_free_preview.settings.llm_provider",
            "openai",
        ), patch(
            "app.domain.saju.services.generate_free_preview.settings.openai_api_key",
            "test-key",
        ):
            report = generate_free_preview_report(
                payload=payload,
                trace_id="test-free-preview-validation",
                service_name="suju-insight",
            )

        self.assertEqual(report.provider, "fallback")
        self.assertIn("headline:generic", report.warnings)
        self.assertIsNotNone(report.diagnostics)
        self.assertEqual(report.diagnostics.fallback_reason, "validation_failed")


if __name__ == "__main__":
    unittest.main()
