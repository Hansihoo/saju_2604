"""Natal structure: real roots/support, hidden wealth and strict uncertainty."""
from datetime import datetime, timezone
import unittest

from lunar_python.util import LunarUtil

from app.domain.saju.natal_structure import build_natal_structure, catalog, derive_profile, render_structure, select_conclusions
from app.domain.saju.pydantic_compat import model_copy_compat, model_to_dict
from app.domain.saju.schemas import SajuPreviewRequest, UncertaintyFlagSummary
from app.domain.saju.services.build_manse import HIDDEN_STEMS_BY_BRANCH
from app.domain.saju.services.build_chart_characteristics import KEYS, _relation, _stem
from app.domain.saju.services.preview_orchestrator import create_saju_preview_response
from app.tools.verify_question_flow import resolve_fact


def profile(chart):
    return derive_profile(chart, {k: HIDDEN_STEMS_BY_BRANCH[v[1]] for k, v in chart.items()}, {k: k for k in KEYS})


class UniversalStructureTests(unittest.TestCase):
    def test_sixty_days_and_twelve_months_use_canonical_relationships(self):
        seen = set()
        for day in LunarUtil.JIA_ZI:
            for month in LunarUtil.JIA_ZI[:12]:
                p = profile({"year": "戊辰", "month": month, "day": day, "time": "丙子"})
                self.assertEqual(p["month_group"], _relation(day[0], p["month_main_stem"])[1])
                seen.add(p["month_group"])
                for locale in ("ko", "en"):
                    blocks = render_structure(p, {k: k for k in KEYS}, locale)
                    self.assertGreaterEqual(len(blocks), 3)
                    for b in blocks:
                        self.assertTrue(all(r in catalog()["rules"] for r in b.rule_ids))
                        self.assertEqual(b.fact_ids, list(KEYS))
                        self.assertNotRegex(b.text, r"\d+\s*%|상위\s*\d|percentile|probability")
                        self.assertNotRegex(b.text, r"태극귀인|신약|신강|용신|월령|지장간|재성|인성")
                        if locale == "en":
                            self.assertNotRegex(b.title + b.text, r"[가-힣一-龥]")
                    conclusion = select_conclusions(p, blocks, locale)[0]
                    self.assertTrue(conclusion.one_line)
                    self.assertNotIn("\n", conclusion.one_line)
                    self.assertNotRegex(conclusion.one_line, r"어디서든|반드시|평생|무조건|신강|신약|용신|\d+%")
                    self.assertEqual(conclusion.conditions["month_group"], p["month_group"])
        self.assertEqual(seen, {"output", "resource", "wealth", "officer", "peer"})

    def test_hidden_wealth_is_not_total_absence_and_support_is_not_a_root(self):
        p = profile({"year": "戊辰", "month": "癸亥", "day": "庚辰", "time": "丙子"})
        self.assertEqual(p["month_group"], "output")
        self.assertEqual(p["root_pillars"], [])
        self.assertTrue(p["resource_present"])
        self.assertEqual(p["wealth_layer"], "hidden_only")
        self.assertEqual({o["pillar"] for o in p["wealth_occurrences"]}, {"year", "month", "day"})
        blocks = render_structure(p, {k: k for k in KEYS}, "ko")
        self.assertIn("혼자서 넉넉히 감당한다고 볼 수는 없어", blocks[1].text)
        self.assertIn("배움이나 도움", blocks[1].text)
        self.assertIn("세부 구성에서 확인돼", blocks[2].text)
        self.assertEqual(blocks[-1].id, "output_officer")

    def test_changing_the_day_rebuilds_roots_and_month_relationship(self):
        original = {"year": "戊辰", "month": "癸亥", "day": "庚辰", "time": "丙子"}
        p, q = profile(original), profile({**original, "day": "己卯"})
        self.assertNotEqual(p["month_group"], q["month_group"])
        self.assertNotEqual(p["root_pillars"], q["root_pillars"])
        self.assertNotEqual(p["wealth_layer"], q["wealth_layer"])
        expected = []
        for key in KEYS:
            if key != "day":
                expected.append(_relation("己", q["chart"][key][0]))
            expected.extend(_relation("己", _stem(s)) for s in HIDDEN_STEMS_BY_BRANCH[q["chart"][key][1]])
        self.assertEqual([(o["god"], o["group"]) for o in q["occurrences"]], expected)
        self.assertEqual(p["degree_scope"], "positions_and_relationships_only_not_final_strength")

    def test_missing_or_corrupt_hidden_data_fails_instead_of_inventing_roots(self):
        chart = {"year": "戊辰", "month": "癸亥", "day": "庚辰", "time": "丙子"}
        hidden = {k: HIDDEN_STEMS_BY_BRANCH[v[1]] for k, v in chart.items()}
        hidden["day"] = []
        with self.assertRaises(ValueError):
            derive_profile(chart, hidden, {k: k for k in KEYS})

    def test_selected_conclusion_connects_month_and_support_without_money_location_padding(self):
        for day in ("庚辰", "己卯"):
            p = profile({"year": "戊辰", "month": "癸亥", "day": day, "time": "丙子"})
            for locale in ("ko", "en"):
                blocks = render_structure(p, {k: k for k in KEYS}, locale)
                conclusions = select_conclusions(p, blocks, locale)
                main = conclusions[0]
                self.assertEqual(main.source_block_ids, ["month_context", "roots_and_support"])
                self.assertEqual(main.conditions["month_group"], p["month_group"])
                self.assertEqual(main.conditions["root_pillars"], p["root_pillars"])
                self.assertEqual(main.conditions["resource_present"], p["resource_present"])
                self.assertIn("month_context", main.rule_ids)
                self.assertIn("roots_and_support", main.rule_ids)
                # Preserve meaning and counterconditions that the former
                # first-paragraph projection silently removed.
                month = next(b for b in blocks if b.id == "month_context")
                support = next(b for b in blocks if b.id == "roots_and_support")
                self.assertIn(month.text, main.text)
                self.assertIn(support.text, main.text)
                self.assertNotIn("wealth_layer", main.rule_ids)
                self.assertTrue(any(b.id == "wealth_layer" for b in blocks))
                self.assertNotRegex(main.text, r"지장간|재성|월령|신강|신약|용신|관계과|준비과")


class StructureBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = SajuPreviewRequest(birth_date="1988-11-20", birth_time="23:30", gender="male", region_id="kr-chungbuk-jecheon")
        cls.base = create_saju_preview_response(payload=cls.request, trace_id="natal-test", service_name="test", debug_requested=False,
            report_mode="none", as_of=datetime(2026, 10, 10, tzinfo=timezone.utc))

    def test_real_boundary_retains_hold_exact_sources_and_rebuilt_alternative(self):
        reading = build_natal_structure(base=self.base, locale="ko")
        self.assertEqual(reading.status, "conditional")
        self.assertTrue(reading.assumption)
        self.assertIsNone(self.base.result.interpretation)
        source = model_to_dict(self.base)
        for fact in reading.facts:
            self.assertEqual(resolve_fact(source, fact["source_path"]), fact["value"])
        alternative = reading.comparisons[0]["profile"]
        self.assertEqual(alternative["day_stem"], "己")
        self.assertEqual(alternative["month_group"], "wealth")
        self.assertEqual(reading.profile["day_stem"], "庚")
        self.assertFalse(reading.final_strength_supported)
        self.assertFalse(reading.useful_element_supported)
        self.assertFalse(reading.whole_chart_synthesis_supported)
        self.assertTrue(reading.conclusions)
        self.assertNotEqual(reading.conclusions[0].conditions, reading.comparisons[0]["conclusions"][0]["conditions"])
        self.assertNotIn("태극귀인", " ".join(b.text for b in reading.blocks))
        self.assertIn("겨울 금", reading.memo_body)

    def test_unknown_time_and_unexplained_critical_are_blocked(self):
        unknown = model_copy_compat(self.base, deep=True)
        unknown.manse.meta.hour_pillar_enabled = False
        self.assertEqual(build_natal_structure(base=unknown, locale="ko").blocks, [])
        uncertain = model_copy_compat(self.base, deep=True)
        uncertain.result.uncertainty_summary.append(UncertaintyFlagSummary(code="unexplained", severity="critical", user_message="test", developer_message="test", affected_fields=["month_pillar"], evidence={}))
        reading = build_natal_structure(base=uncertain, locale="ko")
        self.assertEqual(reading.status, "blocked_calculation")
        self.assertFalse(reading.blocks)

    def test_scores_and_presentation_order_cannot_change_the_reading(self):
        original = build_natal_structure(base=self.base, locale="ko")
        changed = model_copy_compat(self.base, deep=True)
        for key in KEYS:
            getattr(changed.manse.pillars, key).hidden_stems.reverse()
        # Unrelated raw distribution and numeric analysis are not inputs.
        changed.result.signals.balance_score = 99
        changed.result.signals.wealth_score = 0
        changed.result.signals.missing_elements = ["water"]
        other = build_natal_structure(base=changed, locale="ko")
        self.assertEqual(original.profile, other.profile)
        self.assertEqual(original.blocks, other.blocks)
        self.assertEqual(original.memo_body, other.memo_body)
