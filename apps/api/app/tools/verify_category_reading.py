"""Freeze initial full readings through ASGI in an isolated fallback process.

Reuses independent role jobs; generated copy is not certified by code checks.
No server, model or agent is launched by this verifier.
"""
import argparse
import asyncio
import inspect
import json
import os
from pathlib import Path


async def capture(case_inputs=None):
    import httpx
    from app.main import app
    from app.domain.saju.pydantic_compat import model_to_dict
    from app.domain.saju.schemas import SajuPreviewRequest, SajuPreviewResponse
    from app.domain.saju.services.build_interpretation_payload import build_interpretation_payload
    from app.tools.verify_question_flow import resolve_fact
    from app.domain.saju.chart_characteristics import load_characteristic_catalog, group_support, evaluate_characteristics
    from app.domain.saju.services.build_chart_characteristics import _relation, _stem, MAIN_STEMS
    from app.domain.saju.services.build_manse import HIDDEN_STEMS_BY_BRANCH
    from lunar_python.util import LunarUtil
    from app.domain.saju.distinctive_reading import catalog as distinctive_catalog
    from app.domain.saju.natal_structure import catalog as natal_catalog, select_conclusions
    from app.domain.saju.question_followups import QUESTION_MEANINGS, ANSWER_MEANINGS, VERSION as FOLLOWUP_VERSION, select_followups

    checks, cases = [], []
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 12345)), base_url="http://test") as client:
        defaults = (
            ("normal_ko", "1997-09-18", "14:30", "kr-seoul", "female", False, "ko"),
            ("normal_en", "1997-09-18", "14:30", "kr-seoul", "female", False, "en"),
            ("boundary_ko", "1988-11-20", "23:30", "kr-chungbuk-jecheon", "male", False, "ko"),
            ("unknown_ko", "1997-09-18", "00:00", "kr-seoul", "female", True, "ko"),
        )
        selected = case_inputs if case_inputs is not None else [
            {"id": name, "input": {"birth_date": date, "birth_time": time, "region_id": region,
             "gender": gender, "is_birth_time_estimated": unknown, "locale": locale}}
            for name, date, time, region, gender, unknown, locale in defaults]
        for case in selected:
            name = case["id"]
            payload = SajuPreviewRequest(**case["input"])
            locale = payload.locale
            raw = await client.post("/saju/reading", json=json.loads(payload.json()), headers={"X-Saju-Verification-Provider": "fallback"})
            checks.append({"id": name + ".http", "status": "PASS" if raw.status_code == 200 else "FAIL", "evidence": str(raw.status_code)})
            if raw.status_code != 200:
                continue
            data = raw.json()
            category = data["category_reading"]
            sections = category["sections"]
            expected = ["core", "love", "wealth", "career", "luck_flow"]
            checks.append({"id": name + ".categories", "status": "PASS" if [s["id"] for s in sections] == expected else "FAIL", "evidence": "Five ordered reading categories"})
            questions = data["question_flow"]["questions"]
            checks.append({"id": name + ".question_categories", "status": "PASS" if all(q["category"] in expected for q in questions) else "FAIL", "evidence": "Only server-supplied supported questions in their categories"})
            report = data["result"].get("interpretation")
            source = dict(data)
            source["input"] = json.loads(payload.json())
            # The category presentation adds money-location facts to the legacy
            # report. Include their original pillar/hidden-stem sources even
            # when the full report also has selected catalog facts.
            facts = [dict(f) for f in data["basic_reading"]["facts"]]
            facts.extend({**f, "label": f["id"]} for f in category["reading_information"]["facts"])
            distinctive = category.get("distinctive_reading") or {}
            facts.extend({**f, "label": f["id"]} for f in distinctive.get("facts", []))
            natal = category.get("natal_structure") or {}
            facts.extend({**f, "label": f["id"]} for f in natal.get("facts", []))
            for fact in natal.get("facts", []):
                checks.append({"id": name + ".natal_source." + fact["id"],
                    "status": "PASS" if resolve_fact(source, fact["source_path"]) == fact["value"] else "FAIL",
                    "evidence": "Natal structure has exact pillar and independently derived alternate sources"})
            for block in natal.get("blocks", []):
                checks.append({"id": name + ".natal_refs." + block["id"],
                    "status": "PASS" if block["fact_ids"] and all(any(f["id"] == ref for f in facts) for ref in block["fact_ids"]) and
                    all(rule in natal_catalog()["rules"] for rule in block["rule_ids"]) else "FAIL",
                    "evidence": "Structural reading has facts and independently versioned bounded rules"})
            for fact in distinctive.get("facts", []):
                checks.append({"id": name + ".distinctive_source." + fact["id"],
                    "status": "PASS" if resolve_fact(source, fact["source_path"]) == fact["value"] else "FAIL",
                    "evidence": "Applied supplementary theme retains exact original facts; eligible matches are separately recorded"})
            characteristics = category.get("characteristics") or {}
            trait_items = characteristics.get("items", [])
            facts.extend({**f, "label": f["id"]} for f in characteristics.get("facts", []))
            for fact in characteristics.get("facts", []):
                checks.append({"id": name + ".characteristic_source." + fact["id"],
                               "status": "PASS" if resolve_fact(source, fact["source_path"]) == fact["value"] else "FAIL",
                               "evidence": "Structural reading source matches frozen calculation"})
            all_trait_items = trait_items + [i for c in characteristics.get("comparisons", []) for i in c["items"]]
            for item in all_trait_items:
                checks.append({"id": name + ".characteristic_refs." + item["id"],
                               "status": "PASS" if item["fact_ids"] and all(any(f["id"] == ref for f in facts) for ref in item["fact_ids"]) else "FAIL",
                               "evidence": "Project interpretation has source-linked facts and separate emphasis scope"})
            for item in category["reading_information"]["items"]:
                checks.append({"id": name + ".information." + item["id"], "status": "PASS" if item["fact_ids"] and
                               all(any(f["id"] == ref for f in facts) for ref in item["fact_ids"]) else "FAIL",
                               "evidence": "Information item has real fact references"})
            for fact in category["reading_information"]["facts"]:
                checks.append({"id": name + ".source." + fact["id"],
                               "status": "PASS" if resolve_fact(source, fact["source_path"]) == fact["value"] else "FAIL",
                               "evidence": "Original calculation source equals frozen fact value"})
            if report:
                from datetime import datetime
                reading_payload = build_interpretation_payload(request=payload, response=SajuPreviewResponse(**data),
                                                               as_of=datetime.fromisoformat(data["question_flow"]["as_of"]))
                source["reading_payload"] = json.loads(reading_payload.json())
                paths = {f["source_path"] for structure in report.get("reading_sections", {}).values() for f in structure["facts"]}
                # Full prose uses more supplied inputs than the catalog's four
                # selected features. Freeze those too, rather than calling them
                # absent merely because the projection omitted them.
                paths.update({"day_master", "element_counts", "love_facts", "career_facts", "wealth_facts", "current_flow"})
                for index, path in enumerate(sorted(paths)):
                    facts.append({"id": "reading." + str(index), "label": path,
                                  "value": resolve_fact(source["reading_payload"], path), "source_path": "reading_payload." + path})
            else:
                source["source_context"] = data["basic_reading"]["source_context"]
            critical = category["source_context"]["critical_hold"]
            title = "내 사주를 분야별로 읽어줘" if locale == "ko" else "Read my chart by category"
            visible_sections, memo_sections = [], []
            for s in sections:
                if not s.get("visible", True):
                    continue
                main, memos = [], []
                active_core = s["id"] == "core" and bool(trait_items)
                if active_core:
                    if characteristics.get("assumption"):
                        main.append(characteristics["assumption"])
                    for direction, ko, en in (("advantage", "장점으로 읽는 부분", "Potential advantages"), ("burden", "부담으로 읽는 부분", "Potential burdens")):
                        selected = [i for i in trait_items if i["direction"] == direction]
                        if selected:
                            main.append("### " + (ko if locale == "ko" else en))
                        for item in selected:
                            main.append("### " + item["title"] + " · " + ("풀이 비중" if locale == "ko" else "Reading emphasis") + " · " + item["emphasis_label"] + "\n\n" + "\n\n".join(item[k] for k in ("conclusion", "reason", "emphasis_reason", "condition")))
                            memos.append("### " + item["title"] + " · " + item["emphasis_label"] + "\n" + item["emphasis_reason"] + "\n\n" + item["memo_body"])
                    main.append(characteristics["scale_note"])
                    titles = {i["id"]: i["title"] for i in all_trait_items}
                    for comp in characteristics.get("comparisons", []):
                        memos.append("### " + comp["label"] + "\n" + " · ".join(comp["chart"][k] for k in ("year", "month", "day", "time")))
                        memos.append("아래는 본문에 선택된 항목끼리의 비교야. 빠진 항목이 그 사주에 전혀 없다는 뜻은 아니야." if locale == "ko" else "This compares the items selected for the main reading. An unselected item is not necessarily absent from that chart.")
                        comparison_labels = ({"unchanged": "같은 항목·비중", "changed": "비중이 달라진 항목", "added": "대신 선택된 항목", "removed": "이번에는 선택되지 않은 항목"} if locale == "ko" else {"unchanged": "Same item and emphasis", "changed": "Different emphasis", "added": "Selected instead", "removed": "Not selected here"})
                        for kind in ("unchanged", "changed", "added", "removed"):
                            if comp[kind]:
                                memos.append(comparison_labels[kind] + ": " + " · ".join(titles[i] for i in comp[kind]))
                        for item in comp["items"]:
                            memos.append("### " + item["title"] + " · " + item["emphasis_label"] + "\n" + "\n\n".join(item[k] for k in ("conclusion", "reason", "emphasis_reason", "condition", "memo_body")))
                elif s.get("information") and critical:
                    main.append("선택한 명식의 잠정 정보" if locale == "ko" else "Provisional information for the selected chart")
                main.extend("### " + item["title"] + "\n" + item["body"] for item in s.get("information", [])
                            if not (active_core and item["id"] == "structure.day_month"))
                if not critical and not active_core:
                    main.append(s["body"])
                memos.append(s["memo_body"])
                if s.get("publication"):
                    published = s["publication"]
                    main = [published["notice"]] if published.get("notice") else []
                    main.extend((("### " + b["title"] + "\n") if b.get("title") else "") + b["text"] for b in published["blocks"])
                    memos = [published["memo_body"]]
                visible_sections.append({"title": s["title"], "text": "\n\n".join(main)})
                memo_sections.append({"title": s["title"], "text": "\n\n".join(memos)})
            answer = {"question_id": "basic.overview", "question": title, "title": "사주팔자" if locale == "ko" else "Your birth chart",
                      "answer": sections[0]["publication"]["blocks"][0]["text"] if sections[0].get("publication") else (trait_items[0]["conclusion"] if trait_items else (sections[0]["body"].split("\n\n", 1)[0] if not critical else category["calculation_notices"][0])),
                      "sections": visible_sections, "memo_sections": memo_sections,
                      "notices": category["calculation_notices"] + category["notices"], "facts": facts,
                      "source_context": {**category["source_context"],
                                         "interpretation_rules_applied": any(b["kind"] in {"interpretation", "traditional_theme", "structural_reading"} for s in sections if s.get("visible", True) for b in (s.get("publication") or {}).get("blocks", [])),
                                         "vocabulary_only": not any(b["kind"] in {"interpretation", "traditional_theme", "structural_reading"} for s in sections if s.get("visible", True) for b in (s.get("publication") or {}).get("blocks", [])),
                                         "publication_scopes": {s["id"]: s["publication"]["scope"] for s in sections if s.get("publication")}}}
            cases.append({"case_id": name + ".category_reading", "question_id": "basic.overview", "answer": answer,
                          "facts": facts, "source_facts": source, "code_checks": [],
                          "policy": {"scope": "published_five_chapter_reading", "expert_review": "not_completed", "event_timing_supported": False,
                                     "critical_hold": critical, "reading_sections": report.get("reading_sections", {}) if report else {},
                                     "category_statuses": {s["id"]: s["status"] for s in sections},
                                     "reading_information": category["reading_information"],
                                     "characteristics": characteristics,
                                     "distinctive_reading": distinctive,
                                     "distinctive_catalog": distinctive_catalog(),
                                     "natal_structure": natal,
                                     "natal_structure_catalog": natal_catalog(),
                                     "natal_conclusion_selection_reference": inspect.getsource(select_conclusions),
                                     "question_recommendation": {"version": FOLLOWUP_VERSION,
                                         "question_meanings": {k: sorted(v) for k, v in QUESTION_MEANINGS.items()},
                                         "answer_meanings": {k: sorted(v) for k, v in ANSWER_MEANINGS.items()},
                                         "selection_reference": inspect.getsource(select_followups)},
                                     "characteristic_rules": load_characteristic_catalog(),
                                     "characteristic_evaluation_reference": {
                                         "scope": "Frozen project implementation for rule matching, emphasis and selected-item priority; not an external expert rule.",
                                         "group_support": inspect.getsource(group_support),
                                         "evaluate_characteristics": inspect.getsource(evaluate_characteristics),
                                         "hidden_stem_source": "app.domain.saju.services.build_manse.HIDDEN_STEMS_BY_BRANCH",
                                         "hidden_stems_raw": HIDDEN_STEMS_BY_BRANCH,
                                         "hidden_stems_hanja": {b: [_stem(s) for s in stems] for b, stems in HIDDEN_STEMS_BY_BRANCH.items()},
                                         "month_main_stems": MAIN_STEMS},
                                     "characteristic_relation_reference": {
                                         "source": "lunar_python.util.LunarUtil.SHI_SHEN + canonical localization",
                                         "raw": dict(LunarUtil.SHI_SHEN),
                                         "canonical": {d + s: _relation(d, s)[0] for d in "甲乙丙丁戊己庚辛壬癸" for s in "甲乙丙丁戊己庚辛壬癸"}},
                                     "limits": "Review the actual publication blocks as main prose. Legacy characteristics and raw information remain source material; hidden traits must not earn a usefulness PASS. Definitions and cycle dates are not natal fortune synthesis or event forecasts. Critical full-report hold remains. Wealth/event timing and expert validation stay unsupported."}})
    return {"schema_version": "question-flow-snapshot-v1", "cases": cases, "code_checks": checks,
            "source": {"transport": "in_process_asgi", "provider": "fallback", "model_calls": 0,
                       "limits": "Actual fallback prose and critical holds. Not live Codex, prediction accuracy or real-user interest."}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    target = Path(args.output)
    if not target.is_absolute() or not target.parent.is_dir() or target.exists():
        parser.error("Use a new absolute JSON path in an existing registered directory")
    os.environ["SAJU_LLM_PROVIDER"] = "fallback"
    os.environ["SAJU_LOG_LEVEL"] = "ERROR"
    snapshot = asyncio.run(capture())
    target.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    failed = [c["id"] for c in snapshot["code_checks"] if c["status"] == "FAIL"]
    print(json.dumps({"cases": len(snapshot["cases"]), "failed": failed, "output": str(target)}))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
