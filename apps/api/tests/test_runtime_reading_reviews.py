"""Runtime review contract and failure gates; no agent/provider calls."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from app.tools import runtime_reading_reviews as runtime
from app.tools import question_flow_reviews as frozen


def sample():
    fact = {"id": "place", "value": "子", "source_path": "original.place"}
    main = {"case_id": "main", "question_id": "basic.overview", "facts": [fact],
            "source_facts": {"original": {"place": "子"}, "private": "DO_NOT_SEND_TO_READER"},
            "policy": {"event_timing_supported": False, "source": "PRIVATE_RULE"},
            "answer": {"question": "내 사주를 읽어줘", "title": "내 사주", "answer": "배움과 표현을 함께 살피는 사주야.",
                       "sections": [], "notices": [], "memo_sections": [{"title": "근거", "text": "SECRET_MEMO"}]},
            "runtime": {"kind": "main", "followups": [{"id": "stars.dohwa", "title": "도화는 어디에 있어?", "description": "계산 위치를 알려줘"}]}}
    child = copy.deepcopy(main)
    child.update(case_id="selected", question_id="stars.dohwa",
                 runtime={"kind": "followup", "parent_case_id": "main", "followups": []},
                 answer={"question_id": "stars.dohwa", "question": "도화는 어디에 있어?", "title": "도화 위치",
                         "answer": "이번 계산에서는 일지에 있어.", "sections": [], "notices": []})
    return {"schema_version": frozen.SNAPSHOT_VERSION, "cases": [main, child],
            "code_checks": [{"id": "capture", "status": "PASS", "evidence": "Actual fixture contract only"}]}


def review(value, role, kind="fixture"):
    job = runtime.build_job(value, role)
    result = {"schema_version": runtime.VERSION, "role": role, "job_hash": job["job_hash"], "review_kind": kind, "cases": []}
    for index, case in enumerate(value["cases"]):
        checks = [{"id": c["id"], "status": "PASS", "evidence": [{"source": "answer", "quote": case["answer"]["answer"]}],
                   "reason": "Contract test fixture", "repair_target": "none"} for c in runtime.criteria(case, role)]
        item = {"case_index": index, "checks": checks}
        if role == "reader":
            item.update(understood_answer="시험용 재서술", question_fulfillment="met",
                        next_question_id="stars.dohwa" if index == 0 else None,
                        expected_new_information="계산 위치" if index == 0 else "")
        result["cases"].append(item)
    return result, job


class RuntimeReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.value = sample()
        self.source = self.root / "source.json"
        self.source.write_text(json.dumps(self.value, ensure_ascii=False), encoding="utf-8")
        self.jobs = self.root / "jobs"
        self.reviews = self.root / "reviews"
        self.reviews.mkdir()

    def tearDown(self):
        self.temp.cleanup()  # Existing unittest-owned intermediate contract.

    def prepare(self):
        runtime.prepare(self.source, self.jobs)

    def write_reviews(self, transform=None):
        for role in runtime.ROLES:
            r, _ = review(self.value, role, "codex_agent")
            if transform:
                transform(r)
            (self.reviews / (role + "-review.json")).write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")

    def test_reader_projection_keeps_actual_menu_without_private_sources(self):
        job_input = runtime.build_job(self.value, "reader")["input"]
        self.assertEqual(set(job_input), {"cases"})  # No expected-verdict examples in target review.
        text = json.dumps(job_input)
        self.assertIn("stars.dohwa", text)
        for secret in ("SECRET_MEMO", "PRIVATE_RULE", "DO_NOT_SEND_TO_READER", "source_facts"):
            self.assertNotIn(secret, text)

    def test_explicit_answer_roles_match_visible_prose_and_folded_evidence(self):
        answer = self.value["cases"][1]["answer"]
        answer.update(response_mode="question", versions={"format": "basic-question-reading-v3"},
            sections=[{"title": "풀이", "text": "새로 설명하는 뜻", "kind": "reading"},
                      {"title": "근거", "text": "FOLDED_TECHNICAL_SOURCE", "kind": "memo"}],
            notices=["FOLDED_SCOPE"], memo={"reading": "FOLDED_CALCULATION", "facts": []})
        reader = runtime.visible(self.value["cases"][1])
        self.assertEqual(reader["sections"], [{"title": "풀이", "text": "새로 설명하는 뜻"}])
        self.assertEqual(reader["notices"], [])
        self.assertNotIn("FOLDED", json.dumps(reader))
        notes = json.dumps(runtime.memo_sections(answer))
        self.assertIn("FOLDED_TECHNICAL_SOURCE", notes)
        self.assertIn("FOLDED_SCOPE", notes)
        self.assertNotIn("새로 설명하는 뜻", notes)
        evidence = runtime.build_job(self.value, "evidence")["input"]
        self.assertEqual(evidence["cases"][0]["evidence_sources"]["followup_answer.stars.dohwa"], self.value["cases"][1]["answer"]["answer"])

    def test_three_user_requested_checks_are_required_and_child_answers_reviewed(self):
        main = {c["id"] for c in runtime.criteria(self.value["cases"][0], "reader")}
        child = {c["id"] for c in runtime.criteria(self.value["cases"][1], "reader")}
        self.assertTrue({"clarity", "curiosity_satisfaction", "followup_interest"} <= main)
        self.assertTrue({"clarity", "curiosity_satisfaction"} <= child)

    def test_remaining_questions_after_selection_are_also_reviewed(self):
        self.value["cases"][1]["runtime"]["followups"] = [{"id": "stars.dohwa", "title": "다른 질문"}]
        child = {c["id"] for c in runtime.criteria(self.value["cases"][1], "reader")}
        self.assertIn("followup_interest", child)

    def test_selected_answer_cannot_use_another_calculation(self):
        self.value["cases"][0]["source_facts"]["input"] = {"year": 2000}
        self.value["cases"][1]["source_facts"]["input"] = {"year": 2001}
        with self.assertRaisesRegex(ValueError, "differs from its parent"):
            runtime.snapshot(self.value)

    def test_runtime_menu_cannot_drift_from_the_supplied_response(self):
        menu = copy.deepcopy(self.value["cases"][0]["runtime"]["followups"])
        menu[0]["category"] = "stars"
        for case in self.value["cases"]:
            case["source_facts"]["question_flow"] = {"questions": menu}
        self.value["cases"][0]["runtime"]["followups"] = copy.deepcopy(menu)
        runtime.snapshot(self.value)
        self.value["cases"][0]["runtime"]["followups"][0]["title"] = "다른 질문을 표시했다"
        with self.assertRaisesRegex(ValueError, "menu differs"):
            runtime.snapshot(self.value)

    def test_full_contract_pass_preserves_observation_limits(self):
        self.prepare()
        self.write_reviews()
        report = runtime.evaluate(self.jobs, self.reviews)
        self.assertEqual(report["status"], "PASS")
        self.assertFalse(report["real_user_interest_validated"])
        self.assertFalse(report["prediction_accuracy_validated"])
        self.assertFalse(report["browser_verified"])
        self.assertEqual(report["observation_scope"], "frozen_content")
        self.assertEqual(report["source_provenance"], {})

    def test_report_preserves_capture_provenance_without_certifying_api_execution(self):
        self.value["source"] = {"transport": "in_process_asgi", "provider": "fallback", "model_calls": 0}
        self.source.write_text(json.dumps(self.value), encoding="utf-8")
        self.prepare()
        report = runtime.evaluate(self.jobs, self.reviews)
        self.assertEqual(report["source_provenance"], self.value["source"])
        self.assertEqual(report["observation_scope"], "frozen_content")

    def test_policy_projection_keeps_active_rules_and_original_fact_boundary(self):
        case = self.value["cases"][0]
        case["policy"].update(natal_structure_catalog={"rules": {"actual": "bounded"}},
                             distinctive_catalog={"rules": ["actual_theme"]},
                             characteristics={"hidden_old_prose": "not_published"})
        projected = runtime.review_policy(case)
        self.assertNotIn("characteristics", projected)
        self.assertEqual(projected["natal_structure_catalog"], case["policy"]["natal_structure_catalog"])
        self.assertEqual(projected["distinctive_catalog"], case["policy"]["distinctive_catalog"])
        self.assertEqual(projected["projection_scope"]["original_policy_hash"], frozen.digest(case["policy"]))
        self.assertIn("characteristics", case["policy"])

    def test_capture_inputs_reject_calculated_facts_and_duplicate_ids(self):
        from app.tools.capture_runtime_reading import load_inputs
        p = self.root / "births.json"
        value = {"schema_version": "runtime-birth-inputs-v1", "cases": [{"id": "case_1", "input": {"birth_date": "1993-04-22"}}]}
        p.write_text(json.dumps(value), encoding="utf-8")
        self.assertEqual(load_inputs(p), value["cases"])
        value["cases"][0]["input"]["is_lunar_leap_month"] = True
        p.write_text(json.dumps(value), encoding="utf-8")
        self.assertTrue(load_inputs(p)[0]["input"]["is_lunar_leap_month"])
        value["cases"][0]["input"]["is_leap_month"] = True
        p.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(ValueError):
            load_inputs(p)
        del value["cases"][0]["input"]["is_leap_month"]
        value["cases"][0]["input"]["facts"] = []
        p.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(ValueError):
            load_inputs(p)
        del value["cases"][0]["input"]["facts"]
        value["cases"].append(copy.deepcopy(value["cases"][0]))
        p.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(ValueError):
            load_inputs(p)

    def test_code_failure_cannot_be_overridden_by_positive_reviews(self):
        self.value["code_checks"][0]["status"] = "FAIL"
        self.source.write_text(json.dumps(self.value), encoding="utf-8")
        self.prepare()
        self.write_reviews()
        self.assertEqual(runtime.evaluate(self.jobs, self.reviews)["status"], "FAIL")

    def test_missing_and_fixture_reviews_stay_hold(self):
        self.prepare()
        self.assertEqual(runtime.evaluate(self.jobs, self.reviews)["status"], "HOLD")
        for role in runtime.ROLES:
            r, _ = review(self.value, role)
            (self.reviews / (role + "-review.json")).write_text(json.dumps(r), encoding="utf-8")
        self.assertEqual(runtime.evaluate(self.jobs, self.reviews)["status"], "HOLD")

    def test_observed_content_failure_cannot_be_averaged_away(self):
        self.prepare()
        def fail(r):
            if r["role"] == "reader":
                r["cases"][0]["checks"][2]["status"] = "FAIL"
                r["cases"][0]["question_fulfillment"] = "unmet"
        self.write_reviews(fail)
        report = runtime.evaluate(self.jobs, self.reviews)
        self.assertEqual(report["code_status"], "PASS")
        self.assertEqual(report["status"], "FAIL")

    def test_honest_limit_does_not_claim_fulfillment(self):
        self.prepare()
        self.write_reviews(lambda r: r["cases"][0].update(question_fulfillment="unmet") if r["role"] == "reader" else None)
        self.assertEqual(runtime.evaluate(self.jobs, self.reviews)["content_status"], "FAIL")

    def test_missing_displayed_question_response_is_code_fail(self):
        self.value["cases"].pop()
        self.source.write_text(json.dumps(self.value), encoding="utf-8")
        self.prepare()
        self.assertEqual(runtime.evaluate(self.jobs, self.reviews)["code_status"], "FAIL")

    def test_vocabulary_only_main_cannot_pass(self):
        self.value["cases"][0]["answer"]["source_context"] = {"vocabulary_only": True, "interpretation_rules_applied": False}
        self.source.write_text(json.dumps(self.value), encoding="utf-8")
        self.prepare()
        self.write_reviews()
        report = runtime.evaluate(self.jobs, self.reviews)
        self.assertEqual(report["content_status"], "FAIL")
        self.assertTrue(report["content_gates"])

    def test_stale_review_and_changed_rubric_are_rejected(self):
        self.prepare()
        self.write_reviews()
        p = self.reviews / "reader-review.json"
        r = json.loads(p.read_text(encoding="utf-8"))
        r["job_hash"] = "old"
        p.write_text(json.dumps(r), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Stale"):
            runtime.evaluate(self.jobs, self.reviews)

    def test_missing_duplicate_criteria_and_cases_are_rejected(self):
        r, j = review(self.value, "reader")
        for mutate in (lambda x: x["cases"].pop(), lambda x: x["cases"][0]["checks"].pop(),
                       lambda x: x["cases"][1].update(case_index=0),
                       lambda x: x["cases"][0]["checks"][1].update(id="question_fit")):
            changed = copy.deepcopy(r)
            mutate(changed)
            with self.assertRaises(ValueError):
                runtime.validate_review(changed, j, self.value)

    def test_hidden_fabricated_quotes_and_invented_questions_are_rejected(self):
        r, j = review(self.value, "reader")
        for mutate in (lambda x: x["cases"][0].update(next_question_id="invented"),
                       lambda x: x["cases"][0]["checks"][0].update(evidence=[{"source": "memos", "quote": "SECRET_MEMO"}]),
                       lambda x: x["cases"][0]["checks"][0].update(evidence=[{"source": "answer", "quote": "not actually visible"}]),
                       lambda x: x["cases"][0].update(expected_new_information="")):
            changed = copy.deepcopy(r)
            mutate(changed)
            with self.assertRaises(ValueError):
                runtime.validate_review(changed, j, self.value)

    def test_cli_no_reviews_is_hold_and_does_not_overwrite(self):
        self.prepare()
        target = self.root / "report.json"
        args = ["evaluate", "--jobs-dir", str(self.jobs), "--reviews-dir", str(self.reviews), "--output", str(target)]
        self.assertEqual(runtime.main(args), 0)
        self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["status"], "HOLD")
        self.assertEqual(runtime.main(args), 2)

    def test_review_modules_import_without_http_engine_or_settings(self):
        code = "import sys; import app.tools.runtime_reading_reviews; assert not any(n in sys.modules for n in ('app.config','app.main','httpx','app.domain.saju.schemas'))"
        result = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
