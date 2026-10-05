"""Pure deterministic gates. A model can never change the resulting status."""

import json
import re

from .contracts import (AnswerDraft, CaseReport, Check, OUTPUT_MODELS, REVIEW_NAMES,
                        assert_digest, digest, wire)
from .jobs import answer_text, build_task, task_request, verified_answer

FORBIDDEN = re.compile(r"(?:\d+(?:\.\d+)?\s*%|확률\s*\d|상위\s*\d|백분위|percentile|\b\d+(?:\.\d+)?\s*percent\b|"
                       r"반드시\s*(?:취업|승진|재회|결혼)|전문가\s*검증\s*완료|expert[- ]verified|"
                       r"guaranteed\s*(?:promotion|job|marriage))", re.I)


def check(name, ok, detail):
    return Check(name=name, status="PASS" if ok else "FAIL", detail=detail)


def source_value(payload, path):
    value = payload
    for token in re.findall(r"[^.\[\]]+", path):
        value = value[int(token)] if isinstance(value, list) else value[token]
    if isinstance(value, list):
        return ", ".join(value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)


def snapshot_checks(snapshot):
    issues = []
    section = snapshot.selected_section
    if section is not None:
        copied = dict(section)
        policy = copied.pop("policy_rule", {})
        original = snapshot.reading_plan.get("sections", {}).get(snapshot.case.topic)
        if copied != original:
            issues.append("Selected section differs from captured reading plan")
        if (policy.get("id") != section.get("rule_id") or policy.get("version") != section.get("rule_version")
                or policy.get("status") != "active_project_policy"):
            issues.append("Selected rule identity/status is inconsistent")
        for fact in section.get("facts", []):
            try:
                if source_value(snapshot.payload, fact["source_path"]) != fact["value"]:
                    issues.append("Fact value differs from supplied payload: " + fact["id"])
            except (KeyError, IndexError, TypeError, ValueError):
                issues.append("Missing fact path: " + fact.get("id", "unknown"))
        if any(f.get("severity") == "critical" for f in snapshot.payload.get("uncertainty_summary", [])):
            issues.append("Critical uncertainty must not select a reading rule")
        if snapshot.case.topic == "luck_flow" and (
                snapshot.payload.get("profile", {}).get("is_birth_time_estimated")
                or {"luck_cycles", "luck_flow"}.intersection(snapshot.payload.get("disabled_sections", []))):
            issues.append("Unknown/disabled time flow must not select a reading rule")
    return [check("snapshot_source_consistency", not issues, "; ".join(issues) or "Selected facts match captured source paths")]


def answer_checks(snapshot, result):
    checks = snapshot_checks(snapshot)
    try:
        answer = verified_answer(snapshot, result)
    except (ValueError, TypeError):
        return checks + [check("answer_contract", False, "Answer schema, hash or frozen input mismatch")]
    section = snapshot.selected_section
    checks.append(check("question_identity", answer.question_id == snapshot.case.question_id and
                        answer.question == snapshot.case.question, "Answer must address the fixed question"))
    capability = next((c for c in snapshot.reading_plan.get("question_capabilities", [])
                       if c["question_id"] == snapshot.case.question_id), None)
    expected_mode = "scope_limited" if snapshot.case.topic == "today" or capability else "needs_input" if section is None else "supported"
    if snapshot.case.topic == "today":
        checks.append(Check(name="today_contract_mapping", status="HOLD",
                            detail="Legacy today calculation exists; question-reading contract migration remains unverified"))
    checks.append(check("capability_scope", answer.response_mode == expected_mode,
                        "Expected response mode: " + expected_mode))
    checks.append(check("limitations_preserved", set(snapshot.payload.get("limitations", [])) <= set(answer.limitations),
                        "All supplied calculation limitations must remain visible"))
    refs = answer.claim_refs
    if section and not capability:
        facts = {f["id"] for f in section["facts"]}
        refs_ok = (len(refs) == 5 and len({r.text_ref for r in refs}) == 5
                   and all(set(r.fact_ids) <= facts and set(r.rule_ids) == {section["rule_id"]} for r in refs))
        note_ok = answer.analysis_note.facts == section["analysis_note"]["facts"]
        roles_ok = all(getattr(answer, role).strip() for role in ("scene", "tradeoff", "action"))
    else:
        refs_ok = not refs
        note_ok = not answer.analysis_note.facts and not answer.analysis_note.reading
        roles_ok = True
    checks.extend([check("claim_refs", refs_ok, "Proposed references must resolve to selected facts and rule"),
                   check("analysis_note_facts", note_ok, "Note facts must match the selected section exactly"),
                   check("reading_roles", roles_ok, "Supported patterns require example, tradeoff and action"),
                   check("bounded_claim_scan", FORBIDDEN.search(answer_text(answer)) is None,
                         "Bounded scan for numerical probabilities/ranks and false approvals; not semantic proof")])
    if capability:
        checks.append(check("unsupported_limit_visible", bool(answer.limitations),
                            "Unsupported question requires a visible scope limit; meaning is checked separately"))
        selected_texts = {block["role"]: block["text"].strip() for block in (section or {}).get("blocks", [])}
        copied = any(selected_texts.get(role) and selected_texts[role] in getattr(answer, role)
                     for role in ("answer", "action"))
        no_substitute = (not copied and not answer.scene.strip() and not answer.tradeoff.strip()
                         and not answer.next_question.strip() and not answer.claim_refs
                         and not answer.analysis_note.facts and not answer.analysis_note.reading.strip())
        checks.append(check("unsupported_pattern_substitution", no_substitute,
                            "QF-002: A scope disclaimer cannot turn a personality pattern into the requested future answer; bounded structural/copy check only"))
    return checks


def aggregate_status(checks):
    for status in ("ERROR", "FAIL", "HOLD", "WARN"):
        if any(c.status == status for c in checks):
            return status
    return "PASS"


def evaluate(snapshot, results):
    assert_digest(snapshot, "snapshot_hash")
    checks = [check("calculation", snapshot.calculation_state == "passed",
                    snapshot.calculation_issue or "Calculation snapshot supplied")]
    by_role = {}
    for result in results:
        role = result.task.role
        if role in by_role:
            checks.append(check("unique_role_results", False, "Duplicate role result; choose an explicit revision"))
        by_role[role] = result
        try:
            assert_digest(result.task, "task_hash")
            task_request(result.task)
            identity_ok = (result.task.case_id == snapshot.case.case_id and
                           result.task.snapshot_hash == snapshot.snapshot_hash and result.task.locale == snapshot.case.locale)
            checks.append(check(role + "_binding", identity_ok, "Role task must match frozen case/snapshot"))
            if result.execution_state != "completed":
                checks.append(Check(name=role + "_execution", status="HOLD" if result.execution_state == "skipped" else "ERROR",
                                    detail=result.error_code or "Role unavailable"))
                continue
            checks.append(check(role + "_output_hash", digest(result.output) == result.output_hash,
                                "Output must match recorded content hash"))
            OUTPUT_MODELS[role](**(result.output or {}))
        except (ValueError, TypeError):
            checks.append(check(role + "_contract", False, "Invalid role schema/hash"))
        if result.provider == "fixture":
            checks.append(Check(name=role + "_synthetic_transport", status="HOLD",
                                detail="Fixture validates plumbing only; no live semantic judgment observed"))
    answer_result = by_role.get("answer")
    candidate = None
    if answer_result and answer_result.execution_state == "completed":
        checks.extend(answer_checks(snapshot, answer_result))
        try:
            candidate = verified_answer(snapshot, answer_result)
        except (ValueError, TypeError):
            pass
    if candidate is not None:
        text = answer_text(candidate)
        for role in ("user", "supervisor"):
            result = by_role.get(role)
            if result is None or result.execution_state != "completed":
                continue
            try:
                review = OUTPUT_MODELS[role](**(result.output or {}))
                expected_task = build_task(snapshot, role, answer_result, job_id=result.task.job_id,
                                           code_checks=answer_checks(snapshot, answer_result) if role == "supervisor" else ())
                checks.append(check(role + "_input_binding", wire(expected_task) == wire(result.task),
                                    "Review must use this exact answer and independently derived input"))
                quotes = review.quotes + review.confusing_phrases if role == "user" else [i.quote for i in review.items if i.quote]
                quotes_ok = all(q.strip() and q in text for q in quotes)
                checks.append(check(role + "_quotes", quotes_ok, "Every cited phrase must exist in visible answer"))
                if role == "user":
                    grade = review.limitations_understood
                    checks.append(Check(name="synthetic_understanding", status={"pass": "PASS", "fail": "FAIL", "uncertain": "HOLD"}[grade],
                                        detail="Synthetic reader's scope understanding"))
                    checks.append(Check(name="synthetic_interest", status={"engaging": "PASS", "flat": "WARN", "uncertain": "HOLD"}[review.interest],
                                        detail="Synthetic reaction only; not measured real-user interest"))
                else:
                    checks.append(check("supervisor_rubric", {i.name for i in review.items} == REVIEW_NAMES,
                                        "All five independent rubric items are required"))
                    section = snapshot.selected_section or {}
                    fact_ids = {f["id"] for f in section.get("facts", [])}
                    for item in review.items:
                        refs_ok = set(item.fact_ids) <= fact_ids and set(item.rule_ids) <= {section.get("rule_id")}
                        checks.append(check("supervisor_" + item.name + "_evidence", refs_ok and (item.grade == "uncertain" or bool(item.quote.strip())),
                                            "References must exist; definite judgments require an exact quote"))
                        checks.append(Check(name="semantic_" + item.name,
                                            status={"pass": "PASS", "fail": "FAIL", "uncertain": "HOLD"}[item.grade], detail=item.reason))
            except (ValueError, TypeError):
                checks.append(check(role + "_review_contract", False, "Review contract or input reconstruction failed"))
    for role in ("answer", "user", "supervisor"):
        if role not in by_role:
            checks.append(Check(name=role + "_missing", status="HOLD", detail="This role has not run"))
    checks.append(Check(name="meaning_scope", status="WARN", detail="References and bounded scans do not prove every natural-language claim"))
    checks.append(Check(name="ui_scope", status="WARN", detail="Content only: mobile/click/share success not observed"))
    return CaseReport(case_id=snapshot.case.case_id, snapshot_hash=snapshot.snapshot_hash,
                      status=aggregate_status(checks), checks=checks, results=list(results))
