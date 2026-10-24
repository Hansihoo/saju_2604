"""Initial reading boundaries: one report, five categories and factual questions."""
import json
import unittest
from unittest.mock import patch

import httpx

from app.config import settings
from app.main import app
from app.domain.saju.category_reading import split_reading_body
from app.domain.saju.services.generate_interpretation import generate_interpretation_report


NORMAL = {"birth_date": "1997-09-18", "birth_time": "14:30", "region_id": "kr-seoul", "gender": "female"}
BOUNDARY = {"birth_date": "1988-11-20", "birth_time": "23:30", "region_id": "kr-chungbuk-jecheon", "gender": "male"}


class CategoryProseTests(unittest.TestCase):
    def test_memo_is_separate_and_later_prose_is_not_lost(self):
        main, memo = split_reading_body("### 핵심 결론\n결론\n\n### 풀이 포인트\n- 사실\n\n### 전문가 노트\n기준\n\n### 다음 흐름\n다음 본문")
        self.assertIn("결론", main)
        self.assertIn("다음 본문", main)
        self.assertNotIn("핵심 결론", main)
        self.assertNotIn("사실", main)
        self.assertIn("사실", memo)
        self.assertIn("기준", memo)


class CategoryReadingHttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 12345)), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_one_existing_report_and_category_questions(self):
        with patch("app.domain.saju.services.build_preview_response.generate_interpretation_report", wraps=generate_interpretation_report) as full, patch("app.domain.saju.services.build_preview_response._generate_free_preview_safely") as preview:
            response = await self.client.post("/saju/reading", json=NORMAL, headers={"X-Saju-Verification-Provider": "fallback"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(full.call_count, 1)
        preview.assert_not_called()
        self.assertIn("no-store", response.headers["cache-control"])
        data = response.json()
        sections = data["category_reading"]["sections"]
        self.assertEqual([s["id"] for s in sections], ["core", "love", "wealth", "career", "luck_flow"])
        self.assertTrue(all(s["body"] for s in sections))
        self.assertTrue(all(s["memo_body"] for s in sections if s["status"] == "existing_interpretation"))
        self.assertEqual(sections[2]["status"], "needs_rule_review")
        self.assertNotIn("확장보다", sections[2]["body"])
        wealth = (await self.client.post("/saju/question", json={"input": NORMAL, "question_id": "wealth.locations"})).json()
        self.assertIn(wealth["answer"], sections[2]["memo_body"])
        self.assertNotIn(wealth["answer"], sections[2]["body"])
        self.assertTrue(any("태어난 해" in item["body"] for item in sections[2]["information"]))
        self.assertIn("정재", sections[2]["memo_body"])
        self.assertTrue(any(item["id"] == "cycle.next" for item in sections[4]["information"]))
        self.assertTrue(data["category_reading"]["notices"])
        self.assertFalse(data["category_reading"]["source_context"]["interpretation_rules_changed"])
        self.assertFalse(data["category_reading"]["source_context"]["event_timing_supported"])
        self.assertTrue(all(q["id"].startswith("features.") for q in data["question_flow"]["questions"]))
        for section in sections:
            self.assertNotIn("### 전문가 노트", section["body"])
            self.assertNotIn("### 풀이 포인트", section["body"])
            published = section["publication"]
            self.assertTrue(published["blocks"])
            self.assertTrue(published["memo_body"])
            for block in published["blocks"]:
                self.assertNotRegex(block["text"], r"[一-龥]")
        self.assertEqual(sections[0]["publication"]["scope"], "natal_structure")
        opening = sections[0]["publication"]["blocks"][0]
        self.assertEqual(opening["id"], "natal.one_line")
        self.assertTrue(sections[0]["body"].startswith(opening["text"]))
        self.assertIn(data["category_reading"]["natal_structure"]["conclusions"][0]["one_line"], opening["text"])
        self.assertEqual(data["category_reading"]["natal_structure"]["status"], "available")
        self.assertFalse(any(b["kind"] == "traditional_definition" for s in sections for b in s["publication"]["blocks"]))
        self.assertEqual(sections[2]["publication"]["scope"], "calculation_information")
        self.assertEqual(sections[-1]["title"], "지금부터 달라질 운")

    async def test_demo_explains_money_and_cycle_difference_without_promising_events(self):
        payload = {"birth_date": "1993-04-22", "birth_time": "03:40", "region_id": "kr-chungbuk-jecheon", "gender": "male"}
        for locale in ("ko", "en"):
            raw = await self.client.post("/saju/reading", json={**payload, "locale": locale}, headers={"X-Saju-Verification-Provider": "fallback"})
            self.assertEqual(raw.status_code, 200, raw.text)
            data = raw.json()
            sections = {s["id"]: s for s in data["category_reading"]["sections"]}
            wealth = sections["wealth"]
            self.assertEqual(wealth["status"], "needs_rule_review")
            self.assertIn("재산과 일의 대가" if locale == "ko" else "assets and compensation", wealth["body"])
            self.assertNotIn("거래와 자원 운용이야" if locale == "ko" else "concerns trade and resource management", wealth["body"])
            self.assertNotRegex(wealth["body"], r"정재|편재|[一-龥]")
            comparison = next(b for b in sections["luck_flow"]["publication"]["blocks"] if b["id"] == "cycle.comparison")
            self.assertIn("서로의 몫" if locale == "ko" else "roles and resources", comparison["text"])
            self.assertFalse(data["category_reading"]["source_context"]["whole_chart_synthesis_supported"])
            self.assertFalse(data["category_reading"]["source_context"]["event_timing_supported"])
            information = data["category_reading"]["reading_information"]
            source_ids = {f["id"] for f in information["facts"]}
            item = next(i for i in information["items"] if i["id"] == "cycle.comparison")
            self.assertEqual(set(item["fact_ids"]), {"information.day_master", "information.cycle.current", "information.cycle.next"})
            self.assertTrue(set(item["fact_ids"]) <= source_ids)
            self.assertTrue(any(d["rule"] == "cycle_theme_comparison_v1" and d["current_god"] == "비견" and d["next_god"] == "겁재" for d in information["derivations"]))

    async def test_critical_and_unknown_do_not_generate_interpretations(self):
        for payload in (BOUNDARY, {**BOUNDARY, "locale": "en"}, {**NORMAL, "is_birth_time_estimated": True}, {**NORMAL, "is_birth_time_estimated": True, "locale": "en"}):
            with patch("app.domain.saju.services.build_preview_response.generate_interpretation_report") as full:
                response = await self.client.post("/saju/reading", json=payload)
            self.assertEqual(response.status_code, 200, response.text)
            full.assert_not_called()
            data = response.json()
            self.assertTrue(data["category_reading"]["source_context"]["critical_hold"])
            self.assertEqual([s["id"] for s in data["category_reading"]["sections"] if s["visible"]],
                             ["core", "love", "wealth", "career", "luck_flow"])
            self.assertTrue(all(s["publication"]["blocks"] for s in data["category_reading"]["sections"]))
            self.assertTrue(all(s["status"] == "blocked_calculation" for s in data["category_reading"]["sections"]))
            for section in data["category_reading"]["sections"]:
                expected = ("conditional_natal_structure" if section["id"] == "core" else "conditional_traditional_themes") if not payload.get("is_birth_time_estimated") and section["id"] in {"core", "love"} else "provisional_information"
                self.assertEqual(section["publication"]["scope"], expected)
                self.assertTrue(section["publication"]["notice"])
                self.assertFalse(any(b["kind"] == "interpretation" for b in section["publication"]["blocks"]))
            self.assertTrue(data["question_flow"]["notices"])
            if payload.get("is_birth_time_estimated"):
                self.assertIn("해석은 보류" if payload.get("locale", "ko") == "ko" else "interpretations are withheld", data["category_reading"]["calculation_notices"][0])
            else:
                self.assertIn("가정한 풀이" if payload.get("locale", "ko") == "ko" else "assumes the selected calculation convention", data["category_reading"]["calculation_notices"][0])
                self.assertTrue(any(("종합 풀이는 보류" if payload.get("locale", "ko") == "ko" else "full reading on hold") in notice for notice in data["category_reading"]["calculation_notices"]))
            self.assertNotIn("읽었어", " ".join(data["category_reading"]["calculation_notices"]))
            if payload.get("is_birth_time_estimated"):
                self.assertNotIn("luck.current_next", {q["id"] for q in data["question_flow"]["questions"]})

    async def test_stream_has_actual_stages_and_complete_categories(self):
        response = await self.client.post("/saju/reading-stream", json=BOUNDARY)
        self.assertEqual(response.status_code, 200)
        frames = [json.loads(line) for line in response.text.splitlines()]
        self.assertEqual([frame["stage"] for frame in frames if frame["type"] == "stage"], ["accepted", "calculating", "writing"])
        self.assertEqual(frames[-1]["type"], "result")
        self.assertEqual(len(frames[-1]["data"]["category_reading"]["sections"]), 5)
        self.assertTrue(all(section["visible"] for section in frames[-1]["data"]["category_reading"]["sections"]))

    async def test_verifier_guard_prevents_calls_to_paid_provider(self):
        with patch.object(settings, "llm_provider", "openai"), patch("app.api.routes.create_saju_preview_response") as calculate:
            for endpoint in ("/saju/reading", "/saju/reading-stream"):
                response = await self.client.post(endpoint, json=NORMAL, headers={"X-Saju-Verification-Provider": "fallback"})
                self.assertEqual(response.status_code, 409)
        calculate.assert_not_called()

    async def test_chart_question_uses_same_pillars_and_rejects_unimplemented_timing(self):
        initial = (await self.client.post("/saju/reading", json=BOUNDARY)).json()
        answer = await self.client.post("/saju/question", json={"input": BOUNDARY, "question_id": "chart.pillars"})
        self.assertEqual(answer.status_code, 200, answer.text)
        for pillar in initial["manse"]["pillars"].values():
            if pillar["enabled"]:
                self.assertIn(pillar["gan_zhi"], answer.json()["answer"])
        for question in ("love.meeting_window", "career.entry_window"):
            denied = await self.client.post("/saju/question", json={"input": BOUNDARY, "question_id": question})
            self.assertEqual(denied.status_code, 422)

    async def test_english_main_stays_localized_and_cycle_dates_are_not_duplicated(self):
        import re
        response = await self.client.post("/saju/reading", json={**NORMAL, "locale": "en"},
                                          headers={"X-Saju-Verification-Provider": "fallback"})
        self.assertEqual(response.status_code, 200)
        sections = response.json()["category_reading"]["sections"]
        for section in sections:
            main = section["body"] + "\n" + "\n".join(item["body"] for item in section["information"])
            self.assertNotRegex(main, r"[가-힣一-龥]")
        self.assertNotIn("Next interval", sections[4]["body"])
        self.assertEqual(len([item for item in sections[4]["information"] if item["id"] == "cycle.next"]), 1)
