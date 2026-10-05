"""Verification-system regression tests; no servers, providers, or files used."""

import copy
import io
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from app.tools.verify_user_story import (
    DEFAULT_OUTPUT, HttpResult, LocalHttp, UserStoryVerifier, VerificationBlocked,
    basis_structure, check_periods, digest, local_base, main, natal_facts, unavailable_luck_assertions,
)


class FakeHttp:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.accepts = []

    def request(self, base, path="", payload=None, *, accept="application/json"):
        self.calls.append((path, payload is not None))
        self.accepts.append(accept)
        return self.responses.pop(0)


def fallback_config():
    return HttpResult(200, {"configured_provider": "fallback", "fallback_only": True}, "application/json")


def response_fixture(unknown=False, locale="ko"):
    now = datetime.now(timezone(timedelta(hours=9)))
    today = now.date().isoformat()
    flow = {"headline": "기준을 정리하는 흐름", "summary": "작은 기준을 정리하세요.",
            "actions": ["담당자를 확인하세요."], "primary_signal": "비견",
            "evidence": [{"label": "기준", "value": "비견", "detail": "일간 기준 계산", "source": "period_rule_v1"}]}
    cards = [{"key": key, "title": "주제 " + key, "basis_line": "보이는 명식 자료를 참고했습니다.",
              "preview_paragraphs": [key + " 내용 하나", key + " 내용 둘", key + " 내용 셋"],
              "user_takeaway": key + " 조언"} for key in ("core", "work_money", "love", "luck_flow")]
    response = {
        "region": {"tzid": "Asia/Seoul"},
        "pipeline_status": {key: "passed" for key in ("input_validation", "region_resolution", "time_correction",
                                                      "calendar_normalization", "regional_solar_correction", "saju_calculation", "analysis_engine")},
        "time_correction": {"is_placeholder_time": unknown},
        "period_flows": {"timezone_id": "Asia/Seoul", "as_of": now.isoformat(),
                         "today": {**flow, "period_start": today, "period_end": today},
                         "month": {**flow, "period_start": (now - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S"),
                                   "period_end": (now + timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S")}},
        "manse": {"pillars": {"month": {"stem_ten_god": "比肩"}, "day": {"branch_ten_god": "正財", "stem": "甲"},
                              "time": {"enabled": not unknown}}, "luck_cycles": [] if unknown else [{"index": 1}],
                  "elements": {"wood": 2, "fire": 1, "earth": 1, "metal": 1, "water": 1 if unknown else 3}},
        "result": {"hour_pillar_enabled": not unknown,
                   "signals": {"visible_pillar_keys": ["year", "month", "day"] + ([] if unknown else ["time"]),
                               "dominant_elements": ["wood"] if unknown else ["water", "wood"], "missing_elements": []},
                   "limitations": ["출생시간 미상"] if unknown else [],
                   "disabled_sections": ["time_pillar", "luck_cycles", "hour_based_interpretation"] if unknown else [],
                   "evidence_sections": {"luck_cycles": {"status": "disabled" if unknown else "ready"}},
                   "free_preview": {"provider": "fallback", "headline": "작은 기준을 세우는 사람", "hero_overview": ["풀이입니다."],
                                    "cards": cards, "diagnostics": {"configured_provider": "fallback", "final_provider": "fallback", "attempts": []}}},
    }
    ko = locale == "ko"
    years = [(now.year - 2, now.year + 7), (now.year + 8, now.year + 17)]
    if not unknown:
        response["manse"]["luck_cycles"] = [{"index": index, "start_year": start, "end_year": end,
                                             "start_datetime": f"{start}-01-01 10:30:00", "change_datetime": f"{end + 1}-01-01 10:30:00"}
                                            for index, (start, end) in enumerate(years)]
    core_counts = "목 2개" if unknown else "수 3개, 목 2개"
    core_en = "wood 2" if unknown else "water 3, wood 2"
    cycle_facts = [f"현재 10년 구간(대운): 갑자 · {years[0][0]}년 1월 ~ {years[0][1] + 1}년 1월",
                   f"다음 10년 구간(대운): 을축 · {years[1][0]}년 1월 ~ {years[1][1] + 1}년 1월"] if ko else [
                   f"Current luck-cycle window: Gap-Ja · {years[0][0]}-01 to {years[0][1] + 1}-01",
                   f"Next luck-cycle window: Eul-Chuk · {years[1][0]}-01 to {years[1][1] + 1}-01"]
    for card in cards:
        if card["key"] == "core":
            facts = ["보이는 기둥의 강한 오행: " + core_counts] if ko else ["Stronger visible elements: " + core_en]
            if unknown:
                facts.append("출생시간 미상: 시주는 제외했어" if ko else "Unknown birth time: the hour pillar is excluded")
            reading = "보이는 강점에 대한 질문으로 읽었어." if ko else "These visible signals frame a question about strengths."
        elif card["key"] == "work_money":
            facts = ["태어난 달에서 확인한 단서(월간): 비견" if ko else "Work reference (month stem): Peer"]
            reading = "함께 맡는 일의 경계를 살펴봤어." if ko else "This signal frames a question about ownership at work."
        elif card["key"] == "love":
            facts = ["관계를 살펴본 자리(배우자궁): 정재" if ko else "Relationship reference (spouse house): Direct Wealth"]
            reading = "함께 생활을 나누는 질문으로 읽었어." if ko else "This signal frames a question about shared resources."
        elif unknown:
            facts = ["출생시간 미상: 시주·대운 계산 비활성" if ko else "Unknown birth time: hour-pillar and luck-cycle calculation are disabled"]
            reading = "현재와 다음 대운의 전환 시점은 읽지 않았어." if ko else "Timing comparison is withheld."
        else:
            facts, reading = cycle_facts, "현재와 다음 구간을 참고했어." if ko else "The supplied windows provide timing context."
        card["basis_explanation"] = {"facts": facts, "reading": reading}
    for kind in ("today", "month"):
        period = response["period_flows"][kind]
        period["period_label"] = today if kind == "today" else "2026년 10월" if ko else "October 2026"
        target = "갑자" if ko else "Gap-Ja"
        signal, stem = ("비견", "갑") if ko else ("Peer", "Gap")
        period["primary_signal"] = signal
        period["evidence"] = [{"label": ("일진" if kind == "today" else "이번 달 월주") if ko else ("Day pillar" if kind == "today" else "Month pillar"),
                               "value": target, "detail": "실제 기준값", "source": "period_rule_v1"}]
        prefix = f"{period['period_label']}의 일진" if kind == "today" else f"절기 기준 {period['period_label']} 월주"
        prefix_en = f"Day pillar for {period['period_label']}" if kind == "today" else f"Solar-term month pillar for {period['period_label']}"
        facts = [(prefix if ko else prefix_en) + ": " + target,
                 f"내 하루 기준(일간) {stem}에서 확인한 단서: {signal}" if ko else f"Signal relative to natal day stem {stem}: {signal}"]
        reading = "계산한 신호를 참고 방향으로 읽었어." if ko else "This signal provides a reference direction."
        if unknown:
            reading += " 출생시간 미상이라 시주와 대운 연결은 제외했어." if ko else " The unknown birth time excludes hour-pillar and luck-cycle connections."
        period["basis_explanation"] = {"facts": facts, "reading": reading}
    return response


class UserStoryVerificationTests(unittest.TestCase):
    def verifier(self, client):
        return UserStoryVerifier(client, "http://127.0.0.1:8000", "http://127.0.0.1:5173")

    def test_basis_shape_requires_one_to_three_short_facts_and_short_reading(self):
        self.assertTrue(basis_structure({"facts": ["계산한 사실"], "reading": "참고 방향"})[0])
        for explanation in (None, {}, {"facts": [], "reading": "내용"},
                            {"facts": ["x"] * 4, "reading": "내용"}, {"facts": ["x" * 97], "reading": "내용"},
                            {"facts": ["x"], "reading": "y" * 361}, {"facts": [" "], "reading": "내용"}):
            with self.subTest(explanation=explanation):
                self.assertFalse(basis_structure(explanation)[0])

    def test_checked_basis_facts_pass_for_known_and_unknown_ko_en(self):
        for unknown, locale in ((False, "ko"), (True, "ko"), (True, "en")):
            verifier = self.verifier(FakeHttp([]))
            verifier.check_basis("synthetic", {"is_birth_time_estimated": unknown, "locale": locale}, response_fixture(unknown, locale))
            with self.subTest(unknown=unknown, locale=locale):
                self.assertTrue(all(check["status"] == "PASS" for check in verifier.checks), verifier.checks)
                self.assertEqual(sum(check["category"] == "functional" for check in verifier.checks), 6)
                self.assertTrue(any(check["category"] == "content" for check in verifier.checks))

    def test_work_and_love_basis_use_month_stem_and_day_branch_separately(self):
        response = response_fixture()
        cards = {card["key"]: card for card in response["result"]["free_preview"]["cards"]}
        cards["love"]["basis_explanation"]["facts"] = ["관계를 살펴본 자리(배우자궁): 비견"]
        verifier = self.verifier(FakeHttp([]))
        verifier.check_basis("synthetic", {"locale": "ko"}, response)
        by_id = {check["id"]: check for check in verifier.checks}
        self.assertEqual(by_id["synthetic.basis_love_structure"]["status"], "PASS")
        self.assertEqual(by_id["synthetic.basis_love_fact_values"]["status"], "FAIL")
        self.assertEqual(by_id["synthetic.basis_work_money_fact_values"]["status"], "PASS")

    def test_core_basis_wrong_count_is_content_failure_even_when_shape_is_valid(self):
        response = response_fixture()
        core = next(card for card in response["result"]["free_preview"]["cards"] if card["key"] == "core")
        core["basis_explanation"]["facts"][0] = "보이는 기둥의 강한 오행: 수 4개, 목 2개"
        verifier = self.verifier(FakeHttp([]))
        verifier.check_basis("synthetic", {"locale": "ko"}, response)
        check = next(check for check in verifier.checks if check["id"] == "synthetic.basis_core_fact_values")
        self.assertEqual(check["status"], "FAIL")
        self.assertEqual(check["evidence"]["expected_dominant_counts"], [("수", 3), ("목", 2)])

    def test_today_basis_must_match_actual_period_label_and_target_evidence(self):
        response = response_fixture()
        response["period_flows"]["today"]["basis_explanation"]["facts"][0] = "잘못된 날짜의 일진: 을축"
        verifier = self.verifier(FakeHttp([]))
        verifier.check_basis("synthetic", {"locale": "ko"}, response)
        self.assertEqual(next(check for check in verifier.checks if check["id"] == "synthetic.basis_today_fact_values")["status"], "FAIL")
        self.assertEqual(next(check for check in verifier.checks if check["id"] == "synthetic.basis_month_fact_values")["status"], "PASS")

    def test_known_luck_basis_must_match_supplied_cycle_period(self):
        response = response_fixture()
        luck = next(card for card in response["result"]["free_preview"]["cards"] if card["key"] == "luck_flow")
        luck["basis_explanation"]["facts"][0] = "현재 10년 구간(대운): 갑자 · 1900년 1월 ~ 1910년 1월"
        verifier = self.verifier(FakeHttp([]))
        verifier.check_basis("synthetic", {"locale": "ko"}, response)
        self.assertEqual(next(check for check in verifier.checks if check["id"] == "synthetic.basis_luck_period_values")["status"], "FAIL")

    def test_legacy_luck_note_still_requires_the_supplied_next_cycle(self):
        response = response_fixture()
        luck = next(card for card in response["result"]["free_preview"]["cards"] if card["key"] == "luck_flow")
        luck["basis_explanation"]["facts"][1] = "다음 10년 구간(대운): 을축 · 1900년 1월 ~ 1910년 1월"
        verifier = self.verifier(FakeHttp([]))
        verifier.check_basis("synthetic", {"locale": "ko"}, response)
        self.assertEqual(next(check for check in verifier.checks if check["id"] == "synthetic.basis_luck_period_values")["status"], "FAIL")

    def test_unknown_luck_basis_does_not_assert_a_dated_active_window(self):
        response = response_fixture(unknown=True)
        luck = next(card for card in response["result"]["free_preview"]["cards"] if card["key"] == "luck_flow")
        luck["basis_explanation"]["facts"].append("현재 10년 구간(대운): 갑자 · 2020년 1월 ~ 2030년 1월")
        verifier = self.verifier(FakeHttp([]))
        verifier.check_basis("synthetic", {"locale": "ko", "is_birth_time_estimated": True}, response)
        check = next(check for check in verifier.checks if check["id"] == "synthetic.basis_luck_unknown_limit")
        self.assertEqual(check["status"], "FAIL")
        self.assertTrue(check["evidence"]["dated_window_claims"])

    def test_unknown_period_basis_preserves_hour_and_cycle_exclusion(self):
        response = response_fixture(unknown=True, locale="en")
        response["period_flows"]["month"]["basis_explanation"]["reading"] = "The signal suggests a direction."
        verifier = self.verifier(FakeHttp([]))
        verifier.check_basis("synthetic", {"locale": "en", "is_birth_time_estimated": True}, response)
        self.assertEqual(next(check for check in verifier.checks if check["id"] == "synthetic.basis_month_unknown_limit")["status"], "FAIL")

    def test_rejects_remote_and_credentialed_urls(self):
        for value in ("https://example.com", "http://127.0.0.1@evil.test", "http://user:password@localhost", "http://localhost/?key=x"):
            with self.subTest(url=value), self.assertRaises(ValueError):
                local_base(value)
        self.assertEqual(local_base("http://127.0.0.1:8000/"), "http://127.0.0.1:8000")

    def test_web_document_uses_html_accept_while_api_remains_json(self):
        client = FakeHttp([
            HttpResult(200, {"status": "ok"}, "application/json"),
            HttpResult(200, '<html><div id="root"></div></html>', "text/html"),
            HttpResult(200, {"configured_provider": "openai", "fallback_only": False}, "application/json"),
        ])
        verifier = self.verifier(client)
        with self.assertRaises(VerificationBlocked):
            verifier.run()
        self.assertEqual(client.accepts, ["application/json", "text/html", "application/json"])
        self.assertEqual(next(check for check in verifier.checks if check["id"] == "runtime.web_document")["status"], "PASS")

    def test_http_client_sends_requested_document_accept(self):
        client = LocalHttp()
        document = io.BytesIO(b'<html><div id="root"></div></html>')
        document.code = 200
        document.headers = {"Content-Type": "text/html"}
        with patch.object(client.opener, "open", return_value=document) as opener:
            result = client.request("http://127.0.0.1:5173", accept="text/html")
            self.assertEqual(opener.call_args[0][0].get_header("Accept"), "text/html")
        self.assertEqual(result.status, 200)
        self.assertIn('id="root"', result.data)

    def test_valid_lunar_day30_schema_rejection_remains_known_functional_failure(self):
        client = FakeHttp([fallback_config(), HttpResult(422, {"error_code": "INPUT_SCHEMA_ERROR", "stage": "input_validation"}, "application/json")])
        verifier = self.verifier(client)
        verifier.check_lunar_day30({"region_id": "synthetic-region"})
        report = verifier.report()
        check = next(check for check in verifier.checks if check["id"] == "known_issue.valid_lunar_day30")
        self.assertEqual(check["status"], "FAIL")
        self.assertTrue(check["evidence"]["known_issue"])
        self.assertEqual(report["functional_failures"], 1)
        self.assertEqual(report["overall_status"], "FAIL")

    def test_valid_lunar_day30_correction_resolves_same_check(self):
        response = response_fixture()
        response["calendar_normalization"] = {"calendar_type": "lunar", "normalized_solar_datetime": "synthetic-normalized-value"}
        verifier = self.verifier(FakeHttp([fallback_config(), HttpResult(200, response, "application/json")]))
        verifier.check_lunar_day30({"region_id": "synthetic-region"})
        check = next(check for check in verifier.checks if check["id"] == "known_issue.valid_lunar_day30")
        self.assertEqual(check["status"], "PASS")
        self.assertFalse(check["evidence"]["known_issue"])

    def test_provider_preflight_blocks_paid_provider_before_post(self):
        client = FakeHttp([HttpResult(200, {"configured_provider": "openai", "fallback_only": False}, "application/json")])
        verifier = self.verifier(client)
        with self.assertRaises(VerificationBlocked):
            verifier.preview("synthetic", {})
        self.assertEqual(client.calls, [("/verification/provider", False)])
        self.assertEqual(verifier.report("blocked")["overall_status"], "BLOCKED")

    def test_absent_provider_endpoint_does_not_assume_environment_is_safe(self):
        client = FakeHttp([HttpResult(404, {}, "application/json")])
        with self.assertRaises(VerificationBlocked):
            self.verifier(client).preview("synthetic", {})
        self.assertFalse(any(post for _, post in client.calls))

    def test_fallback_result_from_attempted_external_provider_stops_run(self):
        response = response_fixture()
        response["result"]["free_preview"]["diagnostics"]["configured_provider"] = "openai"
        client = FakeHttp([fallback_config(), HttpResult(200, response, "application/json")])
        with self.assertRaises(VerificationBlocked):
            self.verifier(client).preview("synthetic", {})
        self.assertEqual(len(client.calls), 2)

    def test_external_attempts_are_not_accepted_as_tokenless_fallback(self):
        response = response_fixture()
        response["result"]["free_preview"]["diagnostics"]["attempts"] = [{"status": "provider_error"}]
        with self.assertRaises(VerificationBlocked):
            self.verifier(FakeHttp([fallback_config(), HttpResult(200, response, "application/json")])).preview("synthetic", {})

    def test_unknown_time_policy_requires_hidden_hour_and_disabled_cycles(self):
        response = response_fixture(unknown=True)
        verifier = self.verifier(FakeHttp([fallback_config(), HttpResult(200, response, "application/json")]))
        verifier.preview("unknown", {"is_birth_time_estimated": True})
        policy = next(item for item in verifier.checks if item["id"] == "unknown.birth_time_policy")
        self.assertEqual(policy["status"], "PASS")
        response["manse"]["luck_cycles"] = [{"index": 1}]
        broken = self.verifier(FakeHttp([fallback_config(), HttpResult(200, response, "application/json")]))
        broken.preview("unknown", {"is_birth_time_estimated": True})
        self.assertEqual(next(item for item in broken.checks if item["id"] == "unknown.birth_time_policy")["status"], "FAIL")

    def test_unknown_luck_cycle_confirmed_assertions_are_regressions(self):
        report = {"summary": {"overview": "첫 대운이 시작되기 전의 현재 구간입니다."},
                  "luck_flow": {"body": "현재 대운에서 좋아지는 점은 안정감입니다.\n다음 대운에서는 지금 정리한 기준이 더 선명하게 드러납니다."}}
        claims = unavailable_luck_assertions(report, restricted=True)
        self.assertEqual({claim["code"] for claim in claims},
                         {"invented_pre_first_cycle", "invented_current_cycle_improvement", "invented_next_cycle_outcome"})

    def test_correct_unknown_luck_limitations_are_not_false_positives(self):
        report = {"summary": {"overview": "출생시간 미상으로 현재/다음 대운을 확인하지 않았습니다."},
                  "luck_flow": {"body": "현재 대운에서 좋아지는 점을 확인하지 않았습니다.\n첫 대운이 시작되기 전의 현재 구간으로 단정하지 않습니다.\n현재 대운에서 좋아지는 점은 확인할 수 없습니다.\n대운과 전환 시점은 계산하지 않았습니다."}}
        self.assertEqual(unavailable_luck_assertions(report, restricted=True), [])

    def test_unknown_english_preview_catches_confirmed_cycle_regressions(self):
        report = {"cards": [{"key": "luck_flow", "title": "Current flow",
                              "preview_paragraphs": ["When emotions rise, the current flow asks for a pause before deciding. Preparing for the next cycle means setting small rules."],
                              "user_takeaway": "Use visible facts."}]}
        claims = unavailable_luck_assertions(report, restricted=True)
        self.assertEqual({claim["code"] for claim in claims},
                         {"invented_current_flow_en", "invented_next_cycle_preparation_en"})
        self.assertTrue(all(claim["block"] == "preview_card:luck_flow" for claim in claims))

    def test_correct_english_unknown_limitations_are_allowed(self):
        report = {"luck_flow": {"body": "Current and next cycles were not calculated.\n"
                                           "We do not assert that the current flow asks for a pause.\n"
                                           "Preparing for the next cycle is not recommended as a calculated timing fact.\n"
                                           "We cannot claim that preparing for the next cycle applies to this result."}}
        self.assertEqual(unavailable_luck_assertions(report, restricted=True), [])

    def test_unknown_english_preview_regression_is_content_fail(self):
        response = response_fixture(unknown=True, locale="en")
        card = next(card for card in response["result"]["free_preview"]["cards"] if card["key"] == "luck_flow")
        card["preview_paragraphs"][0] = "The current flow asks for a pause before deciding."
        verifier = self.verifier(FakeHttp([fallback_config(), HttpResult(200, response, "application/json")]))
        verifier.preview("unknown_time_en", {"is_birth_time_estimated": True, "locale": "en"})
        check = next(check for check in verifier.checks if check["id"] == "unknown_time_en.preview_unavailable_luck_assertions")
        self.assertEqual(check["status"], "FAIL")
        self.assertEqual(verifier.report()["content_failures"], 1)

    def test_run_preserves_five_ko_fixtures_and_adds_en_unknown_with_detail(self):
        client = FakeHttp([
            HttpResult(200, {"status": "ok"}, "application/json"),
            HttpResult(200, '<html><div id="root"></div></html>', "text/html"),
            *[HttpResult(200, {"items": [{"display_name": query, "id": "synthetic-" + query, "tzid": "Asia/Seoul"}]}, "application/json")
              for query in ("서울", "부산", "대전")],
            *[HttpResult(422, {"error_code": "INPUT_SCHEMA_ERROR"}, "application/json") for _ in range(4)],
        ])
        verifier = self.verifier(client)
        seen = {}

        def fake_preview(name, payload):
            seen[name] = payload
            response = response_fixture(unknown=payload.get("is_birth_time_estimated", False), locale=payload.get("locale", "ko"))
            response["result"]["calculation_basis"] = {"accuracy_mode": "legacy"}
            verifier.responses[name] = response
            return response

        with patch.object(verifier, "provider_preflight"), patch.object(verifier, "preview", side_effect=fake_preview), \
             patch.object(verifier, "detail") as detail, patch.object(verifier, "check_lunar_day30"), \
             patch.object(verifier, "compare_personalization"):
            verifier.run()
        self.assertEqual(set(seen), {"known_seoul", "known_busan", "late_zi", "lunar_known", "unknown_time",
                                     "unknown_time_en", "known_seoul_repeat", "known_seoul_explicit_legacy"})
        self.assertEqual(seen["unknown_time_en"], {**seen["unknown_time"], "locale": "en"})
        self.assertEqual([call.args[0] for call in detail.call_args_list], ["known_seoul", "unknown_time", "unknown_time_en"])
        self.assertEqual(detail.call_args_list[1].args[1]["locale"], "ko")
        self.assertEqual(detail.call_args_list[2].args[1]["locale"], "en")

    def test_supported_luck_cycles_do_not_trigger_unknown_policy_check(self):
        report = {"luck_flow": {"body": "현재 대운에서 좋아지는 점은 역할 정리입니다."}}
        self.assertEqual(unavailable_luck_assertions(report, restricted=False), [])

    def test_unknown_detail_assertion_is_content_failure_in_runtime_report(self):
        preview = response_fixture(unknown=True)
        preview["result"]["evidence_sections"] = {"elements": {"status": "ready"}, "luck_cycles": {"status": "disabled"}}
        sections = {key: {"title": key, "body": "보이는 기둥에 따른 참고입니다.", "evidence_ids": ["elements"]}
                    for key in ("core_analysis", "love", "career", "wealth", "luck_flow")}
        sections["luck_flow"]["body"] = "현재 대운에서 좋아지는 점은 안정감입니다."
        detail = {"interpretation": {**sections, "provider": "fallback",
                                     "diagnostics": {"configured_provider": "fallback", "final_provider": "fallback", "attempts": []}}}
        verifier = self.verifier(FakeHttp([fallback_config(), HttpResult(200, detail, "application/json")]))
        verifier.detail("unknown_time", {"is_birth_time_estimated": True}, preview)
        check = next(check for check in verifier.checks if check["id"] == "unknown_time.detail_unavailable_luck_assertions")
        self.assertEqual(check["status"], "FAIL")
        self.assertEqual(verifier.report()["content_failures"], 1)

    def test_live_llm_semantic_validation_remains_separate_human_review(self):
        verifier = self.verifier(FakeHttp([]))
        for index, name in enumerate(("known_seoul", "known_busan", "late_zi")):
            response = response_fixture()
            response["manse"]["elements"]["wood"] += index
            verifier.responses[name] = response
        verifier.compare_personalization()
        check = next(check for check in verifier.checks if check["id"] == "quality.live_llm_semantic_accuracy")
        self.assertEqual(check["status"], "WARN")
        self.assertEqual(check["category"], "human_review")
        self.assertFalse(check["evidence"]["live_llm_executed"])

    def test_daily_date_and_exclusive_solar_term_month_window(self):
        response = response_fixture()
        as_of = datetime.fromisoformat(response["period_flows"]["as_of"])
        self.assertTrue(check_periods(response, as_of, as_of)[0])
        response["period_flows"]["month"]["period_end"] = as_of.strftime("%Y-%m-%d %H:%M:%S")
        self.assertFalse(check_periods(response, as_of, as_of)[0])
        response = response_fixture()
        response["period_flows"]["today"]["period_start"] = "2000-01-01"
        self.assertFalse(check_periods(response, as_of, as_of)[0])

    def test_natal_comparison_excludes_trace_and_period_clock(self):
        first = response_fixture()
        second = copy.deepcopy(first)
        second["trace_id"] = "other"
        second["period_flows"]["as_of"] = "different clock"
        self.assertEqual(natal_facts(first), natal_facts(second))
        second["manse"]["elements"]["wood"] = 3
        self.assertNotEqual(digest(natal_facts(first)), digest(natal_facts(second)))

    def test_identical_love_and_work_bodies_are_content_failures(self):
        verifier = self.verifier(FakeHttp([]))
        for index, name in enumerate(("known_seoul", "known_busan", "late_zi")):
            response = response_fixture()
            response["manse"]["elements"]["wood"] += index
            verifier.responses[name] = response
        verifier.compare_personalization()
        report = verifier.report()
        self.assertEqual(report["functional_failures"], 0)
        self.assertEqual(report["content_failures"], 2)
        self.assertTrue(any(item["category"] == "human_review" for item in report["checks"]))

    def test_personalized_bodies_pass_without_inventing_interest_accuracy(self):
        verifier = self.verifier(FakeHttp([]))
        for index, name in enumerate(("known_seoul", "known_busan", "late_zi")):
            response = response_fixture()
            response["manse"]["elements"]["wood"] += index
            for card in response["result"]["free_preview"]["cards"]:
                card["preview_paragraphs"][0] += " 개인 신호 " + str(index)
            verifier.responses[name] = response
        verifier.compare_personalization()
        self.assertEqual(verifier.report()["content_failures"], 0)
        self.assertEqual(verifier.report()["overall_status"], "WARN")

    def test_default_output_is_in_existing_repo_documentation(self):
        self.assertEqual(DEFAULT_OUTPUT, Path(__file__).resolve().parents[3] / "docs/ai/USER_STORY_VERIFICATION.json")

    def test_cli_returns_nonzero_when_guard_blocked_without_creating_file(self):
        with patch("app.tools.verify_user_story.UserStoryVerifier.run", side_effect=VerificationBlocked("Provider unconfirmed.")), \
             patch.object(Path, "write_text") as write_text, patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(main(["--output", str(DEFAULT_OUTPUT)]), 2)
            report = write_text.call_args[0][0]
            self.assertIn('"overall_status": "BLOCKED"', report)
            self.assertNotIn("1997-09-18", report)


class RealReadingContractVerificationTests(unittest.TestCase):
    """Mutate actual calculated fallback output, not self-consistent fake facts.

    All inputs are synthetic and all providers are explicitly disabled. This
    covers calculation-to-contract linkage without servers, HTTP or file output.
    """

    @classmethod
    def setUpClass(cls):
        from app.domain.saju.pydantic_compat import model_to_dict
        from app.domain.saju.schemas import SajuPreviewRequest
        from app.domain.saju.services.preview_orchestrator import create_saju_preview_response

        cls.payloads = {
            "known_seoul": {"birth_date": "1997-09-18", "birth_time": "14:30", "gender": "female", "region_id": "kr-seoul", "locale": "ko"},
            "known_busan": {"birth_date": "1990-01-01", "birth_time": "10:30", "gender": "male", "region_id": "kr-busan", "locale": "ko"},
            "known_en": {"birth_date": "1997-09-18", "birth_time": "14:30", "gender": "female", "region_id": "kr-seoul", "locale": "en"},
            "late_zi": {"birth_date": "1988-11-20", "birth_time": "23:30", "gender": "male", "region_id": "kr-seoul", "locale": "ko"},
            "unknown_ko": {"birth_date": "1997-09-18", "birth_time": "00:00", "gender": "female", "region_id": "kr-seoul", "locale": "ko", "is_birth_time_estimated": True},
            "unknown_en": {"birth_date": "1997-09-18", "birth_time": "00:00", "gender": "female", "region_id": "kr-seoul", "locale": "en", "is_birth_time_estimated": True},
        }
        cls.responses = {}
        with patch("app.config.settings.llm_provider", "fallback"):
            for name, payload in cls.payloads.items():
                response = create_saju_preview_response(payload=SajuPreviewRequest(**payload), trace_id="test-knowledge-contract",
                                                        debug_requested=False, service_name="verification-tests", report_mode="free_preview")
                cls.responses[name] = model_to_dict(response)
                if response.result.free_preview.provider != "fallback" or response.result.free_preview.diagnostics.attempts:
                    raise AssertionError("Real contract tests must remain tokenless fallback.")

    def audit(self, response=None, fixture="known_seoul"):
        verifier = UserStoryVerifier(FakeHttp([]), "http://127.0.0.1:8000", "http://127.0.0.1:5173")
        verifier.check_reading_contract(fixture, self.payloads[fixture], response if response is not None else self.responses[fixture])
        return verifier

    def fresh(self, key="core", fixture="known_seoul"):
        response = copy.deepcopy(self.responses[fixture])
        card = next(card for card in response["result"]["free_preview"]["cards"] if card["key"] == key)
        return response, card

    def assert_failure(self, verifier, suffix):
        checks = [check for check in verifier.checks if check["id"].endswith(suffix)]
        self.assertEqual(len(checks), 1, verifier.checks)
        self.assertEqual(checks[0]["status"], "FAIL", checks[0])

    def test_real_ko_en_calculation_markers_capabilities_and_rendered_blocks_pass(self):
        for name in self.payloads:
            with self.subTest(fixture=name):
                verifier = self.audit(fixture=name)
                self.assertFalse(any(check["status"] == "FAIL" for check in verifier.checks), verifier.checks)
                cards = self.responses[name]["result"]["free_preview"]["cards"]
                critical = any(flag["severity"] == "critical" for flag in self.responses[name]["result"].get("uncertainty_summary", []))
                if critical:
                    self.assertTrue(all(card.get("reading_structure") is None for card in cards))
                else:
                    self.assertTrue(all(card.get("reading_structure") for card in cards if card["key"] in {"core", "love", "work_money"}))
                self.assertEqual(len(self.responses[name]["result"]["free_preview"]["question_capabilities"]), 5)

    def test_real_analysis_notes_pass_both_basis_and_structure_checks(self):
        for name in self.payloads:
            with self.subTest(fixture=name):
                verifier = self.audit(fixture=name)
                verifier.check_basis(name, self.payloads[name], self.responses[name])
                self.assertFalse(any(check["status"] == "FAIL" for check in verifier.checks), verifier.checks)
                for card in self.responses[name]["result"]["free_preview"]["cards"]:
                    structure = card.get("reading_structure")
                    if structure is not None:
                        self.assertEqual(card["basis_explanation"], structure["analysis_note"])
                        self.assertEqual(card["basis_line"], " · ".join(structure["analysis_note"]["facts"]))

    def test_analysis_note_shape_is_required_and_bounded(self):
        for note in (None, {}, {"facts": [], "reading": "기준"},
                     {"facts": ["x"] * 4, "reading": "기준"}, {"facts": ["x" * 97], "reading": "기준"},
                     {"facts": ["기준"], "reading": "y" * 361},
                     {"facts": ["기준"], "reading": "기준", "expert_verified": True}):
            with self.subTest(note=note):
                response, card = self.fresh()
                card["reading_structure"]["analysis_note"] = note
                self.assert_failure(self.audit(response), ".knowledge_core_analysis_note_structure")

    def test_card_note_structure_note_and_basis_line_cannot_drift(self):
        for mutation in ("basis", "structure", "line"):
            with self.subTest(mutation=mutation):
                response, card = self.fresh("love")
                if mutation == "basis":
                    card["basis_explanation"]["reading"] = "카드만 다른 해석 기준을 설명했습니다."
                elif mutation == "structure":
                    card["reading_structure"]["analysis_note"]["reading"] = "구조만 다른 해석 기준을 설명했습니다."
                else:
                    card["basis_line"] = "배우자궁 십성: 없는 사실"
                self.assert_failure(self.audit(response), ".knowledge_love_analysis_note_card_match")

    def test_self_consistent_fabricated_note_cannot_pass_catalog_or_public_fact_checks(self):
        for fixture in ("known_seoul", "known_en"):
            for key in ("core", "love", "work_money", "luck_flow"):
                for field in ("facts", "reading"):
                    with self.subTest(fixture=fixture, key=key, field=field):
                        response, card = self.fresh(key, fixture)
                        note = card["reading_structure"]["analysis_note"]
                        if field == "facts":
                            note["facts"][0] = "계산 결과와 연결되지 않은 가공의 사실입니다."
                        else:
                            note["reading"] = "상대방의 속마음을 확인했고 내년에 반드시 좋은 결과가 나옵니다."
                        card["basis_explanation"] = copy.deepcopy(note)
                        card["basis_line"] = " · ".join(note["facts"])
                        verifier = self.audit(response, fixture)
                        self.assert_failure(verifier, ".knowledge_" + key + "_analysis_note_policy")
                        match = next(check for check in verifier.checks if check["id"].endswith(".knowledge_" + key + "_analysis_note_card_match"))
                        self.assertEqual(match["status"], "PASS")

    def test_analysis_note_from_another_actual_rule_cannot_replace_selected_rule(self):
        response, card = self.fresh("love")
        work = next(item for item in response["result"]["free_preview"]["cards"] if item["key"] == "work_money")
        card["reading_structure"]["analysis_note"] = copy.deepcopy(work["reading_structure"]["analysis_note"])
        card["basis_explanation"] = copy.deepcopy(card["reading_structure"]["analysis_note"])
        card["basis_line"] = " · ".join(card["basis_explanation"]["facts"])
        self.assert_failure(self.audit(response), ".knowledge_love_analysis_note_policy")

    def test_structured_luck_note_does_not_require_a_legacy_next_cycle_comparison(self):
        for fixture in ("known_seoul", "known_en"):
            with self.subTest(fixture=fixture):
                response, card = self.fresh("luck_flow", fixture)
                self.assertIsNotNone(card["reading_structure"])
                self.assertEqual(len(card["basis_explanation"]["facts"]), 2)
                verifier = self.audit(response, fixture)
                verifier.check_basis(fixture, self.payloads[fixture], response)
                self.assertFalse(any(check["id"].endswith(".basis_luck_period_values") for check in verifier.checks))
                self.assertFalse(any(check["status"] == "FAIL" for check in verifier.checks), verifier.checks)
                note = card["reading_structure"]["analysis_note"]
                note["facts"].append("다음 대운에는 연애와 취업이 모두 보장됩니다.")
                card["basis_explanation"] = copy.deepcopy(note)
                card["basis_line"] = " · ".join(note["facts"])
                self.assert_failure(self.audit(response, fixture), ".knowledge_luck_flow_analysis_note_policy")

    def test_missing_busan_daily_basis_remains_a_functional_failure(self):
        response = copy.deepcopy(self.responses["known_busan"])
        response["period_flows"]["today"]["basis_explanation"] = None
        verifier = self.audit(response, "known_busan")
        verifier.check_basis("known_busan", self.payloads["known_busan"], response)
        self.assert_failure(verifier, ".basis_today_structure")

    def test_forged_versions_source_and_review_are_rejected(self):
        for field, value in (("format_version", "unreviewed-v2"), ("knowledge_version", "fabricated"),
                             ("copy_version", "fabricated"), ("source_id", "model-invented-source"),
                             ("rule_version", 999), ("provenance", "llm_generated"), ("expert_review", "completed")):
            with self.subTest(field=field):
                response, card = self.fresh()
                card["reading_structure"][field] = value
                self.assert_failure(self.audit(response), ".knowledge_core_format")

    def test_fact_path_cannot_be_switched_to_another_calculated_feature(self):
        response, card = self.fresh("love")
        card["reading_structure"]["facts"][0]["source_path"] = "career_facts.month_stem_ten_god"
        self.assert_failure(self.audit(response), ".knowledge_love_fact_paths")

    def test_valid_fact_path_does_not_make_fabricated_value_pass(self):
        response, card = self.fresh("love")
        card["reading_structure"]["facts"][0]["value"] = "확인되지 않은 십성"
        verifier = self.audit(response)
        self.assert_failure(verifier, ".knowledge_love_public_fact_values")
        self.assertEqual(next(check for check in verifier.checks if check["id"].endswith(".knowledge_love_fact_paths"))["status"], "PASS")

    def test_core_count_json_must_match_actual_manse_counts(self):
        response, card = self.fresh()
        fact = next(fact for fact in card["reading_structure"]["facts"] if fact["id"] == "core.element_counts")
        changed = dict(response["manse"]["elements"])
        changed["water"] += 1
        import json
        fact["value"] = json.dumps(changed, sort_keys=True)
        self.assert_failure(self.audit(response), ".knowledge_core_public_fact_values")

    def test_self_consistent_dominant_claim_still_fails_actual_count_guard(self):
        response, card = self.fresh()
        counts = response["manse"]["elements"]
        non_dominant = next(element for element, count in counts.items() if count < max(counts.values()))
        response["result"]["signals"]["dominant_elements"] = [non_dominant]
        next(fact for fact in card["reading_structure"]["facts"] if fact["id"] == "core.dominant_elements")["value"] = non_dominant
        self.assert_failure(self.audit(response), ".knowledge_core_dominant_counts")

    def test_unknown_fact_link_wrong_role_and_wrong_block_rule_are_rejected(self):
        for mutation in ("fact_link", "role", "rule", "kind"):
            with self.subTest(mutation=mutation):
                response, card = self.fresh()
                block = card["reading_structure"]["blocks"][1]
                if mutation == "fact_link":
                    block["fact_ids"] = ["missing-calculated-fact"]
                elif mutation == "role":
                    block["role"] = "action"
                elif mutation == "rule":
                    block["rule_id"] = "another-rule"
                else:
                    block["kind"] = "advice"
                self.assert_failure(self.audit(response), ".knowledge_core_roles_and_links")

    def test_card_takeaway_and_three_paragraphs_cannot_drift_from_blocks(self):
        for mutation in ("takeaway", "extra_paragraph", "paragraph_order"):
            with self.subTest(mutation=mutation):
                response, card = self.fresh()
                if mutation == "takeaway":
                    card["user_takeaway"] = "카드의 결론이 근거 역할과 달라졌습니다."
                elif mutation == "extra_paragraph":
                    card["preview_paragraphs"].append("역할 없이 추가된 네 번째 단락입니다.")
                else:
                    card["preview_paragraphs"] = list(reversed(card["preview_paragraphs"]))
                self.assert_failure(self.audit(response), ".knowledge_core_rendered_text")

    def test_self_consistent_fabricated_scene_is_not_catalog_verified(self):
        response, card = self.fresh("love")
        fabricated = "상대방이 이미 당신을 좋아한다고 확정하는 내용입니다."
        card["reading_structure"]["blocks"][1]["text"] = fabricated
        card["preview_paragraphs"][0] = fabricated
        self.assert_failure(self.audit(response), ".knowledge_love_rendered_text")

    def test_unknown_and_disabled_luck_cannot_receive_verified_marker(self):
        known_marker = next(card for card in self.responses["known_seoul"]["result"]["free_preview"]["cards"]
                            if card["key"] == "luck_flow")["reading_structure"]
        self.assertIsNotNone(known_marker)
        for fixture, disabled in (("unknown_ko", False), ("known_seoul", True)):
            with self.subTest(fixture=fixture):
                response, card = self.fresh("luck_flow", fixture)
                card["reading_structure"] = copy.deepcopy(known_marker)
                if disabled:
                    response["result"]["disabled_sections"] = ["luck_flow"]
                self.assert_failure(self.audit(response, fixture), ".knowledge_luck_exclusion")

    def test_critical_calculation_uncertainty_withholds_all_markers(self):
        response, card = self.fresh("core", "unknown_ko")
        self.assertTrue(any(flag["severity"] == "critical" for flag in response["result"]["uncertainty_summary"]))
        known_core = next(card for card in self.responses["known_seoul"]["result"]["free_preview"]["cards"] if card["key"] == "core")
        card["reading_structure"] = copy.deepcopy(known_core["reading_structure"])
        self.assert_failure(self.audit(response, "unknown_ko"), ".knowledge_critical_exclusion")

    def test_current_luck_public_gan_zhi_and_period_are_not_marker_echo_checks(self):
        for identifier, fabricated in (("luck.current_gan_zhi", "不存在"), ("luck.current_period", "1900-01 ~ 1910-01")):
            with self.subTest(identifier=identifier):
                response, card = self.fresh("luck_flow")
                next(fact for fact in card["reading_structure"]["facts"] if fact["id"] == identifier)["value"] = fabricated
                self.assert_failure(self.audit(response), ".knowledge_luck_flow_public_fact_values")

    def test_english_cycle_fact_uses_display_value_not_raw_hanja(self):
        response, card = self.fresh("luck_flow", "known_en")
        fact = next(fact for fact in card["reading_structure"]["facts"] if fact["id"] == "luck.current_gan_zhi")
        self.assertEqual(fact["source_path"], "current_flow.active_luck_cycle.display_gan_zhi")
        self.assertTrue(fact["value"].isascii())
        year = datetime.fromisoformat(response["period_flows"]["as_of"]).year
        active = next(cycle for cycle in response["manse"]["luck_cycles"] if cycle["start_year"] <= year <= cycle["end_year"])
        fact["value"] = active["gan_zhi"]
        self.assert_failure(self.audit(response, "known_en"), ".knowledge_luck_flow_public_fact_values")

    def test_unexposed_luck_ten_god_is_warned_once_and_never_counted_as_verified_value(self):
        verifier = self.audit()
        verifier.check_reading_contract("known_busan", self.payloads["known_busan"], self.responses["known_busan"])
        warnings = [check for check in verifier.checks if check["id"] == "quality.unobservable_luck_ten_god"]
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["status"], "WARN")
        self.assertFalse(warnings[0]["evidence"]["value_independently_verified"])
        for check in verifier.checks:
            if check["id"].endswith(".knowledge_luck_flow_public_fact_values"):
                self.assertNotIn("luck.current_stem_ten_god", check["evidence"]["checked_fact_ids"])
                self.assertEqual(check["evidence"]["unverified_fact_ids"], ["luck.current_stem_ten_god"])

    def test_all_five_unsupported_questions_reject_probability_ranking_or_event_support(self):
        for index in range(5):
            for field, value in (("status", "supported"), ("supported_scope", "event_probability"),
                                 ("supported_scope", "event_date"), ("supported_scope", "population_percentile"),
                                 ("missing_requirements", []), ("forbidden_claims", [])):
                with self.subTest(index=index, field=field, value=value):
                    response, _ = self.fresh()
                    capability = response["result"]["free_preview"]["question_capabilities"][index]
                    identifier = capability["question_id"]
                    capability[field] = value
                    self.assert_failure(self.audit(response), ".knowledge_unsupported_" + identifier)

    def test_missing_or_duplicate_question_capability_is_not_accepted(self):
        for mutation in ("missing", "duplicate"):
            response, _ = self.fresh()
            capabilities = response["result"]["free_preview"]["question_capabilities"]
            if mutation == "missing":
                capabilities.pop()
            else:
                capabilities[-1] = copy.deepcopy(capabilities[0])
            self.assert_failure(self.audit(response), ".knowledge_question_capabilities")


if __name__ == "__main__":
    unittest.main()
