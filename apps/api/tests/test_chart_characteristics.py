"""Universal pattern scope, emphasis meaning and narrow conditional boundaries."""
from datetime import datetime, timezone
import unittest

from lunar_python.util import LunarUtil

from app.domain.saju.chart_characteristics import evaluate_characteristics, group_support
from app.domain.saju.pydantic_compat import model_copy_compat, model_to_dict
from app.domain.saju.schemas import SajuPreviewRequest, UncertaintyFlagSummary
from app.domain.saju.services.build_chart_characteristics import (
    build_chart_characteristics, _occurrences, KEYS,
)
from app.domain.saju.services.build_manse import HIDDEN_STEMS_BY_BRANCH
from app.domain.saju.services.preview_orchestrator import create_saju_preview_response
from app.tools.verify_question_flow import resolve_fact


def occurrence(group, pillar="year", layer="visible", month_main=False):
    return {"group": group, "pillar": pillar, "layer": layer, "month_main": month_main,
            "god": {"output": "상관", "resource": "정인", "officer": "정관", "peer": "비견", "wealth": "정재"}[group],
            "fact_id": pillar}


class EmphasisTests(unittest.TestCase):
    def test_one_group_criteria_and_same_pillar_deduplication(self):
        base = [occurrence("output"), occurrence("output", layer="hidden")]
        self.assertEqual(group_support(base, "output")["level"], "supporting")
        self.assertEqual(group_support(base + base, "output"), group_support(base, "output"))
        base.append(occurrence("output", "month", "hidden", True))
        self.assertEqual(group_support(base, "output")["level"], "prominent")
        separate = [occurrence("output"), occurrence("resource", "month", "hidden", True)]
        self.assertEqual(group_support(separate, "output")["level"], "supporting")
        self.assertEqual(group_support(separate, "resource")["level"], "supporting")

    def test_hidden_only_and_unmatched_rules_do_not_create_levels(self):
        self.assertEqual(evaluate_characteristics(occurrences=[], locale="ko"), [])
        self.assertEqual(evaluate_characteristics(occurrences=[occurrence("output")], locale="ko"), [])
        hidden = [occurrence("output", layer="hidden"), occurrence("resource", "day", "hidden")]
        self.assertEqual(evaluate_characteristics(occurrences=hidden, locale="ko"), [])

    def test_benefit_and_burden_remain_separate_not_averaged(self):
        facts = [occurrence("output"), occurrence("resource", "month"), occurrence("officer", "time")]
        items = evaluate_characteristics(occurrences=facts, locale="ko")
        self.assertTrue(any(i.direction == "advantage" for i in items))
        self.assertTrue(any(i.direction == "burden" for i in items))
        self.assertEqual(len({(i.direction, i.focus_group) for i in items}), len(items))
        no_officer = evaluate_characteristics(occurrences=facts[:-1], locale="ko")
        self.assertNotIn("expression_against_rules", {i.id for i in no_officer})

    def test_exclusion_and_minimum_emphasis_are_enforced(self):
        facts = [occurrence("officer"), occurrence("officer", "month", "hidden", True), occurrence("peer", "time")]
        self.assertIn("responsibility_without_support", {i.id for i in evaluate_characteristics(occurrences=facts, locale="ko")})
        facts.append(occurrence("resource", "month"))
        self.assertNotIn("responsibility_without_support", {i.id for i in evaluate_characteristics(occurrences=facts, locale="ko")})

    def test_visible_repeat_condition_and_explicit_emphasis_reason(self):
        facts = [occurrence("officer"), occurrence("wealth", "month")]
        self.assertNotIn("duties_and_compensation", {i.id for i in evaluate_characteristics(occurrences=facts, locale="ko")})
        facts.append(occurrence("officer", "time"))
        items = evaluate_characteristics(occurrences=facts, locale="ko")
        self.assertIn("duties_and_compensation", {i.id for i in items})
        self.assertTrue(all(i.emphasis_reason and i.emphasis_label in i.emphasis_reason for i in items))

    def test_no_population_or_probability_claims_and_localized_main(self):
        facts = [occurrence(g, "month" if g == "resource" else "year") for g in ("peer", "output", "wealth", "officer", "resource")]
        for locale in ("ko", "en"):
            for item in evaluate_characteristics(occurrences=facts, locale=locale):
                main = " ".join([item.title, item.conclusion, item.reason, item.condition, item.emphasis_label])
                self.assertNotRegex(main, r"\d+\s*%|상위\s*\d|백분위|percentile|probability")
                if locale == "en":
                    self.assertNotRegex(main + item.memo_body, r"[가-힣]")

    def test_all_sixty_day_pillars_and_twelve_months_use_same_rules(self):
        totals = set()
        for day in LunarUtil.JIA_ZI:
            for month in LunarUtil.JIA_ZI[:12]:
                chart = {"year": "甲子", "month": month, "day": day, "time": "丙寅"}
                hidden = {k: HIDDEN_STEMS_BY_BRANCH[v[1]] for k, v in chart.items()}
                occurrences = _occurrences(chart, hidden, {k: k for k in KEYS})
                self.assertFalse(any(o["pillar"] == "day" and o["layer"] == "visible" for o in occurrences))
                items = evaluate_characteristics(occurrences=occurrences, locale="ko")
                totals.update(i.id for i in items)
                self.assertLessEqual(len(items), 4)
        self.assertGreaterEqual(len(totals), 7)


class CharacteristicBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.now = datetime(2026, 10, 9, tzinfo=timezone.utc)
        cls.request = SajuPreviewRequest(birth_date="1988-11-20", birth_time="23:30", gender="male", region_id="kr-chungbuk-jecheon")
        cls.boundary = create_saju_preview_response(payload=cls.request, trace_id="characteristic-boundary", service_name="test",
            debug_requested=False, report_mode="none", as_of=cls.now)
        normal = SajuPreviewRequest(birth_date="1997-09-18", birth_time="14:30", gender="female", region_id="kr-seoul")
        cls.normal = create_saju_preview_response(payload=normal, trace_id="characteristic-normal", service_name="test",
            debug_requested=False, report_mode="none", as_of=cls.now)

    def build(self, base=None, locale="ko"):
        return build_chart_characteristics(base=base or self.boundary, locale=locale)

    def test_normal_and_conditional_keep_source_facts_and_legacy_hold(self):
        for base, expected in ((self.normal, "available"), (self.boundary, "conditional")):
            before = model_to_dict(base)
            result = self.build(base)
            self.assertEqual(result.status, expected)
            self.assertTrue(result.items)
            self.assertEqual(before, model_to_dict(base))
            source = model_to_dict(base)
            for fact in result.facts:
                self.assertEqual(resolve_fact(source, fact.source_path), fact.value)
            ids = {f.id for f in result.facts}
            for item in result.items + [i for c in result.comparisons for i in c.items]:
                self.assertTrue(set(item.fact_ids) <= ids)
        self.assertTrue(any(f.severity == "critical" for f in self.boundary.result.uncertainty_summary))

    def test_alternate_recomputes_relations_and_rule_results(self):
        result = self.build()
        self.assertEqual(len(result.comparisons), 1)
        alternate = result.comparisons[0]
        self.assertEqual(alternate.chart["day"], "己卯")
        self.assertNotEqual({i.id for i in result.items}, {i.id for i in alternate.items})
        self.assertEqual(result.derivations[0]["day_stem"], "庚")
        self.assertEqual(result.derivations[1]["day_stem"], "己")
        self.assertNotEqual(result.derivations[0]["occurrences"][0]["god"], result.derivations[1]["occurrences"][0]["god"])

    def test_other_critical_or_unverified_alternate_remains_blocked(self):
        base = model_copy_compat(self.boundary, deep=True)
        base.result.uncertainty_summary.append(UncertaintyFlagSummary(code="year_or_month_pillar_may_change", severity="critical",
            affected_fields=["month_pillar"], user_message="boundary", developer_message="test"))
        self.assertEqual(self.build(base).status, "blocked_calculation")
        base = model_copy_compat(self.boundary, deep=True)
        flag = next(f for f in base.result.uncertainty_summary if f.code == "midnight_rule_changes_day_pillar")
        flag.evidence["sect2_00_changes_day"]["month_pillar"] = "甲子"
        self.assertEqual(self.build(base).status, "blocked_calculation")

    def test_unknown_time_and_missing_pillar_are_not_released(self):
        base = model_copy_compat(self.boundary, deep=True)
        base.manse.meta.hour_pillar_enabled = False
        self.assertEqual(self.build(base).status, "blocked_calculation")
        self.assertEqual(self.build(base).items, [])

    def test_malformed_hidden_stems_are_blocked_but_order_is_irrelevant(self):
        original = self.build()
        base = model_copy_compat(self.boundary, deep=True)
        for key in KEYS:
            getattr(base.manse.pillars, key).hidden_stems.reverse()
        self.assertEqual([i.dict() for i in self.build(base).items], [i.dict() for i in original.items])
        base.manse.pillars.month.hidden_stems = []
        self.assertEqual(self.build(base).status, "blocked_calculation")

    def test_element_counts_and_stars_do_not_change_structural_judgments(self):
        original = self.build()
        base = model_copy_compat(self.boundary, deep=True)
        base.manse.special_stars = []
        base.manse.elements.wood = 99
        base.manse.elements.water = 0
        self.assertEqual([i.dict() for i in self.build(base).items], [i.dict() for i in original.items])
