"""Fact-linked detail, independent alternates and unchanged critical guards."""
from types import SimpleNamespace
import unittest

from app.domain.saju.natal_structure import derive_profile, render_structure, select_conclusions
from app.domain.saju.natal_structure_contracts import NatalStructureReading
from app.domain.saju.distinctive_contracts import DistinctiveReading
from app.domain.saju.reading_detail import build_reading_details, RULES
from app.domain.saju.services.build_manse import HIDDEN_STEMS_BY_BRANCH


class ReadingDetailTests(unittest.TestCase):
    def natal(self, day="庚辰"):
        chart = {"year": "戊辰", "month": "癸亥", "day": day, "time": "丙子"}
        refs = {k: "natal.pillar." + k for k in chart}
        profile = derive_profile(chart, {k: HIDDEN_STEMS_BY_BRANCH[v[1]] for k, v in chart.items()}, refs)
        blocks = render_structure(profile, refs, "ko")
        return NatalStructureReading(status="available", profile=profile, blocks=blocks,
            conclusions=select_conclusions(profile, blocks, "ko"),
            facts=[{"id": ref} for ref in refs.values()])

    def details(self, natal, locale="ko"):
        return build_reading_details(natal=natal, distinctive=DistinctiveReading(status="no_matching_rules"), information=None, locale=locale)

    def test_money_locations_use_each_actual_category_not_visible_or_global_absence(self):
        value = self.natal()
        money = next(b for b in self.details(value) if b.id == "detail.money")
        self.assertIn("태어난 해 · 태어난 날의 안쪽 구성", money.text)
        self.assertIn("태어난 달의 안쪽 구성", money.text)
        self.assertEqual(money.conditions, {"meaning": "both", "layer": "hidden_only"})
        self.assertFalse(money.provisional)
        self.assertTrue(set(money.fact_ids) <= {f["id"] for f in value.facts})

    def test_alternate_is_not_copied_from_primary_and_all_claims_keep_sources(self):
        first, other = self.natal(), self.natal("己卯")
        first.status = "conditional"
        first.facts.append({"id": "natal.alternate"})
        first.comparisons = [{"profile": other.profile}]
        for locale in ("ko", "en"):
            details = self.details(first, locale)
            changed = next(b for b in details if b.id == "detail.alternate_money")
            self.assertEqual(changed.conditions, {"selected_layer": "hidden_only", "alternate_layer": "visible"})
            for block in details:
                self.assertTrue(block.provisional)
                self.assertTrue(set(block.rule_ids) <= set(RULES))
                self.assertTrue(set(block.fact_ids) <= {f["id"] for f in first.facts})
                self.assertNotRegex(block.text, r"\d+\s*%|상위\s*\d|반드시.*(?:취업|결혼)|percentile|probability")
                if locale == "en":
                    self.assertNotRegex(block.title + block.text, r"[가-힣一-龥]")

    def test_unknown_or_unexplained_critical_never_receives_invented_detail(self):
        self.assertEqual(self.details(NatalStructureReading()), [])
        value = self.natal()
        value.status = "blocked_calculation"
        self.assertEqual(self.details(value), [])

    def test_shared_findings_require_both_independently_derived_charts(self):
        first, other = self.natal(), self.natal("己卯")
        first.status = "conditional"
        first.facts.append({"id": "natal.alternate"})
        first.comparisons = [{"profile": other.profile}]
        blocks = {b.id: b for b in self.details(first)}
        self.assertEqual(blocks["detail.shared_money"].conditions,
                         {"shared_money_categories": sorted({"정재", "편재"})})
        self.assertIn("공통으로 확인돼", blocks["detail.shared_money"].text)
        self.assertTrue(blocks["detail.shared_support"].conditions["resource_present_in_both"])
        other.profile["resource_present"] = False
        other.profile["wealth_occurrences"] = []
        blocks = {b.id: b for b in self.details(first)}
        self.assertNotIn("detail.shared_support", blocks)
        self.assertNotIn("detail.shared_money", blocks)

    def test_no_cycle_or_unrelated_day_reference_cannot_create_cycle_detail(self):
        value = self.natal()
        information = SimpleNamespace(facts=[SimpleNamespace(id="information.day_master", value="己")])
        blocks = build_reading_details(natal=value, distinctive=DistinctiveReading(status="no_matching_rules"), information=information, locale="ko")
        self.assertFalse(any(b.category == "luck_flow" for b in blocks))
