"""The only verification module allowed to import the saju engine.

Capture once; all later roles consume plain immutable JSON artifacts.
"""

import hashlib
import subprocess
from datetime import datetime
from pathlib import Path

from .contracts import CaseSnapshot, CaseSpec, digest, wire


def source_identity():
    root = Path(__file__).resolve().parents[5]
    sha = hashlib.sha256()
    paths = [root / "docs/planning/033-current-calculation-rules.md", root / "apps/api/app/config.py"]
    domain = root / "apps/api/app/domain/saju"
    paths += list(domain.rglob("*.py")) + list((domain / "data").rglob("*.json"))
    paths += list((domain / "data").rglob("*.jsonl"))
    for path in sorted(set(paths)):
        sha.update(path.relative_to(root).as_posix().encode())
        sha.update(path.read_bytes())
    try:
        revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
                                  text=True, timeout=5, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        revision = "unavailable"
    return revision, sha.hexdigest()


def prepare_snapshot(case: CaseSpec, as_of: str) -> CaseSnapshot:
    # Lazy imports keep task execution/evaluation usable without the domain runtime.
    from pydantic import ValidationError
    from app.config import settings
    from app.domain.saju.schemas import SajuPreviewRequest
    from app.domain.saju.pydantic_compat import model_to_dict
    from app.domain.saju.services.preview_orchestrator import create_saju_preview_response
    from app.domain.saju.services.build_interpretation_payload import build_interpretation_payload
    from app.domain.saju.services.build_reading_plan import load_reading_knowledge

    clock = datetime.fromisoformat(as_of)
    if clock.tzinfo is None or clock.utcoffset() is None:
        raise ValueError("as_of must have an explicit UTC offset")
    if settings.use_canonical_year_month_pillars:
        raise ValueError("Verification fixtures require the preserved legacy primary policy")
    revision, source_hash = source_identity()
    bundle = load_reading_knowledge()
    common = dict(case=wire(case), as_of=clock.isoformat(), timezone="Asia/Seoul",
                  source_revision=revision, source_hash=source_hash,
                  versions={"calculation": "033-legacy-primary", "knowledge": bundle.knowledge_version,
                            "copy": bundle.copy_version, "reading_format": bundle.format_version})
    try:
        request = SajuPreviewRequest(**case.birth_input)
    except ValidationError:
        data = dict(common, calculation_state="failed", calculation_issue="input_validation_422",
                    payload={}, reading_plan={}, selected_section=None, visible={})
    else:
        response = create_saju_preview_response(payload=request, trace_id="verification-" + case.case_id,
                   debug_requested=False, service_name="agent-verification", report_mode="none", as_of=clock)
        payload = build_interpretation_payload(request=request, response=response, as_of=clock)
        plan = model_to_dict(payload.reading_plan)
        section = plan["sections"].get(case.topic)
        if case.topic == "today":
            today = model_to_dict(response.period_flows.today)
            visible = {"question": case.question, "answer": today.get("summary", ""),
                       "period": {key: today.get(key) for key in ("period_start", "period_end")}}
        elif section:
            visible = {"question": section["question"], **{b["role"]: b["text"] for b in section["blocks"]},
                       "analysis_note": section["analysis_note"]}
        else:
            visible = {"question": case.question}
        visible["limitations"] = list(payload.limitations)
        raw_payload = model_to_dict(payload)
        rules = {rule.id: model_to_dict(rule) for rule in bundle.rules}
        # The selected rule copy/conditions travel with the snapshot, not a live catalog import.
        if section:
            section = dict(section, policy_rule=rules[section["rule_id"]])
        data = dict(common, calculation_state="passed", calculation_issue=None,
                    payload=raw_payload, reading_plan=plan, selected_section=section, visible=visible)
    data["snapshot_hash"] = digest({"schema_version": "agent-snapshot-v1", **data})
    return CaseSnapshot(**data)
