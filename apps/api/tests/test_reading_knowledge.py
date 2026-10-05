import json
import unittest
from copy import deepcopy
from unittest.mock import patch

from app.domain.saju.interpretation import FreePreviewLLMOutput, InterpretationLLMOutput
from app.domain.saju.llm_payload import InterpretationLuckCycleAnalysis, InterpretationUncertaintyFlag
from app.domain.saju.localization import TEN_GOD_ENGLISH
from app.domain.saju.pydantic_compat import model_to_dict
from app.domain.saju.services.build_reading_plan import (
    build_reading_plan, load_reading_knowledge, validate_reading_structure,
)
from app.domain.saju.services.generate_free_preview import (
    _build_provider_report, _model_json_schema, _parse_free_preview_output,
    _validate_free_preview_report, build_fallback_free_preview_report,
)
from app.domain.saju.services.generate_interpretation import (
    _validate_report, build_fallback_interpretation_report,
)
from tests.test_generate_interpretation import make_payload


def payload_with_analysis(locale="ko"):
    payload = make_payload(locale=locale)
    current = payload.current_flow.active_luck_cycle
    payload.luck_cycle_analysis = [InterpretationLuckCycleAnalysis(
        display_gan_zhi=current.display_gan_zhi, start_year=current.start_year,
        end_year=current.end_year, start_age=current.start_age, end_age=current.end_age,
        period="2020–2029", phase="responsibility", phase_label="Responsibility",
        overall_tone="balanced", cycle_rank=2, overall_favorability="medium",
        confidence="medium", stem_ten_god="정관" if locale == "ko" else "Direct Officer",
        summary="Test-supplied cycle analysis, not an outcome forecast.",
    )]
    return payload


class ReadingKnowledgeTests(unittest.TestCase):
    def test_catalog_resolves_each_rule_with_locale_and_provenance(self):
        bundle = load_reading_knowledge()
        self.assertEqual(len(bundle.rules), 21)
        for locale in ("ko", "en"):
            for rule in bundle.rules:
                with self.subTest(locale=locale, rule=rule.id):
                    payload = payload_with_analysis(locale)
                    value = rule.any_of[0]
                    supplied = TEN_GOD_ENGLISH.get(value, value) if locale == "en" else value
                    if rule.topic == "core":
                        payload.element_counts = {key: 1 for key in payload.element_counts}
                        if value == "mixed":
                            payload.signals.dominant_elements = list(payload.element_counts)
                        else:
                            payload.element_counts[value] = 4
                            payload.signals.dominant_elements = [value]
                    elif rule.topic == "love":
                        payload.love_facts.spouse_house_ten_god = supplied
                    elif rule.topic == "work_money":
                        payload.career_facts.month_stem_ten_god = supplied
                    else:
                        payload.luck_cycle_analysis[0].stem_ten_god = supplied
                    report = build_fallback_free_preview_report(payload)
                    card = next(card for card in report.cards if card.key == rule.topic)
                    structure = card.reading_structure
                    self.assertEqual(structure.rule_id, rule.id)
                    self.assertEqual(structure.expert_review, "not_completed")
                    self.assertEqual([block.kind for block in structure.blocks], ["interpretation", "illustration", "interpretation", "advice"])
                    self.assertEqual(model_to_dict(card.basis_explanation), model_to_dict(structure.analysis_note))
                    self.assertEqual(_validate_free_preview_report(report, payload), [])

    def test_missing_and_stale_cycle_inputs_never_receive_verified_timing(self):
        for state in ("unknown", "disabled", "disabled_evidence", "missing", "not_in_list", "stale_analysis"):
            with self.subTest(state=state):
                payload = payload_with_analysis()
                if state == "unknown":
                    payload.profile.is_birth_time_estimated = True
                elif state == "disabled":
                    payload.disabled_sections = ["luck_cycles"]
                elif state == "disabled_evidence":
                    next(item for item in payload.evidence if item.key == "luck_cycles").status = "disabled"
                elif state == "missing":
                    payload.current_flow.active_luck_cycle = None
                elif state == "not_in_list":
                    payload.luck_cycles = []
                else:
                    payload.luck_cycle_analysis[0].end_year = 1900
                self.assertNotIn("luck_flow", build_reading_plan(payload).sections)

    def test_inconsistent_counts_and_unknown_labels_do_not_select_a_rule(self):
        payload = payload_with_analysis()
        payload.signals.dominant_elements = ["water"]
        payload.love_facts.spouse_house_ten_god = "NOT_A_TEN_GOD"
        payload.career_facts.month_stem_ten_god = ""
        plan = build_reading_plan(payload)
        self.assertEqual(set(plan.unclassified_topics), {"core", "love", "work_money"})

    def test_critical_calculation_uncertainty_withholds_new_verified_rules(self):
        payload = payload_with_analysis()
        payload.uncertainty_summary = [InterpretationUncertaintyFlag(
            code="uncertain_day_pillar", severity="critical", affected_fields=["day_pillar"],
            user_message="The supplied day pillar is uncertain.",
        )]
        self.assertEqual(build_reading_plan(payload).sections, {})
        self.assertTrue(all(card.reading_structure is None for card in build_fallback_free_preview_report(payload).cards))

    def test_catalog_loader_rejects_ambiguous_missing_and_unsupported_configuration(self):
        original = model_to_dict(load_reading_knowledge())
        for mutation in ("conflict", "source", "locale", "exclusion", "placeholder", "note_placeholder", "topic"):
            data = deepcopy(original)
            if mutation == "conflict":
                rule = deepcopy(data["rules"][0])
                rule["id"] = "different-id-same-condition"
                data["rules"].append(rule)
            elif mutation == "source":
                data["rules"][0]["source_id"] = "unknown-source"
            elif mutation == "locale":
                del data["rules"][0]["wording"]["en"]
            elif mutation == "exclusion":
                data["rules"][0]["exclusions"] = ["pretend_guard"]
            elif mutation == "placeholder":
                data["rules"][0]["wording"]["ko"]["answer"] = "알 수 없는 {event_date}에 취업한다"
            elif mutation == "note_placeholder":
                data["rules"][0]["wording"]["ko"]["analysis_note"] = "사실이 아닌 {next_cycle}을 근거로 검토했습니다."
            else:
                data["rules"][0]["topic"] = "love"
            with self.subTest(mutation=mutation), patch("pathlib.Path.read_text", return_value=json.dumps(data)):
                with self.assertRaises(ValueError):
                    load_reading_knowledge()

    def test_draft_rules_never_supply_claims(self):
        bundle = load_reading_knowledge()
        for rule in bundle.rules:
            if rule.topic == "love":
                rule.status = "draft"
        self.assertNotIn("love", build_reading_plan(payload_with_analysis(), bundle).sections)

    def test_tampered_fact_rule_reference_and_text_fail_after_rebuilding_plan(self):
        for field in ("fact", "reference", "rule", "block", "text", "note_fact", "note_reading", "structure_note", "basis_line", "payload"):
            payload = payload_with_analysis()
            card = build_fallback_free_preview_report(payload).cards[1]
            if field == "fact":
                card.reading_structure.facts[0].value = "편재"
            elif field == "reference":
                card.reading_structure.blocks[0].fact_ids = ["fictional-life-event"]
            elif field == "rule":
                card.reading_structure.rule_version = 999
            elif field == "block":
                card.reading_structure.blocks.reverse()
            elif field == "text":
                card.preview_paragraphs[0] = "실제 경험을 알고 있는 것처럼 꾸며낸 장면입니다."
            elif field == "note_fact":
                card.basis_explanation.facts = ["실제로 계산되지 않은 정재"]
            elif field == "note_reading":
                card.basis_explanation.reading = "근거 없는 다음 대운까지 사용한 해석입니다."
            elif field == "structure_note":
                card.reading_structure.analysis_note.reading = "근거 없는 다음 대운까지 사용한 해석입니다."
            elif field == "basis_line":
                card.basis_line = "원문에 없는 계산 사실"
            else:
                payload.career_facts.month_stem_ten_god = "편재"
            with self.subTest(field=field):
                self.assertTrue(validate_reading_structure(card, payload))

    def test_notes_explain_selected_rule_inputs_instead_of_legacy_extra_facts(self):
        for locale in ("ko", "en"):
            payload = payload_with_analysis(locale)
            report = build_fallback_free_preview_report(payload)
            cards = {card.key: card for card in report.cards}
            core = cards["core"].basis_explanation
            self.assertIn("화" if locale == "ko" else "Fire", core.facts[1])
            self.assertNotIn("부족" if locale == "ko" else "missing", core.reading)
            luck = cards["luck_flow"].basis_explanation
            self.assertIn(payload.luck_cycle_analysis[0].stem_ten_god, luck.reading)
            self.assertIn(payload.luck_cycle_analysis[0].period, luck.reading)
            self.assertNotIn("다음" if locale == "ko" else "next", luck.reading)
            payload.profile.is_birth_time_estimated = True
            limited = {card.key: card for card in build_fallback_free_preview_report(payload).cards}
            self.assertIn("시주 제외" if locale == "ko" else "hour pillar excluded", limited["core"].basis_explanation.facts[-1])
            self.assertIsNone(limited["luck_flow"].reading_structure)

    def test_model_cannot_supply_server_markers_or_verified_facts(self):
        data = model_to_dict(build_fallback_free_preview_report(payload_with_analysis()))
        data["cards"][0]["reading_structure"]["expert_review"] = "completed"
        for model in (FreePreviewLLMOutput, InterpretationLLMOutput):
            schema = json.dumps(_model_json_schema(model))
            self.assertNotIn("reading_structure", schema)
            self.assertNotIn("reading_sections", schema)
        parsed = _parse_free_preview_output(json.dumps(data))
        result = _build_provider_report(parsed, provider="codex")
        self.assertTrue(all(card.reading_structure is None for card in result.cards))

    def test_event_timing_and_population_questions_remain_explicitly_unavailable(self):
        caps = build_reading_plan(payload_with_analysis()).question_capabilities
        self.assertEqual(len(caps), 5)
        for cap in caps:
            self.assertIn(cap.status, {"needs_rule_review", "needs_reference_population"})
            self.assertTrue(cap.missing_requirements)
            self.assertEqual(set(cap.forbidden_claims), {"event_probability", "guaranteed_event_date", "population_percentile"})

    def test_detailed_and_preview_fallback_share_judgments_and_reject_divergence(self):
        for locale in ("ko", "en"):
            payload = payload_with_analysis(locale)
            preview = build_fallback_free_preview_report(payload)
            detail = build_fallback_interpretation_report(payload)
            self.assertEqual(len(detail.reading_sections), 4)
            for topic, key in (("core", "core_analysis"), ("love", "love"), ("work_money", "career"), ("luck_flow", "luck_flow")):
                card = next(card for card in preview.cards if card.key == topic)
                self.assertEqual(detail.reading_sections[key], card.reading_structure)
                for block in card.reading_structure.blocks:
                    self.assertIn(block.text, getattr(detail, key).body)
            self.assertEqual(_validate_report(detail, payload), [])
            detail.career.body += "\nThis contradictory conclusion was not in the selected rule."
            self.assertIn("career:reading_contract_mismatch", _validate_report(detail, payload))

    def test_unfounded_claims_in_unstructured_hero_are_rejected(self):
        cases = {
            "ko": ["내일은 면접에 꼭 붙어. 합격 소식을 듣게 될 거야.", "다음 달에 승진하게 될 거야.",
                   "이번 주 금요일에 연인을 만나게 될 거야.", "사주 전문가가 검증한 정확한 해석이야.", "타인보다 상위 1%야."],
            "en": ["You will get the job tomorrow. Expect a signed offer.", "You will be promoted next month.",
                   "You will meet your partner on Friday.", "This interpretation is verified by a saju expert.", "You have a 90% chance of meeting someone."],
        }
        for locale, claims in cases.items():
            payload = payload_with_analysis(locale)
            for claim in claims:
                preview = build_fallback_free_preview_report(payload)
                preview.hero_overview[0] = claim
                detail = build_fallback_interpretation_report(payload)
                detail.summary.overview += " " + claim
                with self.subTest(locale=locale, claim=claim):
                    self.assertTrue(any(issue.startswith("unsupported_") for issue in _validate_free_preview_report(preview, payload)))
                    self.assertTrue(any(issue.startswith("unsupported_") for issue in _validate_report(detail, payload)))

    def test_unverified_model_cards_still_require_three_supported_role_slots(self):
        payload = payload_with_analysis()
        data = model_to_dict(build_fallback_free_preview_report(payload))
        parsed = _parse_free_preview_output(json.dumps(data))
        report = _build_provider_report(parsed, provider="codex")
        report.cards[0].preview_paragraphs.append("An extra filler paragraph outside the three planned roles.")
        self.assertIn("cards.core:reading_role_count_mismatch", _validate_free_preview_report(report, payload))
