import asyncio
import json
import unittest
from unittest.mock import patch

from fastapi.routing import APIRoute, serialize_response

from app.domain.saju.interpretation import (
    FreePreviewLLMOutput,
    FreePreviewReport,
    InterpretationDiagnostics,
)
from app.domain.saju.llm_payload import InterpretationUncertaintyFlag
from app.domain.saju.localization import TEN_GOD_ENGLISH
from app.domain.saju.pydantic_compat import model_to_dict, model_validate_compat
from app.domain.saju.prompts.free_preview_report import get_free_preview_report_prompt
from app.domain.saju.schemas import SajuPreviewRequest, SajuPreviewResponse
from app.domain.saju.services.generate_free_preview import (
    _attach_diagnostics,
    _build_provider_report,
    _model_json_schema,
    _parse_free_preview_output,
    _validate_free_preview_report,
    build_fallback_free_preview_report,
    generate_free_preview_report,
)
from app.domain.saju.services.preview_orchestrator import create_saju_preview_response
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
        if card.basis_explanation:
            chunks.extend([*card.basis_explanation.facts, card.basis_explanation.reading])
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
    def test_basis_explanations_connect_supplied_labels_to_existing_reading_themes(self) -> None:
        for locale in ("ko", "en"):
            for label in (label for label in TEN_GOD_ENGLISH if label != "일간"):
                with self.subTest(locale=locale, label=label):
                    payload = make_payload(locale=locale)
                    supplied = label if locale == "ko" else TEN_GOD_ENGLISH[label]
                    payload.career_facts.month_stem_ten_god = supplied
                    payload.love_facts.spouse_house_ten_god = supplied
                    report = build_fallback_free_preview_report(payload)
                    for card in report.cards[1:3]:
                        explanation = card.basis_explanation
                        self.assertIsNotNone(explanation)
                        self.assertIn(supplied, explanation.facts[0])
                        self.assertIn(supplied, explanation.reading)
                        self.assertEqual(len(explanation.facts), 1)
                        reference = ("월간 십성" if card.key == "work_money" else "배우자궁") if locale == "ko" else ("month-stem ten-god" if card.key == "work_money" else "spouse-house ten-god")
                        self.assertIn(reference, explanation.reading)
                        self.assertIn("해석 방향을 검토했습니다" if locale == "ko" else "The interpretation considers", explanation.reading)
                        self.assertNotIn("관계 정리" if locale == "ko" else "relationship cleanup", " ".join(explanation.facts))
                    self.assertEqual(_validate_free_preview_report(report, payload), [])

    def test_core_basis_uses_actual_counts_and_does_not_invent_missing_elements(self) -> None:
        for locale in ("ko", "en"):
            with self.subTest(locale=locale):
                payload = make_payload(locale=locale)
                payload.signals.dominant_elements = ["earth"]
                payload.element_counts["earth"] = 4
                payload.signals.missing_elements = ["wood"]
                payload.element_counts["wood"] = 0
                card = build_fallback_free_preview_report(payload).cards[0]
                self.assertIn("토 4개" if locale == "ko" else "earth 4", card.basis_explanation.facts[0])
                self.assertIn("목 0개" if locale == "ko" else "wood 0", card.basis_explanation.facts[0])
                self.assertIn("토" if locale == "ko" else "Earth", card.basis_explanation.facts[1])
                self.assertNotIn("부족" if locale == "ko" else "missing", card.basis_explanation.reading)
                self.assertNotIn("목를", card.basis_line)
                self.assertNotIn("금를", card.basis_line)
                payload.element_counts["wood"] = 1
                explanation = build_fallback_free_preview_report(payload).cards[0].basis_explanation
                self.assertEqual(len(explanation.facts), 2)
                self.assertIn("목 1개" if locale == "ko" else "wood 1", explanation.facts[0])
                self.assertNotIn("확인되지 않은 항목" if locale == "ko" else "Elements absent", explanation.reading)

    def test_unconfirmed_luck_basis_omits_stale_cycles_dates_and_action_tags(self) -> None:
        for locale in ("ko", "en"):
            for state in ("estimated", "disabled", "missing"):
                with self.subTest(locale=locale, state=state):
                    payload = make_payload(locale=locale, estimated=state == "estimated")
                    if state == "disabled":
                        payload.disabled_sections = ["luck_cycles"]
                    elif state == "missing":
                        payload.current_flow.active_luck_cycle = None
                    payload.luck_flow_facts.current_luck_cycle = "STALE_CURRENT"
                    payload.luck_flow_facts.next_luck_cycle = "STALE_NEXT"
                    payload.luck_flow_facts.current_period = "1900-1910"
                    payload.luck_flow_facts.next_period = "1910-1920"
                    payload.luck_flow_facts.now_action_tags = ["STALE_ACTION"]
                    basis = build_fallback_free_preview_report(payload).cards[3].basis_explanation
                    combined = " ".join([*basis.facts, basis.reading])
                    for value in ("STALE_CURRENT", "STALE_NEXT", "STALE_ACTION", "1900", "1910", "1920", "2020", "2030"):
                        self.assertNotIn(value, combined)
                    self.assertIn("생활 점검 항목" if locale == "ko" else "everyday checks", basis.reading)
                    self.assertIn("시기 비교를 보류했습니다" if locale == "ko" else "timing comparison was withheld", basis.reading)
                    self.assertNotIn("첫 대운" if locale == "ko" else "first cycle", combined)

    def test_known_luck_basis_uses_actual_cycle_objects_and_withholds_missing_next(self) -> None:
        for locale in ("ko", "en"):
            with self.subTest(locale=locale):
                payload = make_payload(locale=locale)
                payload.luck_flow_facts.current_luck_cycle = "STALE_CURRENT"
                payload.luck_flow_facts.next_luck_cycle = "STALE_NEXT"
                payload.luck_flow_facts.current_period = "1900-1910"
                payload.luck_flow_facts.next_period = "1910-1920"
                basis = build_fallback_free_preview_report(payload).cards[3].basis_explanation
                self.assertIn(payload.current_flow.active_luck_cycle.display_gan_zhi, basis.facts[0])
                self.assertIn(payload.current_flow.next_luck_cycle.display_gan_zhi, basis.facts[1])
                self.assertIn("2020", basis.facts[0])
                self.assertIn("2030", basis.facts[1])
                self.assertNotIn("STALE", " ".join(basis.facts))
                payload.current_flow.next_luck_cycle = None
                basis = build_fallback_free_preview_report(payload).cards[3].basis_explanation
                self.assertIn("미확인" if locale == "ko" else "unavailable", basis.facts[1])
                self.assertIn("보류" if locale == "ko" else "withheld", basis.reading)

    def test_analysis_notes_use_professional_copy_without_changing_fact_sources(self) -> None:
        for locale in ("ko", "en"):
            for estimated in (False, True):
                with self.subTest(locale=locale, estimated=estimated):
                    payload = make_payload(locale=locale, estimated=estimated)
                    report = build_fallback_free_preview_report(payload)
                    for card in report.cards:
                        basis = card.basis_explanation
                        self.assertIsNotNone(basis)
                        self.assertLessEqual(len(basis.reading), 360)
                        for casual in ("읽었어", "살펴봤어", "연결했어", "남겼어", "보류했어", "frames a question"):
                            self.assertNotIn(casual, basis.reading)
                    if locale == "ko":
                        self.assertIn("보이는 오행의 최다 항목", report.cards[0].basis_explanation.reading)
                        if estimated:
                            self.assertIn("출생시간 미상: 시주 제외", report.cards[0].basis_explanation.facts)
                        self.assertIn("월간 십성", report.cards[1].basis_explanation.reading)
                        self.assertIn("배우자궁", report.cards[2].basis_explanation.reading)
                        self.assertIn("대운", report.cards[3].basis_explanation.reading)
                    self.assertEqual(_validate_free_preview_report(report, payload), [])

    def test_unsupported_card_signals_leave_optional_explanation_empty(self) -> None:
        for locale in ("ko", "en"):
            with self.subTest(locale=locale):
                payload = make_payload(locale=locale)
                payload.career_facts.month_stem_ten_god = "UNSUPPORTED"
                payload.love_facts.spouse_house_ten_god = "UNSUPPORTED"
                payload.signals.dominant_elements = []
                report = build_fallback_free_preview_report(payload)
                self.assertTrue(all(card.basis_explanation is None for card in report.cards[:3]))
                self.assertTrue(all(card.basis_line for card in report.cards[:3]))

    def test_provider_schema_and_parser_do_not_accept_generated_basis_facts(self) -> None:
        report = build_fallback_free_preview_report(make_payload())
        data = model_to_dict(report, mode="json")
        for card in data["cards"]:
            card["basis_explanation"] = {"facts": ["FABRICATED_PARTNER_FEELING"], "reading": "UNVERIFIED_PREDICTION"}
        self.assertNotIn("basis_explanation", json.dumps(_model_json_schema(FreePreviewLLMOutput)))
        parsed = _parse_free_preview_output(json.dumps(data, ensure_ascii=False))
        for provider in ("openai", "codex"):
            provider_report = _build_provider_report(parsed, provider=provider)
            self.assertTrue(all(card.basis_explanation is None for card in provider_report.cards))
            self.assertNotIn("FABRICATED", json.dumps(model_to_dict(provider_report)))
            attached = _attach_diagnostics(report, InterpretationDiagnostics(
                configured_provider=provider, final_provider=provider, payload_chars=1,
                duration_ms=1, prompt_version="saju-free-preview-v4", attempts=[],
            ), provider=provider)
            self.assertTrue(all(card.basis_explanation is None for card in attached.cards))
            self.assertEqual([card.basis_line for card in attached.cards], [card.basis_line for card in report.cards])
        self.assertTrue(all(card.basis_explanation is not None for card in report.cards))

    def test_legacy_preview_without_basis_explanation_still_validates(self) -> None:
        data = model_to_dict(build_fallback_free_preview_report(make_payload()), mode="json")
        for card in data["cards"]:
            card.pop("basis_explanation")
        restored = model_validate_compat(FreePreviewReport, data)
        self.assertTrue(all(card.basis_explanation is None for card in restored.cards))

    def _serialize_public_preview(self, response):
        from app.api.routes import router

        route = next(route for route in router.routes if isinstance(route, APIRoute) and route.path == "/saju/preview")
        return asyncio.run(serialize_response(
            field=route.response_field,
            response_content=response,
            include=route.response_model_include,
            exclude=route.response_model_exclude,
            by_alias=route.response_model_by_alias,
            exclude_unset=route.response_model_exclude_unset,
            exclude_defaults=route.response_model_exclude_defaults,
            exclude_none=route.response_model_exclude_none,
        ))

    def _calculated_preview_response(self, *, locale="ko", estimated=False, report_mode="free_preview"):
        request = SajuPreviewRequest(
            locale=locale,
            calendar_type="solar",
            birth_date="1997-09-18",
            birth_time="00:00" if estimated else "14:30",
            is_birth_time_estimated=estimated,
            gender="female",
            region_id="kr-seoul-special",
        )
        with patch("app.domain.saju.services.generate_free_preview.settings.llm_provider", "fallback"):
            return create_saju_preview_response(
                payload=request,
                trace_id="test-free-preview-public-serialization",
                debug_requested=False,
                service_name="suju-insight",
                report_mode=report_mode,
            )

    def test_all_fact_variants_round_trip_through_public_response_schema(self) -> None:
        # Revalidate plain dictionaries, as the response serializer does. Passing
        # existing Pydantic objects alone can miss fields mutated after creation.
        public_response = self._calculated_preview_response(report_mode="none")
        response_dict = model_to_dict(public_response, mode="json")
        labels = [*TEN_GOD_ENGLISH, ""]
        for locale in ("ko", "en"):
            for label in labels:
                for state in ("known", "estimated", "missing", "disabled", "empty"):
                    with self.subTest(locale=locale, label=label, state=state):
                        payload = make_payload(locale=locale, estimated=state == "estimated")
                        supplied_label = label if locale == "ko" else TEN_GOD_ENGLISH.get(label, "")
                        payload.career_facts.month_stem_ten_god = supplied_label
                        payload.love_facts.spouse_house_ten_god = supplied_label
                        # Exercise the longest localized supporting labels and
                        # maximum visible-pillar counts, including basis_line.
                        payload.love_facts.active_star_labels = (
                            ["왕지도화", "함지도화", "목욕도화", "도화"] if locale == "ko" else
                            ["Wangji Peach Blossom", "Hamji Peach Blossom", "Bath Peach Blossom", "Peach Blossom"]
                        )
                        payload.love_facts.partner_star_count = 8
                        for metric in [*payload.career_facts.key_ten_gods, *payload.wealth_facts.key_ten_gods]:
                            metric.count = 8
                        if state == "missing":
                            payload.current_flow.active_luck_cycle = None
                            payload.current_flow.next_luck_cycle = None
                        elif state == "disabled":
                            payload.disabled_sections = ["luck_cycles"]
                        elif state == "empty":
                            payload.signals.dominant_elements = []
                            payload.signals.missing_elements = []
                            payload.career_facts.key_ten_gods = []
                            payload.wealth_facts.key_ten_gods = []
                            payload.love_facts.partner_star_count = 0
                            payload.love_facts.active_star_labels = []
                        report = build_fallback_free_preview_report(payload)
                        response_dict["result"]["free_preview"] = model_to_dict(report, mode="json")
                        validated = model_validate_compat(SajuPreviewResponse, response_dict)
                        self.assertEqual(validated.result.free_preview, report)
                        response_body = self._serialize_public_preview(response_dict)
                        serialized = json.dumps(response_body, ensure_ascii=False)
                        restored = model_validate_compat(SajuPreviewResponse, json.loads(serialized))
                        self.assertEqual(restored.result.free_preview, report)

    def test_calculated_known_and_unknown_previews_serialize_in_both_locales(self) -> None:
        for locale in ("ko", "en"):
            for estimated in (False, True):
                with self.subTest(locale=locale, estimated=estimated):
                    response = self._calculated_preview_response(locale=locale, estimated=estimated)
                    report = response.result.free_preview
                    self.assertIsNotNone(report)
                    self.assertEqual(report.provider, "fallback")
                    self.assertEqual(response.pipeline_status.saju_calculation, "passed")
                    self.assertEqual(len(report.cards), 4)
                    validated = model_validate_compat(SajuPreviewResponse, model_to_dict(response, mode="json"))
                    self.assertEqual(validated.result.free_preview, report)
                    response_body = self._serialize_public_preview(response)
                    serialized = json.dumps(response_body, ensure_ascii=False)
                    restored = model_validate_compat(SajuPreviewResponse, json.loads(serialized))
                    self.assertEqual(restored.result.free_preview, report)
                    self.assertEqual(restored.manse.meta.hour_pillar_enabled, not estimated)

    def test_contrasting_supplied_facts_change_topic_headlines_and_share_takeaways(self) -> None:
        for locale in ("ko", "en"):
            with self.subTest(locale=locale):
                first = make_payload(locale=locale)
                second = make_payload(locale=locale)
                second.signals.dominant_elements = ["water"]
                second.element_counts["water"] = 4
                second.signals.missing_elements = ["fire"]
                second.career_facts.month_stem_ten_god = "정인" if locale == "ko" else "Direct Resource"
                second.love_facts.spouse_house_ten_god = "비견" if locale == "ko" else "Peer"
                second.love_facts.partner_star_count = 0
                second.love_facts.active_star_labels = []
                for metric in second.wealth_facts.key_ten_gods:
                    metric.count = 0
                first.luck_flow_facts.now_action_tags = ["문서 작성" if locale == "ko" else "write a document"]
                second.luck_flow_facts.now_action_tags = ["역할 조정" if locale == "ko" else "adjust task ownership"]
                first_report = build_fallback_free_preview_report(first)
                second_report = build_fallback_free_preview_report(second)
                self.assertNotEqual(first_report.headline, second_report.headline)
                for first_card, second_card in zip(first_report.cards, second_report.cards):
                    self.assertNotEqual(first_card.user_takeaway, second_card.user_takeaway, first_card.key)
                    if first_card.key in {"love", "work_money"}:
                        self.assertNotEqual(first_card.subtitle, second_card.subtitle)
                        self.assertNotEqual(first_card.preview_paragraphs[0], second_card.preview_paragraphs[0])
                        self.assertNotEqual(first_card.preview_paragraphs[1], second_card.preview_paragraphs[1])
                        self.assertNotEqual(first_card.basis_line, second_card.basis_line)
                self.assertEqual(_validate_free_preview_report(first_report, first), [])
                self.assertEqual(_validate_free_preview_report(second_report, second), [])

    def test_date_and_gender_strings_alone_do_not_fabricate_personalization(self) -> None:
        first = make_payload()
        second = make_payload()
        second.profile.birth_date = "1980-01-02"
        second.profile.birth_time = "03:30"
        second.profile.gender = "male"
        first_report = build_fallback_free_preview_report(first)
        second_report = build_fallback_free_preview_report(second)
        self.assertEqual(first_report.cards, second_report.cards)

    def test_all_known_ten_god_categories_render_plain_language_in_both_locales(self) -> None:
        for locale in ("ko", "en"):
            for label in ("비견", "식신", "편재", "정관", "정인"):
                with self.subTest(locale=locale, label=label):
                    payload = make_payload(locale=locale)
                    supplied_label = label if locale == "ko" else TEN_GOD_ENGLISH[label]
                    payload.career_facts.month_stem_ten_god = supplied_label
                    payload.love_facts.spouse_house_ten_god = supplied_label
                    report = build_fallback_free_preview_report(payload)
                    self.assertEqual(_validate_free_preview_report(report, payload), [])
                    self.assertIn(supplied_label, report.cards[1].basis_line)
                    self.assertIn(supplied_label, report.cards[2].basis_line)

    def test_empty_and_zero_counts_remain_unconfirmed_without_negative_prediction(self) -> None:
        for locale in ("ko", "en"):
            for empty_metrics in (False, True):
                with self.subTest(locale=locale, empty_metrics=empty_metrics):
                    payload = make_payload(locale=locale)
                    payload.signals.dominant_elements = []
                    payload.signals.missing_elements = []
                    payload.career_facts.month_stem_ten_god = ""
                    payload.love_facts.spouse_house_ten_god = ""
                    payload.love_facts.partner_star_count = 0
                    payload.love_facts.active_star_labels = []
                    if empty_metrics:
                        payload.career_facts.key_ten_gods = []
                        payload.wealth_facts.key_ten_gods = []
                    else:
                        for metric in [*payload.career_facts.key_ten_gods, *payload.wealth_facts.key_ten_gods]:
                            metric.count = 0
                    report = build_fallback_free_preview_report(payload)
                    self.assertEqual(_validate_free_preview_report(report, payload), [])
                    self.assertIn("못 벌" if locale == "ko" else "does not mean", report.cards[1].preview_paragraphs[1])
                    self.assertIn("뜻으로 읽지는" if locale == "ko" else "does not mean", report.cards[2].preview_paragraphs[1])
                    self.assertNotIn("도화" if locale == "ko" else "Peach Blossom", report.cards[2].basis_line)

    def test_estimated_or_missing_current_cycle_does_not_leak_stale_timing(self) -> None:
        for locale in ("ko", "en"):
            for estimated in (False, True):
                with self.subTest(locale=locale, estimated=estimated):
                    payload = make_payload(locale=locale, estimated=estimated)
                    if not estimated:
                        payload.current_flow.active_luck_cycle = None
                        payload.current_flow.next_luck_cycle = None
                    payload.luck_flow_facts.current_luck_cycle = "STALE_CURRENT"
                    payload.luck_flow_facts.next_luck_cycle = "STALE_NEXT"
                    payload.luck_flow_facts.current_period = "1900-1910"
                    payload.luck_flow_facts.next_period = "1910-1920"
                    payload.luck_flow_facts.now_action_tags = ["STALE_ACTION"]
                    report = build_fallback_free_preview_report(payload)
                    combined = _combined_user_text(report)
                    for value in ("STALE_CURRENT", "STALE_NEXT", "STALE_ACTION", "1900-1910", "1910-1920"):
                        self.assertNotIn(value, combined)
                    self.assertIn("확정하지" if locale == "ko" else "unconfirmed", report.cards[3].basis_line)
                    self.assertEqual(_validate_free_preview_report(report, payload), [])

    def test_provider_diagnostics_preserve_calculated_uncertainty_warnings(self) -> None:
        payload = make_payload(estimated=True)
        payload.uncertainty_summary = [InterpretationUncertaintyFlag(
            code="day_pillar_uncertain_due_to_unknown_time",
            severity="critical",
            affected_fields=["day_pillar"],
            user_message="Day pillar is unconfirmed.",
        )]
        with patch("app.domain.saju.services.generate_free_preview.settings.llm_provider", "fallback"):
            report = generate_free_preview_report(payload=payload, trace_id="test-free-preview-uncertainty", service_name="suju-insight")
        self.assertEqual(report.warnings, ["day_pillar_uncertain_due_to_unknown_time", "llm_provider_disabled"])

    def test_untranslated_auxiliary_labels_do_not_break_requested_language(self) -> None:
        payload = make_payload(locale="en")
        payload.love_facts.active_star_labels = ["Peach Blossom", "함지도화", "桃花"]
        report = build_fallback_free_preview_report(payload)
        self.assertIn(payload.love_facts.spouse_house_ten_god, report.cards[2].basis_line)
        self.assertNotIn("Peach Blossom", report.cards[2].basis_line)
        self.assertNotIn("함지도화", _combined_user_text(report))
        self.assertNotIn("桃花", _combined_user_text(report))
        self.assertEqual(_validate_free_preview_report(report, payload), [])

    def test_love_limit_is_clear_once_and_other_paragraphs_offer_daily_scenes(self) -> None:
        for locale in ("ko", "en"):
            with self.subTest(locale=locale):
                payload = make_payload(locale=locale)
                card = build_fallback_free_preview_report(payload).cards[2]
                combined = "\n".join(card.preview_paragraphs)
                self.assertEqual(combined.count("속마음" if locale == "ko" else "private feelings"), 1)
                self.assertTrue(card.preview_paragraphs[0].startswith("예를 들면" if locale == "ko" else "For example"))
                self.assertIn("속마음" if locale == "ko" else "private feelings", card.preview_paragraphs[1])
                self.assertNotIn("속마음" if locale == "ko" else "private feelings", card.preview_paragraphs[2])

    def test_disabled_current_cycle_does_not_authorize_timing_action_tags(self) -> None:
        for locale in ("ko", "en"):
            with self.subTest(locale=locale):
                payload = make_payload(locale=locale)
                payload.disabled_sections = ["luck_cycles"]
                payload.luck_flow_facts.now_action_tags = ["STALE_ACTION"]
                report = build_fallback_free_preview_report(payload)
                self.assertNotIn("STALE_ACTION", _combined_user_text(report))
                self.assertEqual(_validate_free_preview_report(report, payload), [])

    def test_unconfirmed_english_luck_body_does_not_use_residual_cycle_narrative(self) -> None:
        for state in ("estimated", "missing", "disabled"):
            with self.subTest(state=state):
                payload = make_payload(locale="en", estimated=state == "estimated")
                if state == "missing":
                    payload.current_flow.active_luck_cycle = None
                elif state == "disabled":
                    payload.disabled_sections = ["luck_cycles"]
                report = build_fallback_free_preview_report(payload)
                body = "\n".join(report.cards[3].preview_paragraphs)
                for claim in ("the current flow asks", "Preparing for the next cycle", "Luck cycles are best used as a map"):
                    self.assertNotIn(claim, body)
                self.assertIn("demands you can actually observe", body)
                self.assertIn("rather than assigning it to a future cycle", body)
                self.assertEqual(_validate_free_preview_report(report, payload), [])
        known_payload = make_payload(locale="en")
        known_report = build_fallback_free_preview_report(known_payload)
        # This legacy fixture has no analysis rows. It must not receive a verified rule marker.
        self.assertIsNone(known_report.cards[3].reading_structure)
        self.assertIn(known_payload.current_flow.active_luck_cycle.display_gan_zhi, known_report.cards[3].preview_paragraphs[0])

    def test_english_love_has_one_outcome_limit_and_a_concrete_final_scene(self) -> None:
        report = build_fallback_free_preview_report(make_payload(locale="en"))
        paragraphs = report.cards[2].preview_paragraphs
        self.assertIn("cannot reveal another person's private feelings", paragraphs[1])
        self.assertNotIn("private feelings", paragraphs[2])
        self.assertTrue(paragraphs[0].startswith("For example"))
        self.assertEqual(len(paragraphs), 3)

    def test_fallback_free_preview_satisfies_schema_and_validation(self) -> None:
        payload = make_payload()
        report = build_fallback_free_preview_report(payload)

        self.assertEqual(report.schema_version, "free-preview-v1")
        self.assertEqual(report.provider, "fallback")
        self.assertEqual(report.prompt_version, "saju-free-preview-v4")
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
        water_payload.element_counts["water"] = 4

        fire_report = build_fallback_free_preview_report(fire_payload)
        water_report = build_fallback_free_preview_report(water_payload)

        self.assertNotEqual(fire_report.headline, water_report.headline)
        self.assertNotIn("혼자 많이 계산", fire_report.headline)
        self.assertNotIn("혼자 많이 계산", water_report.headline)

    def test_fallback_cards_are_substantial_and_structured(self) -> None:
        report = build_fallback_free_preview_report(make_payload())

        for card in report.cards:
            preview_text = "\n".join(card.preview_paragraphs)
            self.assertGreaterEqual(len(preview_text), 120)
            if card.key != "luck_flow":
                self.assertEqual([block.role for block in card.reading_structure.blocks], ["answer", "scene", "tradeoff", "action"])
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

        self.assertEqual(prompt.version, "saju-free-preview-v4")
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
            prompt_version="saju-free-preview-v4",
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
                    prompt_version="saju-free-preview-v4",
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
