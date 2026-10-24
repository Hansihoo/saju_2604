"""Meaningful boundaries for the additive facts-first question flow."""

from datetime import datetime, timedelta
import json
import unittest
from unittest.mock import Mock, patch

import httpx
from pydantic import ValidationError

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from app.domain.saju.pydantic_compat import model_copy_compat, model_to_dict
from app.domain.saju.question_reading import (
    QuestionUnavailable, _ANSWERS, _CALCULATIONS, _dohwa,
    clear_question_caches, create_basic_reading, create_question_reading,
)
from app.domain.saju.question_schemas import SajuQuestionRequest
from app.domain.saju.schemas import SajuPreviewRequest
from app.domain.saju.services.preview_orchestrator import create_saju_preview_response
from app.main import app


NOW = datetime(2026, 10, 8, 12, tzinfo=ZoneInfo("Asia/Seoul"))


def payload(**changes):
    data = {"birth_date": "1988-11-20", "birth_time": "23:30", "region_id": "kr-chungbuk-jecheon", "gender": "male"}
    data.update(changes)
    return SajuPreviewRequest(**data)


class QuestionReadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = create_saju_preview_response(payload=payload(), trace_id="test-base", service_name="tests",
                                               debug_requested=False, report_mode="none", as_of=NOW)

    def setUp(self):
        clear_question_caches()

    def calculate(self):
        return Mock(return_value=model_copy_compat(self.base, deep=True))

    def answer(self, question_id, input_payload=None, as_of=NOW, calculate=None):
        return create_question_reading(payload=SajuQuestionRequest(input=input_payload or payload(), question_id=question_id),
                                       trace_id="test-answer", service_name="tests", as_of=as_of, calculate=calculate or self.calculate())

    def test_basic_skips_generation_and_shares_calculated_facts(self):
        calculate = self.calculate()
        basic = create_basic_reading(payload=payload(), trace_id="basic", service_name="tests", as_of=NOW, calculate=calculate)
        self.assertIsNone(basic.result.free_preview)
        self.assertIsNone(basic.result.interpretation)
        self.assertEqual(basic.pipeline_status.llm_formatting, "skipped")
        self.assertEqual(len([q for q in basic.question_flow.questions if not q.id.startswith("features.")]), 5)
        self.assertEqual({q.id for q in basic.question_flow.questions if q.id.startswith("features.")},
                         {"features.taegeuk", "features.study_solitude", "features.dohwa"})
        self.assertEqual(calculate.call_args.kwargs["report_mode"], "none")
        self.answer("stars.dohwa", calculate=calculate)
        self.assertEqual(calculate.call_count, 1)

    def test_distinct_question_answers_not_one_renamed_topic(self):
        answers = [self.answer(question_id) for question_id in ("luck.current_next", "stars.dohwa", "wealth.locations", "period.this_year")]
        self.assertEqual(len({answer.answer for answer in answers}), 4)
        for answer in answers:
            self.assertEqual(answer.provider, "deterministic")
            self.assertTrue(answer.facts)
            self.assertTrue(answer.sections)
            self.assertTrue(answer.notices)
            self.assertNotIn("free_preview", model_to_dict(answer))
            self.assertNotIn("reading_structure", model_to_dict(answer))

    def test_feature_answer_explanation_is_visible_and_next_menu_omits_answered_meaning(self):
        for locale in ("ko", "en"):
            clear_question_caches()
            tae = self.answer("features.taegeuk", input_payload=payload(locale=locale))
            study = self.answer("features.study_solitude", input_payload=payload(locale=locale))
            self.assertEqual([s.id for s in tae.sections if s.kind == "reading"], ["personal_meaning"])
            self.assertEqual([s.id for s in tae.sections if s.kind == "memo"], ["matched_evidence"])
            self.assertNotIn("features.study_solitude", {q.id for q in tae.followups})
            self.assertNotIn("features.taegeuk", {q.id for q in tae.followups})
            self.assertIn("features.taegeuk", {q.id for q in study.followups})
            self.assertIn("learning_relationship_distinction", tae.source_context["answer_meaning_ids"])
            self.assertTrue(all(q.id.startswith("features.") and q.category == "core" for q in study.followups))
            cached = self.answer("features.taegeuk", input_payload=payload(locale=locale))
            self.assertTrue(cached.cached)
            self.assertEqual(cached.followups, tae.followups)

    def test_feature_memo_only_advertises_supplied_alternate_comparisons(self):
        for locale in ("ko", "en"):
            for conditional in (False, True):
                clear_question_caches()
                birth = payload(locale=locale) if conditional else payload(
                    birth_date="1992-06-09", birth_time="07:10", locale=locale)
                answer = self.answer("features.taegeuk", input_payload=birth,
                                     calculate=create_saju_preview_response)
                self.assertEqual(bool(answer.source_context["feature_comparisons"]), conditional)
                marker = "다른 날짜 기준" if locale == "ko" else "alternate day-convention comparison"
                self.assertEqual(marker in answer.memo.reading, conditional)
                evidence_marker = "다른 날짜 기준의 명식" if locale == "ko" else "Alternate chart:"
                self.assertEqual(evidence_marker in answer.sections[1].text, conditional)

    def test_hidden_stems_are_not_zipped_to_different_library_order(self):
        answer = self.answer("wealth.locations")
        self.assertIn("0곳", answer.answer)
        self.assertIn("3곳", answer.answer)
        relations = answer.source_context["wealth_relations"]
        self.assertIn({"pillar_key": "year", "stem": "을", "ten_god": "정재"}, relations)
        self.assertIn({"pillar_key": "month", "stem": "갑", "ten_god": "편재"}, relations)
        self.assertIn({"pillar_key": "time", "stem": "임", "ten_god": "식신"}, relations)
        self.assertIn("월주 亥 속 갑 · 편재", answer.sections[1].text)

    def test_wealth_uses_selected_day_for_visible_and_hidden_relations(self):
        birth = payload(birth_date="1988-06-10", birth_time="00:00", region_id="kr-seoul",
                        gender="female", is_birth_time_estimated=True)
        answer = self.answer("wealth.locations", input_payload=birth, calculate=create_saju_preview_response)
        month = next(r for r in answer.source_context["visible_wealth_relations"] if r["pillar_key"] == "month")
        self.assertEqual(month["ten_god"], "식신")
        self.assertNotEqual(month["ten_god"], month["reported_ten_god"])
        self.assertIn("겉에 0곳", answer.answer)
        self.assertEqual(next(f.value for f in answer.facts if f.id == "wealth.month.stem_ten_god"),
                         month["reported_ten_god"])
        self.assertTrue(answer.source_context["critical_uncertainty"])

    def test_empty_wealth_does_not_claim_hidden_wealth(self):
        base = model_copy_compat(self.base, deep=True)
        for key in base.manse.meta.visible_pillar_keys:
            pillar = getattr(base.manse.pillars, key)
            pillar.stem_ten_god = "비견"
            pillar.hidden_stems = ["경"]
        answer = self.answer("wealth.locations", calculate=Mock(return_value=base))
        self.assertIn("0곳", answer.answer)
        self.assertNotIn("안쪽에는 있어", answer.answer)

    def test_same_hamji_position_is_not_counted_twice(self):
        base = model_copy_compat(self.base, deep=True)
        match = next(star for star in base.manse.special_stars if star.key == "wangji-dohwa").matches[0]
        for star in base.manse.special_stars:
            if star.key in {"dohwa-year-branch", "dohwa-day-branch"}:
                star.matches = [model_copy_compat(match, deep=True)]
                star.active = True
                star.count = 1
        facts, sections = [], []
        answer, memo, context = _dohwa(base, "ko", facts, sections)
        self.assertIn("좁은 기준: 1곳", answer)
        self.assertEqual(len(context["dohwa_methods"][0]["positions"]), 1)

    def test_precise_cycle_boundary_changes_answer_even_on_same_day(self):
        # Find the interval containing NOW rather than depend on a list offset.
        current = next(cycle for cycle in self.base.manse.luck_cycles if cycle.gan_zhi == "丁卯")
        boundary = datetime.fromisoformat(current.change_datetime).replace(tzinfo=ZoneInfo("Asia/Seoul"))
        base = model_copy_compat(self.base, deep=True)
        base.period_flows.month.period_start = "2034-03-01 00:00:00"
        base.period_flows.month.period_end = "2034-05-01 00:00:00"
        calculate = Mock(return_value=base)
        before = self.answer("luck.current_next", as_of=boundary - timedelta(seconds=1), calculate=calculate)
        at = self.answer("luck.current_next", as_of=boundary, calculate=calculate)
        self.assertIn("정묘", before.answer)
        self.assertTrue(at.answer.startswith("현재 무진"))
        self.assertFalse(at.cached)
        self.assertEqual(calculate.call_count, 1)

    def test_unknown_birth_time_excludes_hour_and_cycle_question(self):
        unknown = payload(is_birth_time_estimated=True)
        basic = create_basic_reading(payload=unknown, trace_id="unknown", service_name="tests", as_of=NOW, calculate=create_saju_preview_response)
        self.assertNotIn("luck.current_next", [question.id for question in basic.question_flow.questions])
        self.assertEqual(basic.manse.analysis.visible_element_total, 6)
        with self.assertRaises(QuestionUnavailable):
            self.answer("luck.current_next", input_payload=unknown, calculate=create_saju_preview_response)
        answer = self.answer("stars.dohwa", input_payload=unknown, calculate=create_saju_preview_response)
        self.assertTrue(all("time" not in item["positions"] for item in answer.source_context["dohwa_methods"]))
        wealth = self.answer("wealth.locations", input_payload=unknown, calculate=create_saju_preview_response)
        self.assertTrue(all(item["pillar_key"] != "time" for item in wealth.source_context["wealth_relations"]))

    def test_before_first_cycle_does_not_expose_unavailable_question(self):
        basic = create_basic_reading(payload=payload(), trace_id="early", service_name="tests", as_of=datetime(1989, 1, 1, tzinfo=ZoneInfo("Asia/Seoul")), calculate=self.calculate())
        self.assertNotIn("luck.current_next", [question.id for question in basic.question_flow.questions])

    def test_critical_chart_has_visible_limitation_and_fact_only_answer(self):
        answer = self.answer("luck.current_next")
        self.assertTrue(answer.source_context["critical_uncertainty"])
        self.assertTrue(any("날의 글자가 달라져" in notice and "선택한 기준" in notice for notice in answer.notices))
        self.assertNotIn("verified", json.dumps(model_to_dict(answer)))
        self.assertNotIn("좋은 시기", answer.answer)

    def test_cached_response_is_copied_and_current_request_trace_is_restored(self):
        first = self.answer("wealth.locations")
        original = first.answer
        first.answer = "caller mutation"
        first.sections[0].text = "caller mutation"
        second = self.answer("wealth.locations")
        self.assertTrue(second.cached)
        self.assertEqual(second.answer, original)
        self.assertNotIn("caller mutation", second.sections[0].text)

    def test_locale_input_and_calculation_flags_do_not_reuse_old_answer(self):
        self.answer("wealth.locations")
        english = self.answer("wealth.locations", input_payload=payload(locale="en"))
        self.assertFalse(english.cached)
        self.assertNotRegex(english.answer + " ".join(section.text for section in english.sections), r"[가-힣]")
        changed = self.answer("wealth.locations", input_payload=payload(gender="female"))
        self.assertFalse(changed.cached)
        with patch("app.domain.saju.question_reading.settings.use_canonical_year_month_pillars", True):
            calculate = self.calculate()
            create_basic_reading(payload=payload(), trace_id="flags", service_name="tests", as_of=NOW, calculate=calculate)
            calculate.assert_called_once()

    def test_region_local_midnight_invalidates_calculation_cache(self):
        calculate = self.calculate()
        before = datetime(2026, 10, 8, 23, 59, 59, tzinfo=ZoneInfo("Asia/Seoul"))
        after = before + timedelta(seconds=1)
        self.assertEqual(before.astimezone(ZoneInfo("UTC")).date(), after.astimezone(ZoneInfo("UTC")).date())
        for instant in (before, after):
            create_basic_reading(payload=payload(), trace_id="midnight", service_name="tests", as_of=instant, calculate=calculate)
        self.assertEqual(calculate.call_count, 2)

    def test_solar_term_change_within_day_invalidates_cached_period_facts(self):
        base = model_copy_compat(self.base, deep=True)
        base.period_flows.month.period_start = "2026-09-08 00:00:00"
        base.period_flows.month.period_end = "2026-10-08 12:00:00"
        calculate = Mock(return_value=base)
        for instant in (NOW - timedelta(seconds=1), NOW):
            create_basic_reading(payload=payload(), trace_id="solar-term", service_name="tests", as_of=instant, calculate=calculate)
        self.assertEqual(calculate.call_count, 2)

    def test_cache_expiry_and_size_are_bounded(self):
        with patch("app.domain.saju.question_reading.monotonic", return_value=0):
            self.answer("stars.dohwa")
        with patch("app.domain.saju.question_reading.monotonic", return_value=121):
            expired = self.answer("stars.dohwa")
        self.assertFalse(expired.cached)
        self.assertLessEqual(len(_ANSWERS), 48)
        self.assertLessEqual(len(_CALCULATIONS), 48)

    def test_unsupported_ids_and_supplied_facts_or_context_are_rejected(self):
        for data in ({"question_id": "love.meeting_window"}, {"question_id": "wealth.locations", "context": "seeking_new_connection"}, {"question_id": "wealth.locations", "facts": {"score": 100}}):
            with self.assertRaises(ValidationError):
                SajuQuestionRequest(input=payload(), **data)

    def test_annual_boundary_uses_ipchun_not_january_first(self):
        january = self.answer("period.this_year", as_of=datetime(2026, 1, 1, 12, tzinfo=ZoneInfo("Asia/Seoul")))
        october = self.answer("period.this_year")
        self.assertEqual(january.source_context["annual"]["gan_zhi"], "乙巳")
        self.assertEqual(october.source_context["annual"]["gan_zhi"], "丙午")
        self.assertEqual(october.source_context["annual"]["stem_ten_god"], "편관")

    def test_annual_korean_particle_is_safe_for_vowel_ending_relation(self):
        normal = payload(birth_date="1997-09-18", birth_time="14:30", region_id="kr-seoul")
        answer = self.answer("period.this_year", input_payload=normal, calculate=create_saju_preview_response)
        self.assertEqual(answer.source_context["annual"]["stem_ten_god"], "정재")
        visible = answer.answer + " ".join(section.text for section in answer.sections)
        self.assertIn("정재에 해당해", visible)
        self.assertNotIn("정재으로", visible)

    def test_english_single_position_grammar_and_dohwa_display(self):
        normal = payload(birth_date="1997-09-18", birth_time="14:30", region_id="kr-seoul", locale="en")
        wealth = self.answer("wealth.locations", input_payload=normal, calculate=create_saju_preview_response)
        self.assertIn("1 visible stem position and 1 hidden stem position", wealth.answer)
        self.assertNotIn("1 visible stem positions", wealth.answer)
        stars = self.answer("stars.dohwa", input_payload=normal, calculate=create_saju_preview_response)
        self.assertIn("0 positions", stars.answer)
        self.assertIn("1 position", stars.answer)
        self.assertNotIn("position(s)", stars.answer + " ".join(section.text for section in stars.sections))

    def test_unknown_zero_hidden_wealth_states_checked_pillar_scope(self):
        unknown = payload(birth_date="1997-09-18", birth_time="14:30", region_id="kr-seoul", is_birth_time_estimated=True)
        answer = self.answer("wealth.locations", input_payload=unknown, calculate=create_saju_preview_response)
        self.assertIn("확인한 연주·월주·일주", answer.answer)
        self.assertIn("확인한 연주·월주·일주의 지장간", answer.sections[1].text)
        self.assertIn("0곳", answer.answer)
        english_input = model_copy_compat(unknown, update={"locale": "en"})
        english = self.answer("wealth.locations", input_payload=english_input, calculate=create_saju_preview_response)
        self.assertIn("checked year, month and day pillars", english.sections[1].text)

    def test_dohwa_names_are_readable_and_empty_methods_do_not_claim_difference(self):
        answer = self.answer("stars.dohwa")
        self.assertIn("진(辰)", answer.sections[0].text)
        self.assertIn("유(酉)", answer.sections[0].text)
        self.assertIn("기준에 따라 다르게 잡혀", answer.answer)
        empty = model_copy_compat(self.base, deep=True)
        for star in empty.manse.special_stars:
            star.matches = []
            star.active = False
            star.count = 0
        clear_question_caches()
        no_matches = self.answer("stars.dohwa", calculate=Mock(return_value=empty))
        self.assertNotIn("다르게 잡혀", no_matches.answer)
        self.assertIn("보는 기준이 나뉘어", no_matches.answer)
        self.assertNotIn("0곳야", no_matches.answer)

    def test_noncritical_cycle_start_warning_is_preserved_with_question(self):
        normal = payload(birth_date="1997-09-18", birth_time="14:30", region_id="kr-seoul", gender="female")
        answer = self.answer("luck.current_next", input_payload=normal, calculate=create_saju_preview_response)
        self.assertFalse(answer.source_context["critical_uncertainty"])
        self.assertIn("luck_cycle_start_age_changed", answer.source_context["uncertainty_codes"])
        self.assertTrue(any("계산 기준에 따라 달라질" in notice for notice in answer.notices))
        self.assertIn("일간 癸 기준으로", answer.sections[0].text)
        self.assertNotIn("癸과", answer.sections[0].text)
        self.assertIn("천간이 壬에서 癸 글자로", answer.sections[1].text)
        self.assertNotIn("癸으로", answer.sections[1].text)
        english_input = model_copy_compat(normal, update={"locale": "en"})
        english = self.answer("luck.current_next", input_payload=english_input, calculate=create_saju_preview_response)
        self.assertTrue(any("differ between calculation policies" in notice for notice in english.notices))
        other_question = self.answer("stars.dohwa", input_payload=normal, calculate=create_saju_preview_response)
        self.assertFalse(any("대운 시점" in notice for notice in other_question.notices))


class QuestionEndpointTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        clear_question_caches()

    async def test_http_basic_then_one_question_never_calls_model(self):
        transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 1))
        with patch("app.domain.saju.services.build_preview_response._generate_free_preview_safely") as preview, patch("app.domain.saju.services.build_preview_response.generate_interpretation_report") as full:
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                wire = json.loads(payload().json())
                basic = await client.post("/saju/basic", json=wire)
                self.assertEqual(basic.status_code, 200, basic.text)
                self.assertEqual(basic.headers["cache-control"], "private, no-store")
                self.assertIn("copy", basic.json()["question_flow"]["versions"])
                first = await client.post("/saju/question", json={"input": wire, "question_id": "wealth.locations"})
                stars = await client.post("/saju/question", json={"input": wire, "question_id": "stars.dohwa"})
                for fact in stars.json()["facts"]:
                    if fact["id"].endswith(".matches"):
                        star_key = fact["id"][len("stars."):-len(".matches")]
                        actual_star = next(star for star in basic.json()["manse"]["special_stars"] if star["key"] == star_key)
                        self.assertEqual(fact["value"], actual_star["matches"])
                second = await client.post("/saju/question", json={"input": wire, "question_id": "wealth.locations"})
                self.assertEqual(first.status_code, 200, first.text)
                self.assertTrue(second.json()["cached"])
                unsupported = await client.post("/saju/question", json={"input": wire, "question_id": "love.meeting_window"})
                self.assertEqual(unsupported.status_code, 422)
            preview.assert_not_called()
            full.assert_not_called()


if __name__ == "__main__":
    unittest.main()
