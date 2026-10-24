"""Chart-specific basic body, independent of model/question wording."""

from datetime import datetime, timedelta
import json
import unittest
from unittest.mock import Mock, patch

import httpx

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from app.domain.saju.basic_reading import build_basic_overview
from app.domain.saju.pydantic_compat import model_copy_compat, model_to_dict
from app.domain.saju.question_reading import (
    QuestionUnavailable, clear_question_caches, create_basic_reading, create_question_reading,
)
from app.domain.saju.question_schemas import QuestionVersions, SajuQuestionRequest
from app.domain.saju.schemas import SajuPreviewRequest
from app.domain.saju.services.preview_orchestrator import create_saju_preview_response
from app.main import app


NOW = datetime(2026, 10, 8, 12, tzinfo=ZoneInfo("Asia/Seoul"))


def input_payload(**changes):
    data = {"birth_date": "1988-11-20", "birth_time": "23:30", "gender": "male", "region_id": "kr-chungbuk-jecheon"}
    data.update(changes)
    return SajuPreviewRequest(**data)


def resolve(document, path):
    value = document
    for key in path.replace("[", ".").replace("]", "").split("."):
        value = value[int(key)] if key.isdigit() else value[key]
    return value


class BasicReadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = {
            "boundary": input_payload(),
            "normal": input_payload(birth_date="1997-09-18", birth_time="14:30", gender="female", region_id="kr-seoul"),
            "unknown": input_payload(birth_date="1997-09-18", birth_time="14:30", region_id="kr-seoul", is_birth_time_estimated=True),
        }
        cls.bases = {key: create_saju_preview_response(payload=value, trace_id="basic-fixture", service_name="tests",
            debug_requested=False, report_mode="none", as_of=NOW) for key, value in cls.inputs.items()}

    def setUp(self):
        clear_question_caches()

    def overview(self, case="boundary", locale="ko", base=None, as_of=NOW):
        return build_basic_overview(base=base or self.bases[case], locale=locale, as_of=as_of)

    def text(self, overview):
        return overview.headline + "\n" + "\n".join(section.text for section in overview.sections)

    def evidence_text(self, overview):
        return "\n".join(section.text for section in overview.memo_sections)

    def memo_section(self, overview, section_id):
        return next(section for section in overview.memo_sections if section.id == section_id)

    def test_personal_period_and_location_information_is_visible(self):
        boundary = self.overview()
        normal = self.overview("normal")
        self.assertEqual([section.id for section in boundary.sections], ["luck", "annual", "wealth", "dohwa"])
        body = self.evidence_text(boundary)
        for value in ("2034년 4월 1일", "정관", "편인", "책임·역할·평가", "배움과 회복", "편관", "올해의 편관 이름", "연주 진(辰) 속 을(乙)", "월주 해(亥) 속 갑(甲)", "지장간 3곳", "시주 자(子)"):
            self.assertIn(value, body)
        self.assertIn("2034년 4월 20일", self.evidence_text(normal))
        self.assertIn("겉 1곳과 지장간 1곳", self.evidence_text(normal))
        self.assertIn("2034년 4월", self.text(boundary))
        self.assertNotEqual(self.text(boundary), self.text(normal))
        self.assertTrue(all(len(section.text.split("\n\n")) >= 2 for section in boundary.sections))

    def test_critical_chart_remains_selected_policy_facts_and_vocabulary(self):
        overview = self.overview()
        self.assertTrue(overview.source_context["critical_uncertainty"])
        self.assertTrue(overview.source_context["vocabulary_only"])
        self.assertFalse(overview.source_context["interpretation_rules_applied"])
        self.assertEqual(sum("지금 선택한 기준" in notice for notice in overview.notices), 1)
        for source in overview.source_context["vocabulary_sources"]:
            self.assertEqual(source["kind"], "vocabulary_theme")
            self.assertFalse(source["interpretation_rule_applied"])
            self.assertEqual(source["expert_review"], "not_completed")
        for rejected in ("좋은 시기", "승진하게", "연인을 만나", "검증된 예측", "정관는", "편관로", "편관라는", "여유을", "癸으로", "0곳야"):
            self.assertNotIn(rejected, self.text(overview))
        for rejected in ("계(癸)을", "계(癸)과", "정재으로"):
            self.assertNotIn(rejected, self.text(self.overview("normal")))

    def test_unknown_time_excludes_time_dependence_and_scopes_zero(self):
        overview = self.overview("unknown")
        self.assertEqual([section.id for section in overview.sections], ["annual", "wealth", "dohwa"])
        self.assertNotIn("luck", overview.source_context)
        self.assertTrue(all("pillars.time" not in fact.source_path and "luck_cycles[" not in fact.source_path for fact in overview.facts))
        wealth = self.memo_section(overview, "wealth")
        self.assertIn("임시로 표시한 연주·월주·일주", wealth.text)
        self.assertTrue(any("날의 글자도 확정하지 못했어" in item for item in overview.notices))
        self.assertIn("잠정", " ".join(overview.memo.facts))
        self.assertIn("지장간 0곳", wealth.text)
        self.assertTrue(any("생년월일" in notice and "구간 설명은 제외" in notice for notice in overview.notices))

    def test_hidden_stem_public_order_not_zipped_with_library_labels(self):
        overview = self.overview()
        relations = overview.source_context["wealth"]["wealth_relations"]
        self.assertIn({"pillar_key": "year", "stem": "을", "ten_god": "정재"}, relations)
        self.assertIn({"pillar_key": "month", "stem": "갑", "ten_god": "편재"}, relations)
        self.assertIn({"pillar_key": "time", "stem": "임", "ten_god": "식신"}, relations)
        wealth = self.memo_section(overview, "wealth")
        self.assertIn("일주 진(辰) 속 을(乙)", wealth.text)
        self.assertIn("같은 글자가 서로 다른 기둥", wealth.text)

    def test_dohwa_methods_are_separate_and_duplicate_positions_are_unioned(self):
        base = model_copy_compat(self.bases["boundary"], deep=True)
        match = next(star for star in base.manse.special_stars if star.key == "wangji-dohwa").matches[0]
        for star in base.manse.special_stars:
            if star.key in {"dohwa-year-branch", "dohwa-day-branch"}:
                star.matches = [model_copy_compat(match, deep=True)]
                star.active = True
                star.count = 1
        overview = self.overview(base=base)
        dohwa = self.memo_section(overview, "dohwa")
        self.assertIn("함지도화: 1곳", dohwa.text)
        self.assertIn("왕지도화: 1곳", dohwa.text)
        self.assertIn("한 번만 기록", dohwa.text)
        self.assertNotIn("도화 2곳", dohwa.text)

    def test_english_localization_and_grammar_has_same_personal_facts(self):
        english = self.overview("normal", "en")
        self.assertNotRegex(self.text(english) + " ".join(english.notices) + english.memo.reading, r"[가-힣]")
        self.assertIn("Apr 20, 2034", self.evidence_text(english))
        self.assertIn("1 position", self.evidence_text(english))
        self.assertNotIn("1 positions", self.text(english))
        self.assertNotIn("position(s)", self.text(english))
        self.assertEqual([(fact.id, fact.value) for fact in english.facts], [(fact.id, fact.value) for fact in self.overview("normal").facts])

    def test_partial_unavailable_keeps_other_sections(self):
        with patch("app.domain.saju.basic_reading._annual", side_effect=QuestionUnavailable("missing boundary")):
            overview = self.overview()
        self.assertEqual([section.id for section in overview.sections], ["luck", "wealth", "dohwa"])
        self.assertNotIn("annual", overview.source_context)
        self.assertFalse(any(fact.id.startswith("annual.") for fact in overview.facts))
        self.assertTrue(any("올해 들어온 글자" in notice and "제외" in notice for notice in overview.notices))
        self.assertNotIn("입춘 세운", overview.memo.reading)
        self.assertIn("정밀 대운 구간", overview.memo.reading)

    def test_memo_names_only_the_data_used_by_included_sections(self):
        unknown = self.overview("unknown")
        self.assertNotIn("정밀 대운 구간", unknown.memo.reading)
        self.assertIn("입춘 세운", unknown.memo.reading)
        self.assertIn("표시된 천간·지장간", unknown.memo.reading)
        for locale in ("ko", "en"):
            with patch("app.domain.saju.basic_reading._luck", side_effect=QuestionUnavailable("missing precise cycles")):
                no_luck = self.overview(locale=locale)
            self.assertNotIn("luck", [section.id for section in no_luck.sections])
            self.assertNotIn("정밀 대운 구간" if locale == "ko" else "precise cycle intervals", no_luck.memo.reading)
        with patch("app.domain.saju.basic_reading._wealth", side_effect=QuestionUnavailable("missing stems")), patch(
            "app.domain.saju.basic_reading._dohwa", side_effect=QuestionUnavailable("missing methods")):
            timing_only = self.overview()
        self.assertEqual([section.id for section in timing_only.sections], ["luck", "annual"])
        self.assertNotIn("표시된 천간·지장간", timing_only.memo.reading)
        self.assertNotIn("방법별 신살 위치", timing_only.memo.reading)
        with patch("app.domain.saju.basic_reading._luck", side_effect=QuestionUnavailable("missing cycles")), patch(
            "app.domain.saju.basic_reading._annual", side_effect=QuestionUnavailable("missing year")):
            positions_only = self.overview()
        self.assertEqual([section.id for section in positions_only.sections], ["wealth", "dohwa"])
        self.assertNotIn("대운 구간", positions_only.memo.reading)
        self.assertNotIn("입춘 세운", positions_only.memo.reading)
        self.assertNotIn("날짜는", positions_only.memo.reading)

    def test_common_theme_is_explained_once_and_actual_difference_is_connected(self):
        normal = self.overview("normal")
        luck = self.memo_section(normal, "luck")
        self.assertEqual(luck.text.count("내 기준과 함께 맡은 몫"), 1)
        self.assertIn("큰 분류는 같은 거야", luck.text)
        self.assertIn("겁재 이름과 다음 대운의 비견 이름", luck.text)
        english_luck = self.memo_section(self.overview("normal", "en"), "luck")
        self.assertEqual(english_luck.text.count("personal standards and shared ownership"), 1)
        boundary = self.overview()
        boundary_luck = self.memo_section(boundary, "luck")
        self.assertIn("앞쪽은 관성, 뒤쪽은 인성으로 큰 분류도 달라", boundary_luck.text)
        annual = self.memo_section(boundary, "annual")
        self.assertEqual(annual.text.count("책임·역할·평가 기준"), 1)
        self.assertIn("‘일·책임·평가’ 이야기가 겹쳐", boundary.headline)
        self.assertIn("내 몫과 함께하는 일", normal.headline)
        self.assertIn("돈과 보상", normal.headline)

    def test_same_current_and_annual_label_does_not_invent_a_difference(self):
        same = self.overview("normal", as_of=datetime(2032, 10, 8, 12, tzinfo=ZoneInfo("Asia/Seoul")))
        self.assertEqual(same.source_context["luck"]["current_stem_ten_god"], same.source_context["annual"]["annual"]["stem_ten_god"])
        annual = self.memo_section(same, "annual")
        self.assertIn("두 항목의 세부 이름도 같아", annual.text)
        self.assertNotIn("큰 분류도 달라", annual.text)

    def test_wealth_connects_shared_character_and_only_actual_layers(self):
        normal = self.memo_section(self.overview("normal"), "wealth")
        self.assertIn("같은 정(丁) 글자가 연주의 겉 천간과 시주의 지장간에 각각 있어", normal.text)
        self.assertNotIn("겉에 없다는 말", normal.text)
        english = self.memo_section(self.overview("normal", "en"), "wealth")
        self.assertTrue(english.text.startswith("The visible wealth stems"))
        self.assertIn("The same Jeong(丁) character", english.text)
        boundary = self.memo_section(self.overview(), "wealth")
        self.assertIn("재성이 확인된 쪽은 겉 천간이 아니라 지장간", boundary.text)
        self.assertIn("을(乙) 글자는 연주·일주에 각각", boundary.text)
        unknown = self.memo_section(self.overview("unknown"), "wealth")
        self.assertIn("지장간에서는 추가 재성 글자가 잡히지 않았어", unknown.text)
        self.assertNotIn("같은 정(丁)", unknown.text)

    def test_plain_body_needs_no_ten_god_or_method_lookup(self):
        for case in self.inputs:
            reading = self.overview(case)
            body = self.text(reading) + " ".join(section.title for section in reading.sections)
            self.assertNotRegex(body, r"[\u4e00-\u9fff]|십성|천간|지장간|정관|편관|편인|함지도화|왕지도화|목욕도화")
            self.assertEqual([section.id for section in reading.sections], [section.id for section in reading.memo_sections])
            self.assertIn("실제 수입", " ".join(reading.limitations))
        boundary = self.overview()
        self.assertIn("돈과 보상", self.text(boundary))
        self.assertIn("총 3곳", self.text(boundary))
        self.assertIn("태어난 해·태어난 달·태어난 날", self.text(boundary))
        self.assertIn("도화는 연애 풀이에서 참고하는 사주 속 표시", self.text(boundary))
        self.assertIn("사주는 여러 해씩 묶어서도 읽어", self.text(boundary))
        self.assertIn("다른 기준에서는 잡혔어", self.text(boundary))
        self.assertIn("지장간", self.evidence_text(boundary))
        self.assertIn("목 0개", " ".join(boundary.memo.facts))

    def test_plain_and_memo_share_actual_fact_refs_and_keep_limits_outside(self):
        for locale in ("ko", "en"):
            for case in self.inputs:
                reading = self.overview(case, locale)
                for body, memo in zip(reading.sections, reading.memo_sections):
                    self.assertEqual(body.fact_ids, memo.fact_ids)
                self.assertTrue(reading.limitations)
                if reading.source_context["critical_uncertainty"] or case == "unknown":
                    self.assertTrue(reading.notices)
    def test_current_cycle_uses_precise_boundary_not_coarse_year(self):
        base = self.bases["boundary"]
        cycle = next(item for item in base.manse.luck_cycles if item.gan_zhi == "丁卯")
        transition = datetime.fromisoformat(cycle.change_datetime).replace(tzinfo=ZoneInfo("Asia/Seoul"))
        before = self.overview(as_of=transition - timedelta(seconds=1))
        after = self.overview(as_of=transition)
        self.assertEqual(before.source_context["luck"]["current_stem_ten_god"], "정관")
        self.assertEqual(after.source_context["luck"]["current_stem_ten_god"], "편인")

    def test_integration_reuses_one_calculation_and_never_generates_questions(self):
        calculate = Mock(return_value=model_copy_compat(self.bases["boundary"], deep=True))
        with patch("app.domain.saju.question_reading.create_question_reading", side_effect=AssertionError("No per-question generation")):
            basic = create_basic_reading(payload=self.inputs["boundary"], trace_id="body", service_name="tests", as_of=NOW, calculate=calculate)
        self.assertEqual(calculate.call_count, 1)
        self.assertEqual(calculate.call_args.kwargs["report_mode"], "none")
        self.assertIsNone(basic.result.free_preview)
        self.assertIsNone(basic.result.interpretation)
        self.assertEqual(basic.pipeline_status.llm_formatting, "skipped")
        self.assertEqual(basic.basic_reading.provider, "deterministic")
        self.assertEqual(model_to_dict(basic.question_flow.versions), model_to_dict(QuestionVersions()))
        for question_id in ("luck.current_next", "period.this_year", "wealth.locations", "stars.dohwa"):
            answer = create_question_reading(payload=SajuQuestionRequest(input=self.inputs["boundary"], question_id=question_id),
                trace_id="question", service_name="tests", as_of=NOW, calculate=calculate)
            for fact in answer.facts:
                basic_fact = next(item for item in basic.basic_reading.facts if item.id == fact.id)
                self.assertEqual(basic_fact.value, fact.value)
        self.assertEqual(calculate.call_count, 1)


class BasicReadingHttpTests(unittest.IsolatedAsyncioTestCase):
    async def test_basic_http_serialized_fact_paths_resolve_exactly(self):
        clear_question_caches()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/saju/basic", json=json.loads(json.dumps(model_to_dict(input_payload()), default=str)))
        self.assertEqual(response.status_code, 200, response.text)
        basic = response.json()
        reading = basic["basic_reading"]
        known = {fact["id"] for fact in reading["facts"]}
        for fact in reading["facts"]:
            self.assertEqual(fact["value"], resolve(basic, fact["source_path"]), fact["id"])
        for section in reading["sections"] + reading["memo_sections"]:
            self.assertTrue(set(section["fact_ids"]) <= known)
        self.assertEqual(reading["versions"]["copy"], "basic-reading-copy-2026-10-08.7")
        self.assertEqual(reading["versions"]["format"], "basic-overview-v2")
        self.assertEqual(basic["question_flow"]["versions"]["copy"], "question-copy-2026-10-24.1")
        self.assertEqual(basic["pipeline_status"]["llm_formatting"], "skipped")


if __name__ == "__main__":
    unittest.main()
