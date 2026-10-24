"""The published view preserves scope, source notes and ordinary-language text."""
import unittest
from types import SimpleNamespace

from app.domain.saju.question_schemas import CategoryReadingSection
from app.domain.saju.reading_information_contracts import ReadingInformationItem
from app.domain.saju.reading_publication import plain_wording, publish_chapter


class PublicationTests(unittest.TestCase):
    def test_one_line_precedes_full_reading_in_both_writing_paths_and_keeps_hold(self):
        from app.domain.saju.natal_structure import derive_profile, render_structure, select_conclusions
        from app.domain.saju.natal_structure_contracts import NatalStructureReading
        from app.domain.saju.services.build_manse import HIDDEN_STEMS_BY_BRANCH
        from app.domain.saju.publication_writing import WRITING_VERSION
        chart = {"year": "戊辰", "month": "癸亥", "day": "庚辰", "time": "丙子"}
        refs = {k: "natal.pillar." + k for k in chart}
        profile = derive_profile(chart, {k: HIDDEN_STEMS_BY_BRANCH[v[1]] for k, v in chart.items()}, refs)
        for locale in ("ko", "en"):
            blocks = render_structure(profile, refs, locale)
            conclusions = select_conclusions(profile, blocks, locale)
            natal = NatalStructureReading(status="available", blocks=blocks, conclusions=conclusions, memo_body="source evidence")
            for provider in ("fallback", "openai", "codex"):
                report = SimpleNamespace(provider=provider, publication_writing_version=WRITING_VERSION)
                section = self.section(id="core", body="Full supported model prose.")
                published = publish_chapter(section=section, report=report, locale=locale, natal=natal)
                self.assertEqual(published.blocks[0].id, "natal.one_line")
                self.assertIn(conclusions[0].one_line, published.blocks[0].text)
                self.assertGreater(len(published.blocks), 1)
                self.assertIn("source evidence", published.memo_body)
                self.assertIn(section.body if provider != "fallback" else conclusions[0].text,
                              "\n".join(b.text for b in published.blocks[1:]))
            natal.status = "conditional"
            conditional = publish_chapter(section=section, report=None, locale=locale, natal=natal)
            self.assertIn("선택한 명식" if locale == "ko" else "selected chart", conditional.blocks[0].text)
            self.assertEqual(conditional.scope, "conditional_natal_structure")
            natal.status = "blocked_calculation"
            blocked = publish_chapter(section=self.section(id="core", status="blocked_calculation"),
                                      report=None, locale=locale, natal=natal)
            self.assertFalse(any(b.id == "natal.one_line" for b in blocked.blocks))

    def section(self, **overrides):
        fields = dict(id="career", title="직장·직업운", body="책임과 보상을 나눠 읽어.\n\n일만 늘고 대우가 그대로라면 불리해.",
                      memo_body="월간 십성: 정관", status="existing_interpretation")
        fields.update(overrides)
        return CategoryReadingSection(**fields)

    def test_plain_wording_does_not_corrupt_similar_ordinary_words(self):
        self.assertEqual(plain_wording("상관없이 정리해.", "ko"), "상관없이 정리해.")
        self.assertNotIn("재성", plain_wording("재성은 안쪽에 있어.", "ko"))
        self.assertEqual(plain_wording("A plain reading", "en"), "A plain reading")

    def test_main_keeps_conditional_downside_and_original_memo(self):
        section = self.section()
        result = publish_chapter(section=section, report=SimpleNamespace(provider="fallback"), locale="ko")
        self.assertIn("불리해", " ".join(b.text for b in result.blocks))
        self.assertIn("정관", result.memo_body)
        self.assertEqual(result.scope, "supported_reading_excerpt")

    def test_hanja_and_calculation_positions_are_only_in_memo(self):
        item = ReadingInformationItem(id="structure.officer", category="career", title="관성 위치",
            body="정관: 태어난 달", memo_body="천간 丁", kind="calculation_description", fact_ids=["source.month"])
        section = self.section(body="풀이 본문.\n\n丁火가 월간에 있어.", information=[item])
        result = publish_chapter(section=section, report=SimpleNamespace(provider="codex"), locale="ko")
        self.assertEqual([b.text for b in result.blocks], ["풀이 본문."])
        self.assertIn("丁火", result.memo_body)
        self.assertIn("정관: 태어난 달", result.memo_body)

    def test_blocked_calculation_never_releases_a_legacy_judgment(self):
        section = self.section(body="이 사람이 성공한다.", status="blocked_calculation")
        result = publish_chapter(section=section, report=None, locale="ko")
        self.assertNotIn("성공", " ".join(b.text for b in result.blocks))
        self.assertTrue(result.notice)
        self.assertEqual(result.scope, "provisional_information")

    def test_missing_natal_structure_cannot_restore_star_only_core(self):
        from app.domain.saju.natal_structure_contracts import NatalStructureReading
        from app.domain.saju.distinctive_contracts import DistinctiveReading, DistinctiveTheme
        distinctive = DistinctiveReading(status="conditional", themes=[DistinctiveTheme(
            id="forced_star", category="core", title="태극귀인", body="태극귀인만 본문에 넣는 이전 문구",
            memo_body="applied source", fact_ids=["star.source"], rule_id="old_theme")])
        result = publish_chapter(section=self.section(id="core", status="blocked_calculation"), report=None,
            locale="ko", distinctive=distinctive, natal=NatalStructureReading())
        self.assertEqual(result.scope, "provisional_information")
        self.assertTrue(result.notice)
        self.assertNotIn("태극귀인", " ".join(b.text for b in result.blocks))

    def test_eligible_followup_has_context_without_replacing_natal_reading(self):
        from app.domain.saju.natal_structure_contracts import NatalStructureReading, NatalStructureBlock
        from app.domain.saju.distinctive_contracts import DistinctiveReading, DistinctiveTheme
        natal = NatalStructureReading(status="available", memo_body="원본 구조 근거", blocks=[
            NatalStructureBlock(id="month_context", title="핵심", text="실제 구조 풀이", rule_ids=["month_context"], fact_ids=["natal.pillar.day"])])
        theme = DistinctiveTheme(id="study_with_solitude", category="core", title="보조 특징",
            body="보조 특징의 전체 문단", memo_body="문창/화개 실제 근거", fact_ids=["actual.star"],
            rule_id="study_with_solitude", question_ids=["features.study_solitude"])
        distinctive = DistinctiveReading(status="available", themes=[theme])
        result = publish_chapter(section=self.section(id="core"), report=None, locale="ko", natal=natal, distinctive=distinctive)
        self.assertEqual(result.blocks[0].text, "실제 구조 풀이")
        self.assertEqual(result.blocks[-1].title, "")
        self.assertIn("배움·기록", result.blocks[-1].text)
        self.assertNotIn("보조 특징의 전체 문단", " ".join(b.text for b in result.blocks))
        self.assertIn("문창/화개", result.memo_body)
        theme.question_ids = []
        result = publish_chapter(section=self.section(id="core"), report=None, locale="ko", natal=natal, distinctive=distinctive)
        self.assertEqual(len(result.blocks), 1)

    def test_generated_dense_terms_are_folded_even_without_hanja(self):
        for text in ("월령을 얻어 통근한 구조야.", "The month stem and hidden stems form the basis."):
            section = self.section(body="첫 결론.\n\n" + text)
            result = publish_chapter(section=section, report=SimpleNamespace(provider="codex"), locale="ko")
            self.assertNotIn(text, " ".join(b.text for b in result.blocks))
            self.assertIn(text, result.memo_body)

    def test_glossary_is_preserved_without_displaying_technical_names(self):
        item = ReadingInformationItem(id="star.hwagae", category="core", title="화개",
            body="네 사주에서 확인돼.", memo_body="화개 기준", kind="traditional_term_definition", fact_ids=["source.star"])
        section = self.section(id="core", information=[item])
        result = publish_chapter(section=section, report=SimpleNamespace(provider="fallback"), locale="ko")
        self.assertEqual(result.blocks[0].kind, "traditional_definition")
        self.assertIn("고독", result.blocks[0].text)
        self.assertNotIn("화개", result.blocks[0].text)
        self.assertIn("화개", result.memo_body)
        self.assertEqual(result.scope, "traditional_information")

    def test_unmatched_or_unknown_glossary_does_not_create_a_symbol(self):
        section = self.section(id="core", information=[])
        result = publish_chapter(section=section, report=SimpleNamespace(provider="fallback"), locale="ko")
        self.assertEqual([b.kind for b in result.blocks], ["availability_notice"])
        self.assertNotIn("도화", " ".join(b.text for b in result.blocks))
        self.assertEqual(result.scope, "unavailable")

    def test_legacy_personality_core_is_not_published_for_any_provider(self):
        for provider in ("fallback", "codex", "openai"):
            section = self.section(id="core", body="너는 결단력이 강한 사람이야.")
            result = publish_chapter(section=section, report=SimpleNamespace(provider=provider), locale="ko")
            self.assertNotIn("결단력", " ".join(b.text for b in result.blocks) + result.memo_body)

    def test_information_memo_is_published_once(self):
        item = ReadingInformationItem(id="structure.officer", category="career", title="관성 위치",
            body="정관: 태어난 달", memo_body="출처: 월간", kind="calculation_description", fact_ids=["source.month"])
        section = self.section(memo_body="원래 근거\n\n### 관성 위치\n출처: 월간", information=[item])
        result = publish_chapter(section=section, report=SimpleNamespace(provider="codex"), locale="ko")
        self.assertEqual(result.memo_body.count("출처: 월간"), 1)

    def test_money_information_cannot_look_like_a_supported_money_verdict(self):
        section = self.section(id="wealth", status="needs_rule_review", body="돈의 표시는 겉에 한 곳 있어.")
        result = publish_chapter(section=section, report=None, locale="ko")
        self.assertEqual(result.scope, "calculation_information")
        self.assertIn("판정한 결과는 아니야", result.notice)
        self.assertFalse(any(b.kind == "interpretation" for b in result.blocks))

    def test_alternate_chart_facts_stay_in_memo_without_legacy_traits(self):
        section = self.section(id="core", status="blocked_calculation", body="성격 풀이")
        result = publish_chapter(section=section, report=None, locale="ko", calculation_memo="0시 날짜 변경 기준\n戊辰 癸亥 己卯 丙子")
        self.assertIn("己卯", result.memo_body)
        self.assertNotIn("己卯", " ".join(b.text for b in result.blocks))
        self.assertNotIn("성격 풀이", result.memo_body)

    def test_english_count_summary_uses_plain_words(self):
        section = self.section(id="wealth", status="needs_rule_review", body="Money-related symbols occur once visibly and once in hidden stems.")
        result = publish_chapter(section=section, report=None, locale="en")
        self.assertEqual(result.scope, "calculation_information")
        self.assertIn("inner characters", result.blocks[0].text)
        self.assertTrue(result.notice)

    def test_compatibility_heading_does_not_swallow_its_paragraph(self):
        section = self.section(body="첫 결론.\n\n### 쉽게 풀어보면\n그대로 남아야 할 본문.\n\n### 다음 구간\n다음 설명.")
        result = publish_chapter(section=section, report=SimpleNamespace(provider="codex"), locale="ko")
        self.assertTrue(any(b.text == "그대로 남아야 할 본문." for b in result.blocks))
        self.assertTrue(any(b.text == "다음 구간" and b.kind == "heading" for b in result.blocks))
        self.assertTrue(any(b.text == "다음 설명." and b.kind == "interpretation" for b in result.blocks))
