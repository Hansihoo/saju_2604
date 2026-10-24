"""Generation contract and publication regression checks; no provider calls."""
import json
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import httpx

from app.main import app
from app.domain.saju.natal_structure import catalog
from app.domain.saju.natal_structure_contracts import NatalStructureReading
from app.domain.saju.publication_writing import WRITING_VERSION, visible_main_chars
from app.domain.saju.question_schemas import CategoryReadingSection
from app.domain.saju.reading_publication import publish_chapter
from app.domain.saju.services.build_reading_plan import build_reading_plan
from app.domain.saju.services.generate_interpretation import (
    SECTION_TITLES, _call_openai_structured_interpretation, _validate_evidence_ids, _validate_report,
    _writer_contract, _writer_schema, generate_interpretation_report,
)
from tests.test_generate_interpretation import make_payload, make_report


class WriterContractTests(unittest.TestCase):
    def test_actual_nested_fact_ids_are_accepted_but_invented_aliases_are_not(self):
        payload = make_payload()
        payload.reading_plan = build_reading_plan(payload)
        actual = payload.reading_plan.sections["work_money"].facts[0].id
        report = make_report()
        report.career.evidence_ids = [actual]
        self.assertEqual(_validate_evidence_ids(report, payload), [])
        report.career.evidence_ids = [actual + ".invented"]
        self.assertIn("career.evidence_ids:unknown:" + actual + ".invented",
                      _validate_evidence_ids(report, payload))

    def test_provider_schema_and_prompt_share_exact_titles_and_ids_in_both_locales(self):
        for locale in ("ko", "en"):
            payload = make_payload(locale=locale)
            schema = _writer_schema(payload)
            prompt = _writer_contract(payload)
            for key, title in SECTION_TITLES[locale].items():
                self.assertEqual(schema["properties"][key]["properties"]["title"]["enum"], [title])
                self.assertIn(title, prompt)
            self.assertIn("at least five complete sentences", prompt)
            self.assertEqual(schema["properties"]["summary"]["properties"]["evidence_ids"]["items"]["enum"],
                             ["elements", "luck_cycles", "star:dohwa-day-branch", "ten_gods"])

    def test_actual_openai_request_uses_the_same_contract_without_a_network_call(self):
        payload = make_payload()
        report = make_report()
        wire = report.dict(include={"summary", "core_analysis", "love", "career", "wealth", "luck_flow"})
        client = MagicMock()
        client.responses.create.return_value = SimpleNamespace(id="mock-only", output_text=json.dumps(wire))
        with patch("app.domain.saju.services.generate_interpretation.OpenAI", return_value=client), \
                patch("app.domain.saju.services.generate_interpretation.settings.llm_max_attempts", 1):
            result, _ = _call_openai_structured_interpretation(payload)
        self.assertIsNotNone(result)
        self.assertEqual(client.responses.create.call_count, 1)
        request = client.responses.create.call_args.kwargs
        self.assertIn('"exact_section_titles"', request["input"][0]["content"])
        self.assertEqual(request["text"]["format"]["schema"]["properties"]["career"]["properties"]["title"]["enum"], ["직장운"])

    def test_length_metric_excludes_headings_whitespace_and_folded_notes(self):
        self.assertEqual(visible_main_chars("### 핵심 결론\n**직접 답**\n\n### 풀이 포인트\n근거" * 1), 3)

    def test_new_publication_depth_rejects_short_main_despite_long_memo(self):
        payload = make_payload()
        payload.publication_writing = {"version": WRITING_VERSION, "facts": [],
            "chapters": {key: {"fact_ids": ["elements", "ten_gods", "luck_cycles"]}
                         for key in SECTION_TITLES["ko"]}}
        report = make_report()
        report.core_analysis.body += "\n" + "추가 근거 자료 " * 1200
        issues = _validate_report(report, payload)
        self.assertTrue(any(issue.startswith("publication.main:too_short:") for issue in issues))

    def test_known_fact_from_another_chapter_does_not_authorize_this_chapter(self):
        payload = make_payload()
        payload.publication_writing = {"version": WRITING_VERSION, "facts": [],
            "chapters": {key: {"fact_ids": ["elements"]} for key in SECTION_TITLES["ko"]}}
        report = make_report()
        report.career.evidence_ids = ["ten_gods"]
        self.assertIn("career.evidence_ids:unknown:ten_gods", _validate_evidence_ids(report, payload))

    def test_natal_version_metadata_matches_the_supplied_catalog(self):
        versions = NatalStructureReading().versions.dict(by_alias=True)
        self.assertEqual(versions["copy"], catalog()["copy_version"])
        self.assertEqual(versions["selection"], catalog()["selection_version"])

    def test_only_validated_contract_replaces_the_structural_and_money_projection(self):
        natal = NatalStructureReading(status="available", memo_body="기존 구조 근거")
        for category in ("core", "wealth", "love"):
            section = CategoryReadingSection(id=category, title="제목", body="검증을 거친 생성 본문이 화면까지 이어져.",
                                             memo_body="모델의 접힌 근거", status="existing_interpretation")
            report = SimpleNamespace(provider="codex", publication_writing_version=WRITING_VERSION)
            published = publish_chapter(section=section, report=report, locale="ko", natal=natal)
            self.assertEqual([b.text for b in published.blocks], [section.body])
            self.assertIn("모델의 접힌 근거", published.memo_body)
            report.publication_writing_version = None
            legacy = publish_chapter(section=section, report=report, locale="ko", natal=natal)
            if category == "core":
                self.assertEqual(legacy.blocks, [])
            report.publication_writing_version = WRITING_VERSION
            natal.status = "conditional"
            held = publish_chapter(section=section, report=report, locale="ko", natal=natal)
            if category == "core":
                self.assertEqual(held.blocks, [])
            natal.status = "available"


class InitialWriterIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_initial_request_supplies_actual_judgments_once_without_generation(self):
        with patch("app.domain.saju.services.build_preview_response.generate_interpretation_report", wraps=generate_interpretation_report) as writer:
            response = await self.client.post("/saju/reading", json={"birth_date": "1993-04-22", "birth_time": "03:40",
                "gender": "male", "region_id": "kr-chungbuk-jecheon"}, headers={"X-Saju-Verification-Provider": "fallback"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(writer.call_count, 1)
        payload = writer.call_args.kwargs["payload"]
        ctx = payload.publication_writing
        self.assertEqual(ctx["version"], WRITING_VERSION)
        self.assertFalse(ctx["whole_chart_synthesis_supported"])
        self.assertTrue(all(chapter["basis"] and chapter["fact_ids"] for chapter in ctx["chapters"].values()))
        self.assertEqual(ctx["chapters"]["wealth"]["scope"], "calculated_money_symbols_and_meaning_no_wealth_verdict")
        self.assertIsNone(response.json()["result"]["interpretation"].get("publication_writing_version"))

    async def test_critical_request_still_never_calls_a_writer(self):
        with patch("app.domain.saju.services.build_preview_response.generate_interpretation_report") as writer:
            response = await self.client.post("/saju/reading", json={"birth_date": "1988-11-20", "birth_time": "23:30",
                "gender": "male", "region_id": "kr-chungbuk-jecheon"}, headers={"X-Saju-Verification-Provider": "fallback"})
        self.assertEqual(response.status_code, 200, response.text)
        writer.assert_not_called()
        self.assertTrue(response.json()["category_reading"]["source_context"]["critical_hold"])
