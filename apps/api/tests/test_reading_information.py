"""Found-only terms, original sources and calculation/interpretation separation."""
from datetime import datetime, timezone
import unittest
from unittest.mock import Mock

from app.domain.saju.category_reading import create_category_reading
from app.domain.saju.localization import localize_ten_god
from app.domain.saju.pydantic_compat import model_copy_compat, model_to_dict
from app.domain.saju.reading_information import build_reading_information
from app.domain.saju.schemas import SajuPreviewRequest
from app.domain.saju.services.preview_orchestrator import create_saju_preview_response
from app.domain.saju.services.build_interpretation_payload import build_interpretation_payload
from app.tools.verify_question_flow import resolve_fact


class ReadingInformationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.now = datetime(2026, 10, 9, tzinfo=timezone.utc)
        cls.request = SajuPreviewRequest(birth_date="1988-11-20", birth_time="23:30", gender="male", region_id="kr-chungbuk-jecheon")
        cls.base = create_saju_preview_response(payload=cls.request, trace_id="test-info", service_name="test",
                                               debug_requested=False, report_mode="none", as_of=cls.now)

    def info(self, base=None, locale="ko"):
        return build_reading_information(base=base or self.base, locale=locale, gender="male", as_of=self.now)

    def test_found_stars_preserve_methods_and_real_sources(self):
        info = self.info()
        self.assertTrue(info.interpretation_withheld)
        self.assertTrue(all(item.provisional for item in info.items))
        stars = [item for item in info.items if item.kind == "traditional_term_definition"]
        self.assertTrue(stars)
        self.assertTrue(all(item.methods and item.star_keys and item.matched_pillars for item in stars))
        source = {**model_to_dict(self.base), "input": model_to_dict(self.request)}
        for fact in info.facts:
            self.assertEqual(resolve_fact(source, fact.source_path), fact.value)
        ids = {fact.id for fact in info.facts}
        self.assertTrue(all(set(item.fact_ids) <= ids for item in info.items))
        self.assertFalse(any("dohwa-location" in item.star_keys for item in stars))

    def test_detected_adverse_meanings_are_not_omitted_or_promoted_to_personal_verdicts(self):
        normal = SajuPreviewRequest(birth_date="1997-09-18", birth_time="14:30", region_id="kr-seoul", gender="female")
        normal_base = create_saju_preview_response(payload=normal, trace_id="adverse-glossary", service_name="test",
                                                   debug_requested=False, report_mode="none", as_of=self.now)
        for base, meanings in ((self.base, {"hwagae": ("고독", "solitude"), "gwimungwan": ("집착", "fixation")}),
                               (normal_base, {"gongmang": ("지연", "delays")})):
            for locale in ("ko", "en"):
                info = build_reading_information(base=base, locale=locale, gender="male" if base is self.base else "female", as_of=self.now)
                for term, labels in meanings.items():
                    item = next(item for item in info.items if item.id == "star." + term)
                    self.assertIn(labels[0 if locale == "ko" else 1], item.body)
                    self.assertEqual(item.kind, "traditional_term_definition")
                    self.assertEqual(item.provisional, info.interpretation_withheld)
                    originals = [fact.value for fact in info.facts if fact.id in item.fact_ids and fact.id.startswith("information.star.")]
                    self.assertTrue(any(labels[0] in star["usage_keywords"] for star in originals))
                    self.assertNotIn("나쁜 사주" if locale == "ko" else "bad chart", item.body)
                if "gongmang" in meanings:
                    item = next(item for item in info.items if item.id == "star.gongmang")
                    self.assertIn("약화" if locale == "ko" else "weakened", item.body)

    def test_absent_stars_and_no_matches_do_not_generate_placeholders(self):
        base = model_copy_compat(self.base, deep=True)
        for star in base.manse.special_stars:
            star.active, star.count, star.matches = True, 99, []
        self.assertFalse(any(item.kind == "traditional_term_definition" for item in self.info(base).items))
        reading = create_category_reading(payload=self.request, trace_id="test-info", service_name="test",
                                          calculate=Mock(return_value=base), as_of=self.now)
        self.assertNotIn("stars.dohwa", [q.id for q in reading.question_flow.questions])
        self.assertFalse(any(item.kind == "traditional_term_definition" for section in reading.category_reading.sections for item in section.information))

    def test_inactive_and_disabled_hour_matches_cannot_leak(self):
        base = model_copy_compat(self.base, deep=True)
        for star in base.manse.special_stars:
            star.active = False
        target = next(star for star in base.manse.special_stars if star.key == "wangji-dohwa")
        target.active = True
        target.matches = [m for m in target.matches if m.pillar_key == "time"]
        base.manse.pillars.time.enabled = False
        base.manse.meta.visible_pillar_keys = [key for key in base.manse.meta.visible_pillar_keys if key != "time"]
        self.assertFalse(any(item.kind == "traditional_term_definition" for item in self.info(base).items))

    def test_duplicate_anchor_methods_union_positions_without_location_tags(self):
        base = model_copy_compat(self.base, deep=True)
        hwagae = [star for star in base.manse.special_stars if star.family == "hwagae" and star.active]
        self.assertEqual(len(hwagae), 2)
        items = [item for item in self.info(base).items if item.id == "star.hwagae"]
        self.assertEqual(len(items), 1)
        self.assertEqual(set(items[0].star_keys), {s.key for s in hwagae})
        self.assertEqual(items[0].matched_pillars, ["year", "day"])
        self.assertIn("star.wangji", {item.id for item in self.info().items})
        self.assertNotIn("star.hamji", {item.id for item in self.info().items})

    def test_hidden_stems_have_explicit_relations_and_wealth_locations(self):
        info = self.info()
        wealth = next(item for item in info.items if item.id == "structure.wealth")
        self.assertIn("태어난 해·태어난 날", wealth.body)
        self.assertIn("거래·자원 운용: 태어난 달", wealth.body)
        self.assertIn("재산·보상: 태어난 해·태어난 날", wealth.body)
        self.assertNotIn("정재", wealth.body)
        self.assertIn("(정재)", wealth.memo_body)
        self.assertIn("(편재): 태어난 달", wealth.memo_body)
        relations = info.derivations[0]["relations"]
        self.assertEqual(len([r for r in relations if r["god"] in {"정재", "편재"}]), 3)
        self.assertFalse(any(r["layer"] == "visible" and r["god"] in {"정재", "편재"} for r in relations))

    def test_provisional_visible_and_hidden_relations_use_same_selected_day(self):
        request = SajuPreviewRequest(birth_date="1988-06-10", birth_time="00:00", gender="female",
                                    region_id="kr-seoul", is_birth_time_estimated=True)
        base = create_saju_preview_response(payload=request, trace_id="mixed-relations", service_name="test",
                                           debug_requested=False, report_mode="none", as_of=self.now)
        original = model_to_dict(base)
        for locale in ("ko", "en"):
            info = self.info(base, locale)
            relations = info.derivations[0]["relations"]
            month = next(r for r in relations if r["pillar"] == "month" and r["layer"] == "visible")
            self.assertEqual(month["god"], "식신")
            self.assertNotEqual(month["god"], month["reported_god"])
            item = next(i for i in info.items if i.id == "structure.day_month")
            self.assertIn(localize_ten_god("식신", locale), item.memo_body)
            self.assertIn("원본 월간 분류" if locale == "ko" else "The source reports", item.memo_body)
            self.assertTrue(info.interpretation_withheld)
        self.assertEqual(model_to_dict(base), original)

    def test_unknown_time_excludes_hour_and_cycles_but_retains_provisional_facts(self):
        request = model_copy_compat(self.request, update={"is_birth_time_estimated": True})
        base = create_saju_preview_response(payload=request, trace_id="unknown-info", service_name="test",
                                            debug_requested=False, report_mode="none", as_of=self.now)
        info = self.info(base)
        self.assertTrue(info.interpretation_withheld)
        self.assertFalse(any(item.id.startswith("cycle.") for item in info.items))
        self.assertFalse(any("time" in item.matched_pillars for item in info.items))
        self.assertFalse(any(fact.source_path == "manse.pillars.time" for fact in info.facts))
        reading = create_category_reading(payload=request, trace_id="unknown-memo", service_name="test",
            calculate=Mock(return_value=base), as_of=self.now)
        for section in reading.category_reading.sections:
            if section.information:
                self.assertIn("임시", section.publication.memo_body)

    def test_critical_never_supplies_a_period_comparison(self):
        self.assertNotIn("cycle.comparison", {item.id for item in self.info().items})

    def test_opened_provisional_information_keeps_the_selected_chart_condition(self):
        for locale in ("ko", "en"):
            info = self.info(locale=locale)
            for item in info.items:
                self.assertIn("임시" if locale == "ko" else "provisional", item.body)
                self.assertIn("확정" if locale == "ko" else "not confirmed", item.memo_body)
                if locale == "ko":
                    self.assertNotIn("네 사주", item.body)
                    self.assertNotIn("명식를", item.body)
            reading = create_category_reading(payload=model_copy_compat(self.request, update={"locale": locale}),
                trace_id="scoped-memo", service_name="test", calculate=Mock(return_value=self.base), as_of=self.now)
            for section in reading.category_reading.sections:
                if section.information and section.publication.scope == "provisional_information":
                    self.assertIn("임시" if locale == "ko" else "provisional", section.publication.memo_body)

    def test_plain_information_retains_technical_relations_in_folded_memos(self):
        for locale in ("ko", "en"):
            info = self.info(locale=locale)
            by_id = {item.id: item for item in info.items}
            for item_id in ("structure.wealth", "structure.partner", "structure.officer", "structure.work"):
                item = by_id[item_id]
                self.assertNotIn("(", item.body)
                self.assertIn("(", item.memo_body)
            current = by_id["cycle.current"]
            self.assertNotIn("정관" if locale == "ko" else "Direct Officer", current.body)
            self.assertIn("정관" if locale == "ko" else "Direct Officer", current.memo_body)
            source = next(fact.value for fact in info.facts if fact.id == "information.cycle.current")
            self.assertIn(source["start_datetime"], current.memo_body)

    def test_codex_payload_receives_information_without_releasing_critical_rules(self):
        payload = build_interpretation_payload(request=self.request, response=self.base, as_of=self.now)
        self.assertTrue(payload.reading_information.items)
        self.assertTrue(payload.reading_information.interpretation_withheld)
        self.assertFalse(payload.reading_plan.sections)

    def test_english_main_is_localized_and_cycle_memo_keeps_exact_boundaries(self):
        info = self.info(locale="en")
        import re
        self.assertTrue(all(not re.search(r"[가-힣一-龥]", item.body + item.title) for item in info.items))
        cycle = next(item for item in info.items if item.id == "cycle.next")
        self.assertIn("2034", cycle.body)
        self.assertIn("Asia/Seoul", cycle.memo_body)
        self.assertIn("07:21:17", cycle.memo_body)

    def test_pairs_are_specific_and_inconsistent_match_values_are_rejected(self):
        info = self.info()
        wonjin = next(item for item in info.items if item.id == "star.wonjin")
        self.assertIn("태어난 해 ↔ 태어난 달", wonjin.body)
        self.assertIn("태어난 달 ↔ 태어난 날", wonjin.body)
        base = model_copy_compat(self.base, deep=True)
        for star in base.manse.special_stars:
            for match in star.matches:
                match.matched_value = "invalid"
        self.assertFalse(any(item.kind == "traditional_term_definition" for item in self.info(base).items))
