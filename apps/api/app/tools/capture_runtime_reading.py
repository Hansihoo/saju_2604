"""Capture fresh fallback runtime prose, displayed questions and their actual answers.

Runs in-process ASGI in its own fallback-only process; no model or browser.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re


def load_inputs(path):
    """Only birth requests are injectable; calculation facts/rules are never supplied."""
    from app.tools.question_flow_reviews import _load
    value = _load(path)
    if value.get("schema_version") != "runtime-birth-inputs-v1" or not isinstance(value.get("cases"), list) or not value["cases"]:
        raise ValueError("Expected nonempty runtime-birth-inputs-v1 cases")
    seen = set()
    allowed = {"birth_date", "birth_time", "region_id", "gender", "locale", "calendar_type", "is_lunar_leap_month", "is_birth_time_estimated", "accuracy_mode"}
    for case in value["cases"]:
        if (not isinstance(case, dict) or set(case) != {"id", "input"}
                or not isinstance(case["id"], str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", case["id"])
                or case["id"] in seen or not isinstance(case["input"], dict)
                or not set(case["input"]) <= allowed):
            raise ValueError("Invalid/duplicate birth case or injected calculation fields")
        seen.add(case["id"])
    return value["cases"]


async def capture(case_inputs=None):
    if os.environ.get("SAJU_LLM_PROVIDER") != "fallback":
        raise RuntimeError("Runtime capture requires an isolated fallback-only process")
    import httpx
    from app.main import app
    from app.tools.verify_category_reading import capture as categories
    from app.tools import question_flow_reviews as frozen

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 12345)), base_url="http://test") as client:
        pre = await client.get("/verification/provider")
        if pre.status_code != 200 or pre.json().get("configured_provider") != "fallback" or pre.json().get("fallback_only") is not True:
            raise RuntimeError("Active ASGI app did not confirm fallback-only")
        value = await categories(case_inputs)
        main_cases = list(value["cases"])
        for case in main_cases:
            options = case["source_facts"]["question_flow"]["questions"]
            case["runtime"] = {"kind": "main", "followups": options}
            for option in options:
                raw = await client.post("/saju/question", json={"input": case["source_facts"]["input"], "question_id": option["id"], "context": None})
                value["code_checks"].append({"id": case["case_id"] + ".followup_http." + option["id"],
                    "status": "PASS" if raw.status_code == 200 else "FAIL", "evidence": str(raw.status_code)})
                if raw.status_code != 200:
                    continue
                answer = raw.json()
                source = dict(case["source_facts"], source_context=answer["source_context"])
                child = {"case_id": case["case_id"] + "." + option["id"], "question_id": option["id"],
                         "answer": answer, "facts": answer["facts"], "source_facts": source,
                         "policy": dict(case["policy"], scope="selected_followup_actual_response", versions=answer["versions"]),
                         "code_checks": [], "runtime": {"kind": "followup", "parent_case_id": case["case_id"],
                             "followups": answer["followups"]}}
                # Exact original paths/values are verified, not inferred from prose.
                frozen._source_projection(child)
                child["code_checks"].append({"id": child["case_id"] + ".identity",
                    "status": "PASS" if answer["question_id"] == option["id"] and answer["provider"] == "deterministic" else "FAIL",
                    "evidence": "Actual selected question ID/provider"})
                value["cases"].append(child)
    value["source"].update(captured_at=datetime.now(timezone.utc).isoformat(), runtime_capture_version="runtime-capture-2026-10-10.3",
                           browser_verified=False, original_generation_provider="fallback", displayed_followups_captured=True)
    return value


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True)
    p.add_argument("--inputs", help="Optional runtime-birth-inputs-v1 JSON; defaults retain the existing four cases")
    args = p.parse_args(argv)
    target = Path(args.output)
    if not target.is_absolute() or not target.parent.is_dir() or target.exists():
        p.error("Use a new absolute path in an existing registered directory")
    os.environ["SAJU_LLM_PROVIDER"] = "fallback"
    os.environ["SAJU_LOG_LEVEL"] = "ERROR"
    value = asyncio.run(capture(load_inputs(args.inputs) if args.inputs else None))
    from app.tools.runtime_reading_reviews import snapshot
    from app.tools.question_flow_reviews import _write
    snapshot(value)
    _write(target, value)
    failures = [c["id"] for c in value["code_checks"] if c["status"] == "FAIL"]
    print(json.dumps({"cases": len(value["cases"]), "failures": failures, "model_calls": 0, "output": str(target)}, ensure_ascii=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
