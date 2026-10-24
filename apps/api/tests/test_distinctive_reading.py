"""Guard the difference between a detected label and a supported personal theme."""
from copy import deepcopy
from datetime import datetime, timezone
import unittest
from unittest.mock import Mock

from app.domain.saju.distinctive_reading import build_distinctive_reading, distinctive_questions
from app.domain.saju.pydantic_compat import model_to_dict
from app.domain.saju.question_reading import clear_question_caches, create_question_reading, QuestionUnavailable
from app.domain.saju.question_schemas import SajuQuestionRequest
from app.domain.saju.schemas import SajuPreviewRequest, UncertaintyFlagSummary
from app.domain.saju.services.preview_orchestrator import create_saju_preview_response
from app.tools.verify_question_flow import resolve_fact


class DistinctiveReadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.now = datetime(2026, 10, 9, tzinfo=timezone.utc)
        cls.request = SajuPreviewRequest(birth_date="1988-11-20", birth_time="23:30", gender="male", region_id="kr-chungbuk-jecheon")
        cls.base = create_saju_preview_response(payload=cls.request, trace_id="distinctive-test", service_name="tests",
            debug_requested=False, report_mode="none", as_of=cls.now)

    def build(self, base=None, locale="ko"):
        return build_distinctive_reading(base=base or self.base, locale=locale)

    def setUp(self):
        clear_question_caches()

    def test_selected_chart_has_bounded_themes_and_real_deeper_answers(self):
        reading = self.build()
        self.assertEqual(reading.status, "conditional")
        self.assertEqual({t.id for t in reading.themes}, {"study_with_solitude", "attention_with_friction"})
        self.assertIn("가정", reading.assumption)
        answers = []
        calculate = Mock(return_value=deepcopy(self.base))
        for q in distinctive_questions(reading, "ko"):
            answer = create_question_reading(payload=SajuQuestionRequest(input=self.request, question_id=q["id"]),
                trace_id=q["id"], service_name="tests", calculate=calculate, as_of=self.now)
            self.assertTrue(answer.memo.reading)
            self.assertTrue(answer.sections)
            self.assertEqual(answer.source_context["feature_status"], "conditional")
            self.assertEqual(answer.provider, "deterministic")
            self.assertIn(reading.assumption, answer.notices)
            self.assertLessEqual(len(answer.memo.reading), 360)
            self.assertIn("matched_evidence", {s.id for s in answer.sections})
            answers.append(answer.answer)
        self.assertEqual(len(set(answers)), 3)
        self.assertEqual(calculate.call_count, 1)

    def test_feature_is_introduced_with_meaning_before_its_follow_up(self):
        reading = self.build()
        core = next(t for t in reading.themes if t.category == "core")
        self.assertIn("네 사주에 있는 **태극귀인**의 전통적인 뜻이야", core.body)
        self.assertNotIn("### 네 사주에는 태극귀인이 있어", core.body)
        self.assertIn("일의 시작과 끝을 지켜주는 복", core.body)
        self.assertIn("배움·글에 붙는 복과 별개로", core.body)
        self.assertIn("distinctive.star.taegeuk-gwiin", core.eligible_matches)
        question = next(q for q in distinctive_questions(reading, "ko") if q["id"] == "features.taegeuk")
        self.assertEqual(question["title"], "내 사주의 태극귀인은 어떤 복을 뜻할까?")
        for locale in ("ko", "en"):
            base = deepcopy(self.base)
            next(s for s in base.manse.special_stars if s.key == "taegeuk-gwiin").method_id = "unreviewed"
            absent = self.build(base, locale)
            self.assertNotIn("features.taegeuk", {q["id"] for q in distinctive_questions(absent, locale)})
            self.assertNotIn("태극귀인" if locale == "ko" else "Taiji Noble", " ".join(t.body for t in absent.themes))

    def test_every_fact_resolves_and_comparison_recomputes_its_own_stars(self):
        reading = self.build()
        source = model_to_dict(self.base, exclude_none=True)
        for f in reading.facts:
            expected = resolve_fact(source, f["source_path"])
            self.assertEqual(f["value"], expected)
        other = reading.comparisons[0]
        self.assertEqual(other["chart"]["day"], "己卯")
        self.assertEqual(other["themes"], [])
        self.assertEqual(set(other["removed_theme_ids"]), {t.id for t in reading.themes})
        for f in other["facts"]:
            self.assertEqual(f["value"], resolve_fact(other["derived_source"], f["source_path"]))
        for pillar in other["derived_source"]["manse"]["pillars"].values():
            self.assertNotIn("stem_ten_god", pillar)
            self.assertNotIn("stem_element", pillar)

    def test_one_star_or_missing_day_pair_cannot_publish_a_combination(self):
        for removed, rejected in (("munchang-gwiin", "study_with_solitude"), ("wangji-dohwa", "attention_with_friction")):
            base = deepcopy(self.base)
            for s in base.manse.special_stars:
                if s.key == removed:
                    s.active = False
            self.assertNotIn(rejected, {t.id for t in self.build(base).themes})
        base = deepcopy(self.base)
        wonjin = next(s for s in base.manse.special_stars if s.key == "wonjin")
        wonjin.matches = [m for m in wonjin.matches if m.pillar_key != "day" and m.counterpart_pillar_key != "day"]
        self.assertNotIn("attention_with_friction", {t.id for t in self.build(base).themes})

    def test_absent_taegeuk_removes_only_its_question_and_direct_request_is_rejected(self):
        base = deepcopy(self.base)
        for s in base.manse.special_stars:
            if s.key == "taegeuk-gwiin":
                s.active = False
        reading = self.build(base)
        self.assertIn("study_with_solitude", {t.id for t in reading.themes})
        self.assertNotIn("태극귀인", " ".join(t.body for t in reading.themes))
        self.assertNotIn("features.taegeuk", {q["id"] for q in distinctive_questions(reading, "ko")})
        with self.assertRaises(QuestionUnavailable):
            create_question_reading(payload=SajuQuestionRequest(input=self.request, question_id="features.taegeuk"),
                trace_id="absent", service_name="tests", calculate=Mock(return_value=base), as_of=self.now)

    def test_unknown_or_unexplained_critical_flags_block_new_reading_too(self):
        base = deepcopy(self.base)
        base.manse.meta.hour_pillar_enabled = False
        self.assertEqual(self.build(base).themes, [])
        base = deepcopy(self.base)
        base.result.uncertainty_summary.append(UncertaintyFlagSummary(code="unexplained", severity="critical", affected_fields=["month_pillar"],
            user_message="", developer_message="", evidence={}))
        reading = self.build(base)
        self.assertEqual(reading.status, "blocked_calculation")
        self.assertEqual(distinctive_questions(reading, "ko"), [])

    def test_malformed_match_method_and_missing_hidden_facts_fail_closed(self):
        base = deepcopy(self.base)
        star = next(s for s in base.manse.special_stars if s.key == "munchang-gwiin")
        star.matches[0].gan_zhi = "甲子"
        self.assertNotIn("study_with_solitude", {t.id for t in self.build(base).themes})
        base = deepcopy(self.base)
        next(s for s in base.manse.special_stars if s.key == "wangji-dohwa").method_id = "unreviewed"
        self.assertNotIn("attention_with_friction", {t.id for t in self.build(base).themes})
        base = deepcopy(self.base)
        base.manse.pillars.month.hidden_stems = []
        self.assertEqual(self.build(base).status, "blocked_calculation")

    def test_void_or_clash_is_not_promoted_to_a_favorable_study_theme(self):
        base = deepcopy(self.base)
        base.manse.pillars.day.xun_kong = "辰亥"
        self.assertNotIn("study_with_solitude", {t.id for t in self.build(base).themes})

    def test_no_strength_from_scores_repetition_or_provider(self):
        expected = [model_to_dict(t) for t in self.build().themes]
        base = deepcopy(self.base)
        base.manse.analysis.charm_score = 99
        base.manse.analysis.balance_score = 1
        for s in base.manse.special_stars:
            s.matches += deepcopy(s.matches)
        self.assertEqual([model_to_dict(t) for t in self.build(base).themes], expected)

    def test_ordinary_language_has_no_hidden_rank_or_universal_personality_hook(self):
        for locale in ("ko", "en"):
            reading = self.build(locale=locale)
            for t in reading.themes:
                self.assertNotRegex(t.body + t.title, r"\d+\s*%|상위\s*\d|백분위|percentile")
                self.assertNotRegex(t.body, r"[一-龥]")
                if locale == "en":
                    self.assertNotRegex(t.body + t.title, r"[가-힣]")

    def test_same_facts_use_same_rules_without_birth_identity(self):
        base = deepcopy(self.base)
        base.trace_id = "another-user"
        self.assertEqual([t.id for t in self.build(base).themes], [t.id for t in self.build().themes])

    def test_different_actual_chart_does_not_inherit_personal_questions(self):
        request = SajuPreviewRequest(birth_date="1997-09-18", birth_time="14:30", gender="female", region_id="kr-seoul")
        base = create_saju_preview_response(payload=request, trace_id="other-chart", service_name="tests",
            debug_requested=False, report_mode="none", as_of=self.now)
        self.assertNotEqual({t.id for t in self.build(base).themes}, {t.id for t in self.build().themes})
        self.assertEqual(distinctive_questions(self.build(base), "ko"), [])

    def test_hwagae_unknown_method_cannot_satisfy_study_rule(self):
        base = deepcopy(self.base)
        for star in base.manse.special_stars:
            if star.key.startswith("hwagae-"):
                star.method_id = "unreviewed"
        self.assertNotIn("study_with_solitude", {t.id for t in self.build(base).themes})
