"""Contract, dependency, orchestration and mocked process tests. No paid inference."""

import ast
import json
import os
import subprocess
import tempfile
import threading
import time
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch

from app.tools.agent_verification import contracts
from app.tools.agent_verification.cases import cases, DEFAULT_AS_OF
from app.tools.agent_verification.checks import answer_checks, evaluate
from app.tools.agent_verification.cli import main, parser
from app.tools.agent_verification.contracts import (AgentResult, AgentTask, CaseSnapshot, OUTPUT_MODELS,
    REVIEW_NAMES, assert_digest, digest, wire)
from app.tools.agent_verification.jobs import (CONTENT_POLICY_VERSION, PROMPTS, build_task,
                                             task_request, verified_answer)
from app.tools.agent_verification.runner import JobExecutor, RunLimits, run_snapshots
from app.tools.agent_verification.storage import read_artifact, write_artifact
from app.tools.agent_verification.transports import (CodexConfig, CodexTransport, FixtureTransport,
                                                     TransportError, TransportReply)


def snapshot(case_id="S3", *, failed=False, no_section=False):
    case = cases()[case_id]
    section = dict(question="책임을 맡으면 인정도 따라올까?", rule_id="work_money.officer", rule_version=1,
                   facts=[dict(id="career.month_stem_ten_god", value="정관", source_path="career_facts.month_stem_ten_god")],
                   blocks=[dict(role=role, text=text) for role, text in zip(
                       ("answer", "scene", "tradeoff", "action"),
                       ("책임 범위와 평가 기준을 살피는 방향으로 읽었어.", "예를 들면 맡는 업무부터 정리하는 장면이야.",
                        "책임이 늘어도 보상까지 보장되는 것은 아니야.", "업무 범위와 평가 기준을 한 가지씩 적어봐."))],
                   analysis_note=dict(facts=["월간 십성: 정관"], reading="월간 십성은 정관입니다. 책임 범위에 관한 해석을 검토했습니다."))
    policy = dict(id="work_money.officer", version=1, status="active_project_policy",
                  wording={locale: {"next_question": "편한 업무 환경은 무엇일까?"} for locale in ("ko", "en")})
    section = None if no_section else section
    plan = {"sections": {case.topic: deepcopy(section)} if section else {}, "question_capabilities": []}
    if case.question_id in {"career.reward_window", "love.meeting_window", "fortune.population_comparison"}:
        plan["question_capabilities"] = [dict(question_id=case.question_id, status="needs_rule_review")]
    if section:
        section = dict(section, policy_rule=policy)
    payload = dict(career_facts={"month_stem_ten_god": "정관"}, limitations=["개인 상황은 별도로 확인해야 합니다."],
                   profile={"is_birth_time_estimated": case_id == "S5"}, disabled_sections=["luck_flow"] if case_id == "S5" else [],
                   uncertainty_summary=[])
    data = dict(schema_version="agent-snapshot-v1", case=wire(case), as_of=DEFAULT_AS_OF, timezone="Asia/Seoul",
                source_revision="test-revision", source_hash="test-source-hash", versions={"test": "1"},
                calculation_state="failed" if failed else "passed", calculation_issue="input_validation_422" if failed else None,
                payload=payload if not failed else {}, reading_plan=plan if not failed else {},
                selected_section=section if not failed else None, visible={"question": case.question})
    return CaseSnapshot(**dict(data, snapshot_hash=digest(data)))


def result_for(snap, role="answer", answer=None, *, provider="fixture", mutate=None):
    checks = answer_checks(snap, answer) if role == "supervisor" else ()
    task = build_task(snap, role, answer, code_checks=checks)
    output = FixtureTransport().execute(task, timeout=1, attempt_dir=Path("unused")).output
    if mutate:
        mutate(output)
    return AgentResult(run_id="test-run", attempt_id=task.job_id, task=task, provider=provider,
                       execution_state="completed", duration_ms=0, output=output, output_hash=digest(output))


class AgentContractTests(unittest.TestCase):
    def test_output_schemas_forbid_extra_fields(self):
        for role, model in OUTPUT_MODELS.items():
            self.assertFalse(contracts.model_schema(model)["additionalProperties"], role)
        snap = snapshot()
        bad = result_for(snap, mutate=lambda out: out.update(expert_review="completed"))
        self.assertEqual(evaluate(snap, [bad]).status, "FAIL")

    def test_snapshot_and_task_tamper_are_rejected(self):
        snap = snapshot()
        modified = wire(snap)
        modified["payload"]["career_facts"]["month_stem_ten_god"] = "편재"
        with self.assertRaises(ValueError):
            build_task(CaseSnapshot(**modified), "answer")
        task = wire(build_task(snap, "answer"))
        task["input"]["question"] = "Another question"
        with self.assertRaises(ValueError):
            task_request(AgentTask(**task))

    def test_source_fact_mutation_fails_even_with_recomputed_hash(self):
        data = wire(snapshot())
        data["payload"]["career_facts"]["month_stem_ten_god"] = "편재"
        data.pop("snapshot_hash")
        snap = CaseSnapshot(**dict(data, snapshot_hash=digest(data)))
        report = evaluate(snap, [result_for(snap)])
        self.assertEqual(report.status, "FAIL")
        self.assertEqual(next(c.status for c in report.checks if c.name == "snapshot_source_consistency"), "FAIL")

    def test_single_answer_does_not_claim_whole_verification(self):
        snap = snapshot()
        report = evaluate(snap, [result_for(snap, provider="codex")])
        self.assertEqual(report.status, "HOLD")
        self.assertEqual({c.name for c in report.checks if c.name.endswith("_missing")}, {"user_missing", "supervisor_missing"})

    def test_user_input_is_blind_to_internal_facts_and_checks(self):
        snap = snapshot()
        answer = result_for(snap)
        task = build_task(snap, "user", answer)
        self.assertEqual(set(task.input), {"persona", "question", "locale", "blind_candidate_id", "visible"})
        prompt, payload, _ = task_request(task)
        self.assertNotIn("snapshot_hash", payload)
        self.assertNotIn("claim_refs", payload["visible"])
        self.assertNotIn("selected_section", payload)
        self.assertNotIn(answer.task.job_id, json.dumps(payload))

    def test_supervisor_has_no_user_review_in_its_input(self):
        snap = snapshot()
        answer = result_for(snap)
        task = build_task(snap, "supervisor", answer, code_checks=answer_checks(snap, answer))
        self.assertNotIn("user_review", task.input)
        self.assertIn("code_checks", task.input)

    def test_review_requires_answer_and_rejects_stale_snapshot(self):
        snap = snapshot()
        with self.assertRaises(ValueError):
            build_task(snap, "user")
        with self.assertRaises(ValueError):
            build_task(snapshot("S2"), "supervisor", result_for(snap))

    def test_review_of_old_answer_revision_fails(self):
        snap = snapshot()
        first = result_for(snap)
        user = result_for(snap, "user", first)
        second = result_for(snap, mutate=lambda out: out.update(answer="책임과 평가 기준을 다시 정리하는 해석이야."))
        report = evaluate(snap, [second, user])
        self.assertEqual(report.status, "FAIL")
        self.assertEqual(next(c.status for c in report.checks if c.name == "user_input_binding"), "FAIL")

    def test_nonexistent_quote_and_duplicate_rubric_fail(self):
        snap = snapshot()
        answer = result_for(snap)
        user = result_for(snap, "user", answer, mutate=lambda out: out.update(quotes=["made up quotation"]))
        self.assertEqual(evaluate(snap, [answer, user]).status, "FAIL")
        supervisor = result_for(snap, "supervisor", answer,
                                mutate=lambda out: out["items"][-1].update(name=out["items"][0]["name"]))
        self.assertEqual(evaluate(snap, [answer, supervisor]).status, "FAIL")

    def test_fact_failure_cannot_be_overruled_by_supervisor(self):
        snap = snapshot()
        answer = result_for(snap, provider="codex", mutate=lambda out: out["analysis_note"].update(facts=["월간 십성: 편재"]))
        supervisor = result_for(snap, "supervisor", answer, provider="codex",
                                mutate=lambda out: [item.update(grade="pass") for item in out["items"]])
        report = evaluate(snap, [answer, supervisor])
        self.assertEqual(report.status, "FAIL")
        self.assertEqual(next(c.status for c in report.checks if c.name == "analysis_note_facts"), "FAIL")

    def test_unsupported_response_mode_probability_and_false_refs_fail(self):
        snap = snapshot()
        for mutation in (lambda out: out.update(response_mode="supported"),
                         lambda out: out.update(answer="연인을 만날 확률 90%야."),
                         lambda out: out["claim_refs"].append(dict(text_ref="answer", fact_ids=["missing.fact"],
                                                                  rule_ids=["work_money.officer"]))):
            with self.subTest(mutation=mutation):
                self.assertEqual(evaluate(snap, [result_for(snap, mutate=mutation)]).status, "FAIL")

    def test_missing_time_has_no_fake_rule_or_note(self):
        snap = snapshot("S5", no_section=True)
        answer = result_for(snap)
        self.assertEqual(answer.output["response_mode"], "needs_input")
        self.assertEqual(answer.output["claim_refs"], [])
        self.assertEqual(answer.output["analysis_note"], {"facts": [], "reading": ""})
        self.assertTrue(all(c.status == "PASS" for c in answer_checks(snap, answer)))

    def test_calculation_fail_blocks_generation_and_remains_fail(self):
        snap = snapshot("S6", failed=True)
        with self.assertRaises(ValueError):
            build_task(snap, "answer")
        self.assertEqual(evaluate(snap, []).status, "FAIL")

    def test_output_hash_and_duplicate_results_fail(self):
        snap = snapshot()
        answer = result_for(snap)
        data = wire(answer)
        data["output"]["answer"] += " changed"
        self.assertEqual(evaluate(snap, [AgentResult(**data)]).status, "FAIL")
        self.assertEqual(evaluate(snap, [answer, answer]).status, "FAIL")

    def test_fixture_reviews_never_certify_semantics(self):
        snap = snapshot()
        answer = result_for(snap)
        report = evaluate(snap, [answer, result_for(snap, "user", answer), result_for(snap, "supervisor", answer)])
        self.assertEqual(report.status, "HOLD")
        self.assertTrue(all(i["grade"] == "uncertain" for i in report.results[-1].output["items"]))

    def test_saved_result_prompt_version_and_locale_are_rejected(self):
        snap = snapshot()
        for key, value in (("prompt_version", "old"), ("rubric_version", "old"), ("locale", "en")):
            data = wire(result_for(snap))
            task = data["task"]
            task[key] = value
            task.pop("task_hash")
            task["task_hash"] = digest(task)
            self.assertEqual(evaluate(snap, [AgentResult(**data)]).status, "FAIL")

    def test_today_keeps_legacy_output_and_marks_contract_unverified(self):
        data = wire(snapshot("S1", no_section=True))
        data["visible"] = {"question": data["case"]["question"], "answer": "오늘은 할 일을 하나 정리해봐.",
                           "period": {"period_start": "2026-10-05", "period_end": "2026-10-05"}}
        data.pop("snapshot_hash")
        snap = CaseSnapshot(**dict(data, snapshot_hash=digest(data)))
        answer = result_for(snap)
        self.assertEqual(answer.output["response_mode"], "scope_limited")
        self.assertEqual(answer.output["answer"], snap.visible["answer"])
        self.assertEqual(next(c.status for c in answer_checks(snap, answer) if c.name == "today_contract_mapping"), "HOLD")

    def test_unsupported_questions_do_not_receive_personality_substitutes(self):
        for case_id in ("S2", "S3", "S4"):
            for missing_section in (False, True):
                with self.subTest(case_id=case_id, missing_section=missing_section):
                    snap = snapshot(case_id, no_section=missing_section)
                    answer = result_for(snap)
                    self.assertEqual(answer.output["response_mode"], "scope_limited")
                    self.assertEqual(answer.output["question"], snap.case.question)
                    self.assertTrue(all(c.status == "PASS" for c in answer_checks(snap, answer)))
                    self.assertEqual(answer.output["claim_refs"], [])
                    self.assertEqual(answer.output["analysis_note"], {"facts": [], "reading": ""})
                    self.assertEqual(answer.output["next_question"], "")

    def test_personality_copy_after_a_scope_disclaimer_fails(self):
        snap = snapshot()
        texts = {b["role"]: b["text"] for b in snap.selected_section["blocks"]}
        mutations = [lambda out: out.update(answer=out["answer"] + " " + texts["answer"]),
                     lambda out: out.update(action=texts["action"]),
                     lambda out: out.update(scene=texts["scene"]),
                     lambda out: out.update(tradeoff=texts["tradeoff"]),
                     lambda out: out.update(analysis_note=snap.selected_section["analysis_note"]),
                     lambda out: out.update(next_question="연애할 때 난 어떤 타입?")]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                answer = result_for(snap, mutate=mutation)
                checks = answer_checks(snap, answer)
                self.assertEqual(next(c.status for c in checks if c.name == "unsupported_pattern_substitution"), "FAIL")
                supervisor = result_for(snap, "supervisor", answer, provider="codex",
                                        mutate=lambda out: [item.update(grade="pass") for item in out["items"]])
                self.assertEqual(evaluate(snap, [answer, supervisor]).status, "FAIL")

    def test_role_prompts_match_the_versioned_product_feedback_knowledge(self):
        policy_path = Path(__file__).resolve().parents[3] / "docs/ai/PRODUCT_CONTENT_KNOWLEDGE.json"
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        self.assertEqual(CONTENT_POLICY_VERSION, policy["policy_version"])
        for prompt in PROMPTS.values():
            self.assertIn(CONTENT_POLICY_VERSION, prompt)
            for lesson in policy["lessons"]:
                self.assertIn(lesson["id"], prompt)
        data = wire(result_for(snapshot()))
        data["task"]["prompt_version"] = "agent-jobs-2026-10-05.1"
        data["task"].pop("task_hash")
        data["task"]["task_hash"] = digest(data["task"])
        self.assertEqual(evaluate(snapshot(), [AgentResult(**data)]).status, "FAIL")


class AgentExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="agent-tests-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_standalone_execute_is_one_call_without_other_roles(self):
        task = build_task(snapshot(), "answer")
        write_artifact(self.root / "task.json", task)
        with patch("app.tools.agent_verification.cli.make_transport", return_value=FixtureTransport()) as make:
            self.assertEqual(main(["execute", "--task", str(self.root / "task.json"),
                                   "--output-dir", str(self.root / "one")]), 0)
        result = read_artifact(self.root / "one/result.json", AgentResult)
        self.assertEqual(result.task.role, "answer")
        self.assertEqual(result.provider, "fixture")
        make.assert_called_once_with("fixture")
        self.assertEqual(len(json.loads((self.root / "one/events.json").read_text())), 2)

    def test_standalone_user_task_execute_and_evaluate(self):
        snap = snapshot()
        answer = result_for(snap)
        write_artifact(self.root / "snapshot.json", snap)
        write_artifact(self.root / "answer.json", answer)
        self.assertEqual(main(["task", "--snapshot", str(self.root / "snapshot.json"), "--role", "user",
                               "--answer", str(self.root / "answer.json"), "--output", str(self.root / "user-task.json")]), 0)
        self.assertEqual(main(["execute", "--task", str(self.root / "user-task.json"),
                               "--output-dir", str(self.root / "user-job")]), 0)
        self.assertEqual(main(["evaluate", "--snapshot", str(self.root / "snapshot.json"), "--results",
                               str(self.root / "answer.json"), str(self.root / "user-job/result.json"),
                               "--output", str(self.root / "report.json")]), 0)
        self.assertEqual(json.loads((self.root / "report.json").read_text(encoding="utf-8"))["status"], "HOLD")

    def test_actual_concurrency_and_shared_budget(self):
        class Recording(FixtureTransport):
            lock = threading.Lock()
            active, peak = 0, 0
            def execute(inner, *args, **kwargs):
                with inner.lock:
                    inner.active += 1
                    inner.peak = max(inner.peak, inner.active)
                time.sleep(.03)
                try:
                    return super(Recording, inner).execute(*args, **kwargs)
                finally:
                    with inner.lock:
                        inner.active -= 1
        transport = Recording()
        executor = JobExecutor(transport, RunLimits(concurrency=3, max_calls=5))
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(lambda _: executor.execute(build_task(snapshot(), "answer"), output_root=self.root), range(12)))
        self.assertEqual(executor.calls, 5)
        self.assertLessEqual(transport.peak, 3)
        self.assertEqual(sum(r.execution_state == "completed" for r in results), 5)
        self.assertEqual(sum(r.error_code == "call_budget_exhausted" for r in results), 7)

    def test_deadline_skip_does_not_invoke_transport(self):
        transport = Mock(provider="fixture", configured_model=None)
        executor = JobExecutor(transport)
        result = executor.execute(build_task(snapshot(), "answer"), output_root=self.root, case_deadline=time.monotonic()-1)
        self.assertEqual(result.execution_state, "skipped")
        self.assertEqual(executor.calls, 0)
        transport.execute.assert_not_called()

    def test_cleanup_failure_stops_new_calls(self):
        transport = Mock(provider="codex", configured_model=None)
        transport.execute.side_effect = TransportError("process_cleanup_failed", fatal=True)
        executor = JobExecutor(transport)
        first = executor.execute(build_task(snapshot(), "answer"), output_root=self.root)
        second = executor.execute(build_task(snapshot(), "answer"), output_root=self.root)
        self.assertEqual(first.execution_state, "error")
        self.assertEqual(second.error_code, "cleanup_failed_stop")
        self.assertEqual(executor.calls, 1)

    def test_repair_bound_and_history_keep_original_failure(self):
        class Broken(FixtureTransport):
            def execute(inner, *args, **kwargs):
                reply = super(Broken, inner).execute(*args, **kwargs)
                if args[0].role == "answer":
                    reply.output["analysis_note"]["facts"] = ["wrong fact"]
                return reply
        report = run_snapshots([snapshot()], Broken(), output_root=self.root / "repair", limits=RunLimits(max_calls=20, max_repairs=2))
        self.assertEqual(report["calls"], 9)
        self.assertEqual(report["status"], "FAIL")
        history = json.loads((self.root / "repair/S3/history.json").read_text(encoding="utf-8"))
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0]["status"], "FAIL")
        self.assertTrue((self.root / "repair/S3/answer-2.json").exists())
        self.assertFalse((self.root / "repair/S3/answer-3.json").exists())

    def test_answer_only_run_calls_one_and_reports_missing_reviews(self):
        report = run_snapshots([snapshot()], FixtureTransport(), output_root=self.root / "single", roles=("answer",))
        self.assertEqual(report["calls"], 1)
        self.assertEqual(report["status"], "HOLD")
        self.assertEqual(len(report["cases"][0]["results"]), 1)

    def test_bounds_duplicate_cases_and_overwrite(self):
        for kwargs in ({"concurrency": 4}, {"max_repairs": 3}, {"max_calls": 0}, {"run_seconds": 0},
                       {"run_seconds": float("nan")}, {"call_seconds": float("inf")}, {"max_calls": 1.5}):
            with self.assertRaises(ValueError):
                RunLimits(**kwargs)
        with self.assertRaises(ValueError):
            run_snapshots([snapshot(), snapshot()], FixtureTransport(), output_root=self.root / "dupe")
        write_artifact(self.root / "kept.json", {"evidence": "first"})
        with self.assertRaises(FileExistsError):
            write_artifact(self.root / "kept.json", {"evidence": "second"})

    def test_one_corrupt_case_does_not_erase_other_reports(self):
        bad = wire(snapshot("S2"))
        bad["snapshot_hash"] = "corrupt"
        report = run_snapshots([CaseSnapshot(**bad), snapshot()], FixtureTransport(), output_root=self.root / "isolated")
        self.assertEqual({c["case_id"]: c["status"] for c in report["cases"]}, {"S2": "ERROR", "S3": "HOLD"})
        self.assertTrue((self.root / "isolated/report.md").is_file())

    def test_invalid_supervisor_output_survives_repair_loop(self):
        class BadSupervisor(FixtureTransport):
            def execute(inner, *args, **kwargs):
                reply = super(BadSupervisor, inner).execute(*args, **kwargs)
                return TransportReply({}, 0) if args[0].role == "supervisor" else reply
        report = run_snapshots([snapshot()], BadSupervisor(), output_root=self.root / "bad-supervisor",
                               limits=RunLimits(max_repairs=1))
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["calls"], 6)
        self.assertTrue((self.root / "bad-supervisor/report.json").is_file())

    def test_transport_mutation_does_not_change_snapshot(self):
        class Mutating(FixtureTransport):
            def execute(inner, *args, **kwargs):
                args[0].input["selected_section"]["analysis_note"]["facts"] = ["tampered"]
                return TransportReply({}, 0)
        snap = snapshot()
        executor = JobExecutor(Mutating())
        result = executor.execute(build_task(snap, "answer"), output_root=self.root)
        self.assertEqual(result.execution_state, "error")
        assert_digest(snap, "snapshot_hash")

    def test_cancel_stops_pending_calls_and_notifies_transport(self):
        class Blocking(FixtureTransport):
            started = threading.Event()
            release = threading.Event()
            def execute(inner, *args, **kwargs):
                inner.started.set()
                inner.release.wait(timeout=2)
                raise TransportError("run_cancelled")
            def cancel(inner):
                inner.release.set()
        from concurrent.futures import ThreadPoolExecutor
        transport = Blocking()
        executor = JobExecutor(transport, RunLimits(concurrency=1))
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(executor.execute, build_task(snapshot(), "answer"), output_root=self.root) for _ in range(5)]
            self.assertTrue(transport.started.wait(timeout=2))
            executor.cancel()
            results = [future.result(timeout=3) for future in futures]
        self.assertEqual(executor.calls, 1)
        self.assertTrue(all(r.error_code == "run_cancelled" for r in results))

    def test_parent_exited_cleanup_is_not_certified(self):
        process = Mock()
        process.poll.return_value = 0
        with self.assertRaises(TransportError) as raised:
            CodexTransport.stop_owned_tree(process)
        self.assertTrue(raised.exception.fatal)
        self.assertEqual(raised.exception.code, "process_cleanup_unconfirmed")

    def test_cancel_checks_all_active_processes_even_when_one_cleanup_fails(self):
        transport = CodexTransport(CodexConfig(("codex",), str(self.root)))
        first, second = Mock(), Mock()
        transport.active = {id(first): first, id(second): second}
        with patch.object(transport, "stop_owned_tree", side_effect=[TransportError("process_cleanup_unconfirmed", fatal=True), None]) as stop:
            with self.assertRaises(TransportError):
                transport.cancel()
        self.assertEqual(stop.call_count, 2)
        self.assertTrue(transport.cancelled.is_set())

    def test_run_interrupt_preserves_report_and_cancels_queued_cases(self):
        class Blocking(FixtureTransport):
            started = threading.Event()
            release = threading.Event()
            def execute(inner, *args, **kwargs):
                inner.started.set()
                inner.release.wait(timeout=2)
                raise TransportError("run_cancelled")
            def cancel(inner):
                inner.release.set()
        transport = Blocking()
        def interrupted(_futures):
            self.assertTrue(transport.started.wait(timeout=2))
            raise KeyboardInterrupt()
            yield None
        with patch("app.tools.agent_verification.runner.as_completed", side_effect=interrupted):
            report = run_snapshots([snapshot(), snapshot("S2"), snapshot("S4")], transport,
                                   output_root=self.root / "cancelled", roles=("answer",), limits=RunLimits(concurrency=1))
        self.assertTrue(report["cancelled"])
        self.assertEqual(report["calls"], 1)
        self.assertEqual(len(report["cases"]), 3)
        self.assertTrue((self.root / "cancelled/report.md").is_file())

    def test_standalone_interrupt_preserves_result_and_events(self):
        class Interrupted(FixtureTransport):
            def execute(inner, *args, **kwargs):
                raise KeyboardInterrupt()
            def cancel(inner):
                pass
        write_artifact(self.root / "interrupt-task.json", build_task(snapshot(), "answer"))
        with patch("app.tools.agent_verification.cli.make_transport", return_value=Interrupted()):
            code = main(["execute", "--task", str(self.root / "interrupt-task.json"),
                         "--output-dir", str(self.root / "interrupt-one")])
        self.assertEqual(code, 2)
        result = read_artifact(self.root / "interrupt-one/result.json", AgentResult)
        self.assertEqual(result.execution_state, "skipped")
        self.assertEqual(result.error_code, "run_cancelled")
        self.assertTrue((self.root / "interrupt-one/events.json").is_file())

    def test_standalone_case_deadline_limits_transport(self):
        class Timed(FixtureTransport):
            received_timeout = None
            def execute(inner, *args, **kwargs):
                inner.received_timeout = kwargs["timeout"]
                return super(Timed, inner).execute(*args, **kwargs)
        transport = Timed()
        write_artifact(self.root / "timed-task.json", build_task(snapshot(), "answer"))
        with patch("app.tools.agent_verification.cli.make_transport", return_value=transport):
            self.assertEqual(main(["execute", "--task", str(self.root / "timed-task.json"),
                                   "--output-dir", str(self.root / "timed-one"), "--case-seconds", "0.1"]), 0)
        self.assertGreater(transport.received_timeout, 0)
        self.assertLessEqual(transport.received_timeout, 0.100001)

    def test_cancelled_timeout_still_checks_unconfirmed_process(self):
        process = Mock(pid=73)
        transport = CodexTransport(CodexConfig(("codex",), str(self.root)))
        def timeout(*args, **kwargs):
            transport.cancelled.set()
            raise subprocess.TimeoutExpired("codex", 1)
        process.communicate.side_effect = timeout
        with patch("app.tools.agent_verification.transports.subprocess.Popen", return_value=process), \
                patch.object(transport, "stop_owned_tree", side_effect=TransportError("process_cleanup_unconfirmed", fatal=True)) as stop:
            with self.assertRaises(TransportError) as raised:
                transport.execute(build_task(snapshot(), "answer"), timeout=1, attempt_dir=self.root / "unclean")
        stop.assert_called_once_with(process)
        self.assertEqual(raised.exception.process_ids, (73,))
        self.assertIn(id(process), transport.active)
        self.assertEqual(transport.cleanup_state[id(process)], "unconfirmed")

    def test_codex_adapter_forces_schema_readonly_single_call(self):
        task = build_task(snapshot(), "answer")
        config = CodexConfig(executable=("codex",), workdir=str(self.root), model=None)
        transport = CodexTransport(config)
        process = Mock(returncode=0)
        process.communicate.return_value = ('{"type":"turn.completed","secret":"must not be logged"}\n', "secret stderr")
        def launch(command, **kwargs):
            outpath = Path(command[command.index("--output-last-message")+1])
            outpath.write_text(json.dumps(FixtureTransport().execute(task, timeout=1, attempt_dir=self.root).output), encoding="utf-8")
            self.assertIn("--output-schema", command)
            self.assertEqual(command[command.index("--sandbox")+1], "read-only")
            self.assertIn("--json", command)
            self.assertNotIn("--model", command)
            return process
        with patch("app.tools.agent_verification.transports.subprocess.Popen", side_effect=launch) as popen:
            reply = transport.execute(task, timeout=1, attempt_dir=self.root / "codex-one")
        self.assertEqual(popen.call_count, 1)
        self.assertEqual(reply.event_types, ("turn.completed",))
        self.assertEqual(reply.resolved_model, None)
        stdin = process.communicate.call_args.args[0]
        self.assertNotIn(task.job_id, stdin)

    def test_codex_timeout_stops_owned_tree_and_has_no_retry(self):
        process = Mock()
        process.communicate.side_effect = subprocess.TimeoutExpired("codex", 1)
        transport = CodexTransport(CodexConfig(("codex",), str(self.root)))
        with patch("app.tools.agent_verification.transports.subprocess.Popen", return_value=process) as popen, \
                patch.object(transport, "stop_owned_tree") as stop:
            with self.assertRaises(TransportError) as raised:
                transport.execute(build_task(snapshot(), "answer"), timeout=1, attempt_dir=self.root / "timeout")
        self.assertEqual(raised.exception.code, "codex_timeout")
        stop.assert_called_once_with(process)
        self.assertEqual(popen.call_count, 1)

    def test_codex_missing_output_is_error_not_fallback(self):
        process = Mock(returncode=0)
        process.communicate.return_value = ('{"answer":"stdout is not the final file"}', "")
        transport = CodexTransport(CodexConfig(("codex",), str(self.root)))
        with patch("app.tools.agent_verification.transports.subprocess.Popen", return_value=process):
            with self.assertRaises(TransportError) as raised:
                transport.execute(build_task(snapshot(), "answer"), timeout=1, attempt_dir=self.root / "missing")
        self.assertEqual(raised.exception.code, "codex_output_missing_or_oversized")


class DependencyAndClockTests(unittest.TestCase):
    def test_role_modules_have_no_domain_settings_http_imports(self):
        folder = Path(contracts.__file__).parent
        for name in ("contracts", "jobs", "checks", "transports", "runner", "storage", "cases"):
            tree = ast.parse((folder / (name + ".py")).read_text(encoding="utf-8"))
            imports = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
            self.assertFalse(any(i.startswith(("app.domain", "app.config", "app.api")) for i in imports), name)

    def test_help_and_standalone_import_do_not_load_engine(self):
        code = "import sys; from app.tools.agent_verification.cli import parser; assert 'app.config' not in sys.modules; assert not any(x.startswith('app.domain') for x in sys.modules)"
        result = subprocess.run([os.sys.executable, "-B", "-c", code], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertEqual(parser().parse_args(["execute", "--task", "t.json", "--output-dir", "out"]).transport, "fixture")

    def test_fixed_clock_is_used_for_age_and_current_flow(self):
        from datetime import datetime
        from app.domain.saju.services.build_interpretation_payload import _build_current_flow_context
        from app.domain.saju.schemas import SajuPreviewRequest
        request = SajuPreviewRequest(**cases()["S3"].birth_input)
        response = Mock()
        response.region.tzid = "Asia/Seoul"
        with patch("app.domain.saju.services.build_interpretation_payload._local_today", side_effect=AssertionError("wall clock used")):
            context = _build_current_flow_context(request, response, [], as_of=datetime.fromisoformat("2020-01-01T00:00:00+09:00"))
        self.assertEqual(context.current_year, 2020)
        self.assertEqual(context.current_age, 22)


if __name__ == "__main__":
    unittest.main()
