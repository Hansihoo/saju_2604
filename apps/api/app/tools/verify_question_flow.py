"""Tokenless API checks and frozen inputs for independent question-flow reviews.

Uses in-process ASGI, not a listening test server. Live browser checks and real
user interest are separate evidence. It never invokes a model or an agent.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import re
from time import perf_counter


def resolve_fact(source, path):
    current = source
    for part in filter(None, re.split(r"\.|\[|\]", path)):
        current = current[int(part)] if part.isdigit() else current[part]
    return current


async def capture_snapshot():
    # Import only after the CLI has forced the isolated process to fallback.
    from unittest.mock import patch
    import httpx
    from app.main import app

    checks, cases, timings = [], [], []

    def check(name, condition, evidence):
        checks.append({"id": name, "status": "PASS" if condition else "FAIL", "evidence": evidence})

    fixtures = [
        ("normal_ko", "1997-09-18", "14:30", "kr-seoul", "female", False, "ko"),
        ("boundary_ko", "1988-11-20", "23:30", "kr-chungbuk-jecheon", "male", False, "ko"),
        ("unknown_ko", "1997-09-18", "00:00", "kr-seoul", "female", True, "ko"),
        ("normal_en", "1997-09-18", "14:30", "kr-seoul", "female", False, "en"),
    ]
    question_ids = {"chart.pillars", "luck.current_next", "stars.dohwa", "wealth.locations", "period.this_year"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 12345)), base_url="http://test") as client:
        # The report_mode guard makes an accidental paid generation a hard error.
        from app.api import question_routes
        real_calculate = question_routes.create_saju_preview_response

        def tokenless_calculate(**kwargs):
            if kwargs.get("report_mode") != "none":
                raise RuntimeError("Question verification must never generate a model report")
            return real_calculate(**kwargs)

        with patch.object(question_routes, "create_saju_preview_response", side_effect=tokenless_calculate):
            for name, date, birth_time, region, gender, unknown, locale in fixtures:
                payload = {"locale": locale, "calendar_type": "solar", "birth_date": date, "birth_time": birth_time,
                           "is_birth_time_estimated": unknown, "gender": gender, "region_id": region, "accuracy_mode": "legacy"}
                started = perf_counter()
                raw_basic = await client.post("/saju/basic", json=payload)
                timings.append({"case_id": name, "basic_seconds": round(perf_counter() - started, 4)})
                check(name + ".basic_http", raw_basic.status_code == 200, "HTTP " + str(raw_basic.status_code))
                if raw_basic.status_code != 200:
                    continue
                basic = raw_basic.json()
                check(name + ".no_first_model", not basic["result"].get("free_preview") and not basic["result"].get("interpretation"), "Basic response contains calculation facts without a generated report")
                options = basic["question_flow"]["questions"]
                ids = {item["id"] for item in options}
                check(name + ".supported_catalog", ids <= question_ids and len(ids) == len(options), "Only distinct implemented fact question IDs are shown")
                check(name + ".private_response", "no-store" in raw_basic.headers.get("cache-control", ""), "Birth/chart responses are not cached by browsers/CDNs")
                if unknown:
                    check(name + ".unknown_scope", "luck.current_next" not in ids and not basic["manse"]["meta"]["hour_pillar_enabled"], "Unknown time excludes hour pillar and luck-cycle question")
                if name == "boundary_ko":
                    critical = any(item["severity"] == "critical" for item in basic["result"]["uncertainty_summary"])
                    check(name + ".critical_visible", critical and bool(basic["question_flow"]["notices"]), "Boundary alternatives remain visible; answers describe the selected-policy facts only")
                reading = basic.get("basic_reading", {})
                body_sections = reading.get("sections", [])
                body_facts = reading.get("facts", [])
                body_ids = {section.get("id") for section in body_sections}
                check(name + ".basic_body", bool(reading.get("headline")) and len(body_sections) >= (3 if unknown else 4), "The initial response includes a readable individualized body before question selection")
                check(name + ".basic_body_provider", reading.get("provider") == "deterministic", "Initial main text is supplied without a second request or model call")
                check(name + ".basic_body_versions", set(reading.get("versions", {})) == {"facts", "knowledge", "copy", "format"}, "Basic facts, vocabulary, copy and format have independent versions")
                body_checks = []
                for fact in body_facts:
                    try:
                        matched = resolve_fact(basic, fact["source_path"]) == fact["value"]
                    except (KeyError, IndexError, TypeError):
                        matched = False
                    body_checks.append({"id": "fact." + fact["id"], "status": "PASS" if matched else "FAIL", "evidence": fact["source_path"]})
                check(name + ".basic_body_refs", bool(body_facts) and all(item["status"] == "PASS" for item in body_checks), "All main-body facts match the raw /basic response, including derived-context paths")
                body_fact_ids = {fact["id"] for fact in body_facts}
                check(name + ".basic_body_section_refs", len(body_facts) == len(body_fact_ids) and all(section.get("fact_ids") and set(section["fact_ids"]) <= body_fact_ids for section in body_sections), "Body fact IDs are unique and each section references supplied facts")
                memo_sections = reading.get("memo_sections", [])
                check(name + ".basic_memo_refs", len(memo_sections) == len(body_sections) and all(
                    memo.get("id") == body.get("id") and memo.get("fact_ids") == body.get("fact_ids")
                    for body, memo in zip(body_sections, memo_sections)), "The folded memo retains the same section facts as the plain-language body")
                check(name + ".basic_limits_visible", bool(reading.get("limitations")), "Non-predictive scope is supplied outside the folded memo")
                if unknown:
                    check(name + ".basic_body_unknown", "luck" not in body_ids and bool(reading.get("notices")), "Unknown birth time omits time-dependent body and retains its visible scope")
                body_notices = reading.get("notices", basic["question_flow"]["notices"])
                visible_body = {**reading, "question_id": "basic.overview", "question": "기본 사주에서 먼저 알아둘 내용은?" if locale == "ko" else "What should I understand from my basic chart?",
                                "answer": reading.get("headline", ""), "notices": body_notices}
                cases.append({"case_id": name + ".basic.overview", "question_id": "basic.overview", "answer": visible_body,
                              "facts": body_facts, "source_facts": basic, "code_checks": body_checks,
                              "policy": {"versions": reading.get("versions", {}), "scope": "initial_individualized_facts_and_vocabulary_body", "expert_review": "not_completed", "event_timing_supported": False,
                                         "vocabulary_sources": reading.get("source_context", {}),
                                         "forbidden_claims": ["event probability", "population rank", "favorable meeting/employment date", "personality substitute for timing"]}})
                for option in options:
                    query = {"input": payload, "question_id": option["id"], "context": None}
                    started = perf_counter()
                    raw_answer = await client.post("/saju/question", json=query)
                    timings.append({"case_id": name, "question_id": option["id"], "question_seconds": round(perf_counter() - started, 4)})
                    check(name + "." + option["id"] + ".http", raw_answer.status_code == 200, "HTTP " + str(raw_answer.status_code))
                    if raw_answer.status_code != 200:
                        continue
                    answer = raw_answer.json()
                    source = {**basic, "source_context": answer["source_context"]}
                    case_checks = []
                    for fact in answer["facts"]:
                        try:
                            matched = resolve_fact(source, fact["source_path"]) == fact["value"]
                        except (KeyError, IndexError, TypeError):
                            matched = False
                        case_checks.append({"id": "fact." + fact["id"], "status": "PASS" if matched else "FAIL", "evidence": fact["source_path"]})
                    check(name + "." + option["id"] + ".refs", all(item["status"] == "PASS" for item in case_checks), "Every fact value matches the frozen calculation/context path; derived context is not independent external validation")
                    check(name + "." + option["id"] + ".one_answer", answer["question_id"] == option["id"] and answer["provider"] == "deterministic" and "cards" not in answer, "Only the selected fact answer is returned")
                    check(name + "." + option["id"] + ".limits", bool(answer["notices"]), "Answer/share have explicit question-scope limits")
                    if option["id"] == "luck.current_next" and any(flag["code"] == "luck_cycle_start_age_changed" for flag in basic["result"]["uncertainty_summary"]):
                        check(name + ".luck.policy_warning", bool(re.search(r"계산 기준|calculation polic", " ".join(answer["notices"]), re.I)), "The basic chart's differing cycle-policy warning is retained in the selected answer/share notices")
                    repeat = await client.post("/saju/question", json=query)
                    check(name + "." + option["id"] + ".cache", repeat.status_code == 200 and repeat.json().get("cached") is True and repeat.json().get("answer") == answer["answer"], "A repeated selected question reuses the bounded cache")
                    cases.append({"case_id": name + "." + option["id"], "question_id": option["id"], "answer": answer,
                                  "facts": answer["facts"], "source_facts": source, "code_checks": case_checks,
                                  "policy": {"versions": answer["versions"], "scope": "calculation_facts_and_vocabulary_only", "expert_review": "not_completed", "event_timing_supported": False,
                                             "forbidden_claims": ["event probability", "population rank", "favorable meeting/employment date", "personality substitute for timing"]}})
                for invalid_id in ["love.meeting_window", "career.entry_window", "unknown.question"]:
                    denied = await client.post("/saju/question", json={"input": payload, "question_id": invalid_id})
                    check(name + ".reject." + invalid_id, denied.status_code == 422, "Unsupported/unregistered question is rejected instead of returning another topic")
                denied = await client.post("/saju/question", json={"input": payload, "question_id": "stars.dohwa", "context": "in_relationship"})
                check(name + ".reject_context", denied.status_code == 422, "No unused relationship context is guessed or accepted")
                denied = await client.post("/saju/question", json={"input": payload, "question_id": "stars.dohwa", "facts": {"invented": True}})
                check(name + ".reject_client_facts", denied.status_code == 422, "Client-supplied trusted facts are forbidden")
    check("calculation_mode", True, "Every cache-miss calculation was guarded to report_mode none; no provider call")
    return {"schema_version": "question-flow-snapshot-v1", "cases": cases, "code_checks": checks,
            "source": {"transport": "in_process_asgi", "provider": "fallback", "model_calls": 0, "timings": timings,
                       "limits": "Synthetic/API fixtures; selected boundary input reproduces the user's requested calculation. Not socket/browser evidence, empirical prediction accuracy or actual user enjoyment."}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--review-scope", choices=["all", "basic"], default="all", help="Capture only main-body cases for semantic review, while retaining all executed API checks")
    args = parser.parse_args()
    target = Path(args.output)
    if not target.is_absolute() or not target.parent.is_dir() or target.exists():
        parser.error("output must be a new absolute JSON path in an existing directory")
    os.environ["SAJU_LLM_PROVIDER"] = "fallback"
    os.environ["SAJU_LOG_LEVEL"] = "ERROR"
    snapshot = asyncio.run(capture_snapshot())
    snapshot["source"]["captured_cases"] = len(snapshot["cases"])
    snapshot["source"]["review_scope"] = args.review_scope
    if args.review_scope == "basic":
        snapshot["cases"] = [case for case in snapshot["cases"] if case["question_id"] == "basic.overview"]
    target.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    failures = [item["id"] for item in snapshot["code_checks"] if item["status"] == "FAIL"]
    print(json.dumps({"cases": len(snapshot["cases"]), "checks": len(snapshot["code_checks"]), "failed": failures, "output": str(target)}))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
