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


def _first_screen_plain_text(report) -> str:
    chunks = [report.headline, *report.hero_overview]
    for diagnosis in report.core_diagnoses:
        chunks.append(diagnosis.body)
    for card in report.cards:
        chunks.extend(
            [
                card.title,
                card.subtitle,
                *card.chips,
                *card.preview_paragraphs,
                card.user_takeaway,
                card.next_question,
            ]
        )
    return "\n".join(chunks)


class GenerateFreePreviewTests(unittest.TestCase):
    def test_fallback_free_preview_satisfies_schema_and_validation(self) -> None:
        payload = make_payload()
        report = build_fallback_free_preview_report(payload)

        self.assertEqual(report.schema_version, "free-preview-v1")
        self.assertEqual(report.provider, "fallback")
        self.assertEqual(report.prompt_version, "saju-free-preview-v3")
        self.assertEqual(len(report.hero_overview), 8)
        self.assertEqual(
            [item.key for item in report.core_diagnoses],
            ["strongest_point", "repeating_pattern", "current_task"],
        )
        self.assertEqual(
            [card.key for card in report.cards],
            ["core", "work_money", "love", "luck_flow"],
        )
        self.assertEqual(_validate_free_preview_report(report, payload), [])

    def test_fallback_headline_uses_visible_element_signal(self) -> None:
        fire_payload = make_payload()
        water_payload = make_payload()
        water_payload.signals.dominant_elements = ["water"]

        fire_report = build_fallback_free_preview_report(fire_payload)
        water_report = build_fallback_free_preview_report(water_payload)

        self.assertNotEqual(fire_report.headline, water_report.headline)
        self.assertNotIn("혼자 많이 계산", fire_report.headline)
        self.assertNotIn("혼자 많이 계산", water_report.headline)

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
            "무료",
            "甲",
            "乙",
            "丙",
            "丁",
        ):
            self.assertNotIn(forbidden, combined)

    def test_fallback_first_screen_uses_plain_language(self) -> None:
        prompt = get_free_preview_report_prompt()
        report = build_fallback_free_preview_report(make_payload())
        first_screen = _first_screen_plain_text(report)

        for term in prompt.first_screen_jargon_terms:
            self.assertNotIn(term, first_screen)

    def test_fallback_uses_hook_titles_and_limits_abstract_repetition(self) -> None:
        report = build_fallback_free_preview_report(make_payload())
        titles = [card.title for card in report.cards]
        old_titles = [
            "내 사주 특징",
            "일과 돈의 흐름",
            "연애와 결혼 흐름",
            "현재 운과 대운 흐름",
        ]
        hero_and_cards = "\n".join([*report.hero_overview, *titles, *sum((card.preview_paragraphs for card in report.cards), [])])

        for old_title in old_titles:
            self.assertNotIn(old_title, titles)
        self.assertTrue(any("?" in title or "왜" in title or "때입니다" in title for title in titles))
        self.assertLessEqual(hero_and_cards.count("기준"), 4)
        self.assertLessEqual(hero_and_cards.count("흐름"), 4)
        self.assertLessEqual(hero_and_cards.count("정리"), 4)

    def test_basis_line_may_keep_short_technical_basis(self) -> None:
        payload = make_payload()
        report = build_fallback_free_preview_report(payload)
        report.cards[0].basis_line += " 일간 월주 대운 재성 배우자궁 신묘 경인"

        issues = _validate_free_preview_report(report, payload)

        self.assertNotIn("first_screen_jargon:일간", issues)
        self.assertNotIn("first_screen_jargon:대운", issues)
        self.assertNotIn("first_screen_jargon:신묘", issues)

    def test_prompt_spec_describes_free_preview_shape(self) -> None:
        prompt = get_free_preview_report_prompt()

        self.assertEqual(prompt.version, "saju-free-preview-v3")
        self.assertIn("FreePreviewReport", prompt.repair_prompt)
        self.assertIn("hero_overview", prompt.developer_prompt)
        self.assertIn("work_money", prompt.developer_prompt)
        self.assertIn("Korean Hangul only", prompt.developer_prompt)
        self.assertIn("Plain-language first-screen rules", prompt.developer_prompt)
        self.assertIn("무조건", prompt.validation_banned_phrases)
        self.assertIn("무료", prompt.validation_banned_phrases)
        self.assertIn("대운", prompt.first_screen_jargon_terms)
        self.assertIn("기준", prompt.first_screen_abstract_terms)
        self.assertIn("hook-like", prompt.developer_prompt)

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

    def test_validator_blocks_free_word_in_user_text(self) -> None:
        payload = make_payload()
        report = build_fallback_free_preview_report(payload)
        report.cards[0].preview_paragraphs[0] += " 무료로 제공되는 내용입니다."

        issues = _validate_free_preview_report(report, payload)

        self.assertIn("banned_phrase:무료", issues)

    def test_validator_blocks_jargon_in_first_screen_text(self) -> None:
        payload = make_payload()
        report = build_fallback_free_preview_report(payload)
        report.hero_overview[0] += " 현재는 신묘 대운의 영향을 받습니다."
        report.cards[1].preview_paragraphs[0] += " 월주와 재성을 먼저 봅니다."

        issues = _validate_free_preview_report(report, payload)

        self.assertIn("first_screen_jargon:신묘", issues)
        self.assertIn("first_screen_jargon:대운", issues)
        self.assertIn("first_screen_jargon:월주", issues)
        self.assertIn("first_screen_jargon:재성", issues)

    def test_validator_blocks_overused_abstract_terms(self) -> None:
        payload = make_payload()
        report = build_fallback_free_preview_report(payload)
        report.hero_overview = [
            "기준 기준 기준 기준 기준 문장입니다.",
            *report.hero_overview[1:],
        ]
        report.cards[0].preview_paragraphs[0] += " 흐름 흐름 흐름 흐름 흐름"

        issues = _validate_free_preview_report(report, payload)

        self.assertIn("abstract_term_overused:기준", issues)
        self.assertIn("abstract_term_overused:흐름", issues)

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

    def test_codex_provider_uses_codex_path_without_openai_key(self) -> None:
        payload = make_payload()
        codex_report = build_fallback_free_preview_report(payload)
        codex_report.provider = "codex"
        codex_report.model = "codex-cli"
        diagnostics = InterpretationDiagnostics(
            configured_provider="codex",
            final_provider="codex",
            model="codex-cli",
            prompt_version="saju-free-preview-v3",
            payload_chars=123,
            duration_ms=999,
            final_response_id="codex-test",
            attempts=[],
        )

        with patch(
            "app.domain.saju.services.generate_free_preview.settings.llm_provider",
            "codex",
        ), patch(
            "app.domain.saju.services.generate_free_preview.settings.openai_api_key",
            "",
        ), patch(
            "app.domain.saju.services.generate_free_preview._call_openai_free_preview",
            side_effect=AssertionError("OpenAI path must not be called in Codex mode"),
        ), patch(
            "app.domain.saju.services.generate_free_preview._call_codex_free_preview",
            return_value=(codex_report, diagnostics),
        ):
            report = generate_free_preview_report(
                payload=payload,
                trace_id="test-free-preview-codex",
                service_name="suju-insight",
            )

        self.assertEqual(report.provider, "codex")
        self.assertIsNotNone(report.diagnostics)
        self.assertEqual(report.diagnostics.final_provider, "codex")

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
                    prompt_version="saju-free-preview-v3",
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
