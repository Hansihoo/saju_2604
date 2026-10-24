"""Frozen role projection, stale evidence rejection and honest review grading."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from app.tools import question_flow_reviews as reviews


def snapshot():
    return {"schema_version": reviews.SNAPSHOT_VERSION, "as_of": "2026-10-08T12:00:00+09:00",
            "source": {"provider": "secret-provider"},
            "cases": [{"case_id": "synthetic-1", "question_id": "stars.dohwa",
                       "answer": {"question": "도화는 어디에 있어?", "title": "도화 위치",
                                  "answer": "시주에 한 자리가 있어.", "provider": "secret-provider",
                                  "sections": [{"id": "private-section-id", "title": "위치", "text": "시주 자야."}],
                                  "notices": ["만남 날짜는 판정하지 않았어."],
                                  "memo": {"facts": ["private-memo"], "reading": "private-memo"}},
                       "visible_answer": {"answer": "INJECTED VISIBLE FACT"},
                       "facts": [{"id": "private-fact", "value": "子", "source_path": "private_source"}],
                       "source_facts": {"private_source": "子"},
                       "policy": {"scope": "facts_only"},
                       "code_checks": [{"id": "count", "status": "PASS", "evidence": "1"}]}],
            "code_checks": [{"id": "global", "status": "PASS", "evidence": "matched"}]}


class QuestionFlowReviewsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.snapshot_path = self.root / "input.json"
        self.snapshot_path.write_text(json.dumps(snapshot(), ensure_ascii=False), encoding="utf-8")
        self.jobs_dir = self.root / "jobs"
        self.reviews_dir = self.root / "reviews"
        self.reviews_dir.mkdir()
        reviews.prepare(self.snapshot_path, self.jobs_dir)

    def write_review(self, role, kind="codex_agent", verdict="PASS", future=False):
        job = json.loads((self.jobs_dir / (role + "-job.json")).read_text(encoding="utf-8"))
        value = {"schema_version": reviews.REVIEW_VERSION, "role": role,
                 "job_hash": job["job_hash"], "review_kind": kind,
                 "verdict": verdict, "findings": ["검토 범위 확인"]}
        if role == "questioner":
            value["primary_future_need_met"] = future
            value["usefulness_assessments"] = [{
                "case_index": index, "readability": "PASS", "usefulness": "PASS",
                "information_kind": "direct_fact_answer",
                "learned_information": "선택한 질문의 계산상 위치를 알게 됨",
                "evidence_quote": case["answer"], "reason": "계산 사실 질문에 직접 답함",
            } for index, case in enumerate(job["input"]["cases"])]
        path = self.reviews_dir / (role + "-review.json")
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def test_questioner_is_only_visible_projection(self):
        value = reviews.build_job(snapshot(), "questioner")["input"]
        self.assertEqual(set(value), {"cases"})
        self.assertEqual(set(value["cases"][0]), {"question", "title", "answer", "sections", "notices"})
        text = json.dumps(value)
        for forbidden in ("private", "secret", "INJECTED", "source_facts", "code_checks", "policy"):
            self.assertNotIn(forbidden, text)

    def test_other_roles_are_independent_and_do_not_receive_reviews(self):
        value = snapshot()
        value["questioner_review"] = {"verdict": "FAIL", "interest": "flat"}
        answerer = reviews.build_job(value, "answerer")["input"]
        supervisor = reviews.build_job(value, "supervisor")["input"]
        self.assertIn("source_facts", answerer["cases"][0])
        self.assertNotIn("code_checks", json.dumps(answerer))
        self.assertIn("code_checks", supervisor)
        for projection in (answerer, supervisor):
            self.assertNotIn("questioner_review", json.dumps(projection))

    def test_role_input_does_not_share_mutable_snapshot_objects(self):
        value = snapshot()
        job = reviews.build_job(value, "answerer")
        job["input"]["cases"][0]["facts"][0]["value"] = "changed"
        job["input"]["cases"][0]["answer"]["notices"].append("changed")
        self.assertEqual(value["cases"][0]["facts"][0]["value"], "子")
        self.assertNotIn("changed", value["cases"][0]["answer"]["notices"])

    def test_checked_facts_are_sent_once_without_losing_source_paths(self):
        value = snapshot()
        value["cases"][0]["answer"]["facts"] = copy.deepcopy(value["cases"][0]["facts"])
        original = copy.deepcopy(value)
        for role in ("answerer", "supervisor"):
            case = reviews.build_job(value, role)["input"]["cases"][0]
            self.assertNotIn("facts", case["answer"])
            self.assertEqual(case["facts"], original["cases"][0]["facts"])
            self.assertEqual(case["source_facts"]["private_source"], "子")
        self.assertEqual(value, original)

    def test_source_projection_preserves_indexed_paths_and_guard_fields_only(self):
        value = snapshot()
        case = value["cases"][0]
        case["facts"] = [{"id": "method", "value": "hamji", "source_path": "manse.special_stars[3].method_id"}]
        case["source_facts"] = {
            "manse": {"meta": {"day_master": "庚", "hour_pillar_enabled": False, "visible_pillar_keys": ["year", "month", "day"]},
                      "special_stars": [{"private": "omit"}, {}, {}, {"method_id": "hamji", "unreferenced": "omit"}]},
            "result": {"calculation_basis": {"accuracy_mode": "legacy"}, "uncertainty_summary": [{"severity": "critical"}]},
            "region": {"tzid": "Asia/Seoul", "private": "omit"}, "unreferenced_private": "omit"}
        original = copy.deepcopy(value)
        job = reviews.build_job(value, "supervisor")
        projected = job["input"]["cases"][0]["source_facts"]
        self.assertEqual(projected["manse"]["special_stars"], [None, None, None, {"method_id": "hamji"}])
        self.assertEqual(projected["manse"]["meta"]["day_master"], "庚")
        self.assertEqual(projected["result"]["uncertainty_summary"], [{"severity": "critical"}])
        self.assertNotIn("private", json.dumps(projected))
        self.assertEqual(value, original)
        self.assertEqual(job["input"]["cases"][0]["source_facts_hash"], reviews.digest(case["source_facts"]))

    def test_invalid_missing_mismatched_and_negative_fact_paths_are_rejected(self):
        for path, fact_value in (("missing.path", "子"), ("private_source[-1]", "子"),
                                 ("private_source", "different"), ("private_source.__class__", "子")):
            value = snapshot()
            value["cases"][0]["facts"][0].update(source_path=path, value=fact_value)
            with self.assertRaises(ValueError):
                reviews.build_job(value, "answerer")
        value = snapshot()
        value["cases"][0]["source_facts"]["private_source"] = 1
        value["cases"][0]["facts"][0]["value"] = True
        with self.assertRaises(ValueError):
            reviews.build_job(value, "supervisor")

    def test_missing_review_and_fixture_verdicts_are_hold(self):
        self.assertEqual(reviews.evaluate(self.jobs_dir, self.reviews_dir)["status"], "HOLD")
        for role in reviews.ROLES:
            self.write_review(role, kind="fixture")
        value = reviews.evaluate(self.jobs_dir, self.reviews_dir)
        self.assertEqual(value["status"], "HOLD")
        self.assertIsNone(value["primary_future_need_met"])
        self.assertFalse(value["user_interest_validated"])
        for role in reviews.ROLES:
            self.write_review(role, kind="fixture", verdict="FAIL")
        self.assertEqual(reviews.evaluate(self.jobs_dir, self.reviews_dir)["status"], "HOLD")

    def test_agent_content_pass_does_not_claim_future_or_real_interest(self):
        for role in reviews.ROLES:
            self.write_review(role)
        value = reviews.evaluate(self.jobs_dir, self.reviews_dir)
        self.assertEqual(value["status"], "PASS")
        self.assertFalse(value["primary_future_need_met"])
        self.assertTrue(value["primary_future_need_assessed"])
        self.assertFalse(value["user_interest_validated"])
        self.assertFalse(value["prediction_accuracy_validated"])
        self.assertEqual(value["blindness"], "input_blind_only")
        self.assertEqual(value["code_status"], "PASS")
        self.assertEqual(value["content_usefulness"]["status"], "PASS")

    def test_readable_fact_correct_vocabulary_body_cannot_receive_usefulness_pass(self):
        value = snapshot()
        case = value["cases"][0]
        case["question_id"] = "basic.overview"
        case["answer"].update(
            question="네 사주부터 읽어볼게",
            answer="지금과 올해는 일·책임·평가 이야기야.",
            source_context={"vocabulary_only": True, "interpretation_rules_applied": False},
        )
        input_path = self.root / "glossary-input.json"
        input_path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        self.jobs_dir = self.root / "glossary-jobs"
        reviews.prepare(input_path, self.jobs_dir)
        for role in reviews.ROLES:
            self.write_review(role)
        # Even a mislabeled, unanimous role PASS must not approve this body.
        path = self.reviews_dir / "questioner-review.json"
        questioner = json.loads(path.read_text(encoding="utf-8"))
        questioner["usefulness_assessments"][0]["information_kind"] = "reading_conclusion"
        path.write_text(json.dumps(questioner, ensure_ascii=False), encoding="utf-8")
        result = reviews.evaluate(self.jobs_dir, self.reviews_dir)
        self.assertEqual(set(result["review_states"].values()), {"PASS"})
        self.assertEqual(result["code_status"], "PASS")
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["content_usefulness"]["status"], "FAIL")
        self.assertTrue(result["content_usefulness"]["cases"][0]["capability_gates"])
        self.assertFalse(result["primary_future_need_met"])

    def test_fact_only_basic_and_advice_or_limit_replacements_fail_utility(self):
        for role in reviews.ROLES:
            self.write_review(role)
        path = self.reviews_dir / "questioner-review.json"
        questioner = json.loads(path.read_text(encoding="utf-8"))
        for kind in ("method_only", "generic_advice", "scope_notice_only", "unsupported_substitute"):
            questioner["usefulness_assessments"][0]["information_kind"] = kind
            path.write_text(json.dumps(questioner, ensure_ascii=False), encoding="utf-8")
            result = reviews.evaluate(self.jobs_dir, self.reviews_dir)
            self.assertEqual(result["status"], "FAIL", kind)
            self.assertEqual(result["code_status"], "PASS", kind)
        value = snapshot()
        value["cases"][0]["question_id"] = "basic.overview"
        input_path = self.root / "fact-only-input.json"
        input_path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        self.jobs_dir = self.root / "fact-only-jobs"
        reviews.prepare(input_path, self.jobs_dir)
        for role in reviews.ROLES:
            self.write_review(role)
        self.assertEqual(reviews.evaluate(self.jobs_dir, self.reviews_dir)["status"], "FAIL")

    def test_usefulness_review_requires_every_case_and_literal_visible_evidence(self):
        path = self.write_review("questioner")
        original = json.loads(path.read_text(encoding="utf-8"))
        for changes in ({"case_index": True}, {"case_index": -1}, {"case_index": 1},
                        {"evidence_quote": "private-memo"}, {"evidence_quote": "invented conclusion"},
                        {"information_kind": "supported_event_prediction"}, {"reason": " "}):
            modified = copy.deepcopy(original)
            modified["usefulness_assessments"][0].update(changes)
            path.write_text(json.dumps(modified, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(ValueError):
                reviews.evaluate(self.jobs_dir, self.reviews_dir)
        for missing in ([], None):
            modified = dict(original, usefulness_assessments=missing)
            path.write_text(json.dumps(modified, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "every case"):
                reviews.evaluate(self.jobs_dir, self.reviews_dir)

    def test_one_case_usefulness_failure_cannot_be_averaged_away(self):
        value = snapshot()
        second = copy.deepcopy(value["cases"][0])
        second["case_id"] = "synthetic-2"
        value["cases"].append(second)
        input_path = self.root / "two-case-input.json"
        input_path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        self.jobs_dir = self.root / "two-case-jobs"
        reviews.prepare(input_path, self.jobs_dir)
        for role in reviews.ROLES:
            self.write_review(role)
        path = self.reviews_dir / "questioner-review.json"
        questioner = json.loads(path.read_text(encoding="utf-8"))
        questioner["usefulness_assessments"][1].update(usefulness="FAIL", information_kind="method_only")
        path.write_text(json.dumps(questioner, ensure_ascii=False), encoding="utf-8")
        result = reviews.evaluate(self.jobs_dir, self.reviews_dir)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual([item["effective_usefulness"] for item in result["content_usefulness"]["cases"]], ["PASS", "FAIL"])
        questioner["usefulness_assessments"][1]["case_index"] = 0
        path.write_text(json.dumps(questioner, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            reviews.evaluate(self.jobs_dir, self.reviews_dir)

    def test_unclear_usefulness_cannot_be_promoted_to_pass(self):
        for role in reviews.ROLES:
            self.write_review(role)
        path = self.reviews_dir / "questioner-review.json"
        questioner = json.loads(path.read_text(encoding="utf-8"))
        questioner["usefulness_assessments"][0]["information_kind"] = "unclear"
        path.write_text(json.dumps(questioner, ensure_ascii=False), encoding="utf-8")
        result = reviews.evaluate(self.jobs_dir, self.reviews_dir)
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["content_usefulness"]["status"], "HOLD")

    def test_future_need_claim_requires_a_supported_timing_case(self):
        for role in reviews.ROLES:
            self.write_review(role, future=True)
        result = reviews.evaluate(self.jobs_dir, self.reviews_dir)
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(result["primary_future_need_met"])
        self.assertTrue(result["content_usefulness"]["violations"])

    def test_overall_questioner_hold_does_not_hide_a_known_case_failure(self):
        for role in reviews.ROLES:
            self.write_review(role)
        path = self.reviews_dir / "questioner-review.json"
        questioner = json.loads(path.read_text(encoding="utf-8"))
        questioner["verdict"] = "HOLD"
        questioner["usefulness_assessments"][0].update(usefulness="FAIL", information_kind="method_only")
        path.write_text(json.dumps(questioner, ensure_ascii=False), encoding="utf-8")
        result = reviews.evaluate(self.jobs_dir, self.reviews_dir)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["content_usefulness"]["status"], "FAIL")
        self.assertEqual(result["review_states"]["questioner"], "HOLD")

    def test_code_fail_cannot_be_overruled(self):
        value = snapshot()
        value["code_checks"][0]["status"] = "FAIL"
        other_path = self.root / "failing-input.json"
        other_path.write_text(json.dumps(value), encoding="utf-8")
        self.jobs_dir = self.root / "failing-jobs"
        reviews.prepare(other_path, self.jobs_dir)
        for role in reviews.ROLES:
            self.write_review(role)
        self.assertEqual(reviews.evaluate(self.jobs_dir, self.reviews_dir)["status"], "FAIL")

    def test_stale_review_hash_is_rejected(self):
        path = self.write_review("questioner")
        value = json.loads(path.read_text(encoding="utf-8"))
        value["job_hash"] = "old-job"
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Stale"):
            reviews.evaluate(self.jobs_dir, self.reviews_dir)

    def test_job_snapshot_and_version_mutations_are_rejected(self):
        for filename, field in (("questioner-job.json", "prompt_version"),
                                ("snapshot.json", "as_of"),
                                ("manifest.json", "snapshot_hash")):
            path = self.jobs_dir / filename
            original = path.read_text(encoding="utf-8")
            value = json.loads(original)
            value[field] = "changed"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(ValueError):
                reviews.evaluate(self.jobs_dir, self.reviews_dir)
            path.write_text(original, encoding="utf-8")

    def test_unknown_fields_wrong_role_and_missing_future_are_rejected(self):
        path = self.write_review("questioner")
        original = json.loads(path.read_text(encoding="utf-8"))
        for mutation in ({"other_review": {}}, {"role": "supervisor"}, {"primary_future_need_met": "false"}):
            value = dict(original, **mutation)
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(ValueError):
                reviews.evaluate(self.jobs_dir, self.reviews_dir)
        value = copy.deepcopy(original)
        value.pop("primary_future_need_met")
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(ValueError):
            reviews.evaluate(self.jobs_dir, self.reviews_dir)

    def test_output_paths_are_explicit_and_never_overwritten(self):
        with self.assertRaises(FileExistsError):
            reviews.prepare(self.snapshot_path, self.jobs_dir)
        with self.assertRaises(ValueError):
            reviews.prepare(self.snapshot_path, "relative-jobs")
        with self.assertRaises(ValueError):
            reviews.prepare(self.snapshot_path, self.root / "missing" / "jobs")
        output = self.root / "report.json"
        output.write_text("retained", encoding="utf-8")
        self.assertEqual(reviews.main(["evaluate", "--jobs-dir", str(self.jobs_dir),
                                      "--reviews-dir", str(self.reviews_dir), "--output", str(output)]), 2)
        self.assertEqual(output.read_text(encoding="utf-8"), "retained")

    def test_failed_supervisor_review_fails_cli_and_retains_report(self):
        self.write_review("questioner")
        self.write_review("answerer")
        self.write_review("supervisor", verdict="FAIL")
        output = self.root / "failed-review.json"
        code = reviews.main(["evaluate", "--jobs-dir", str(self.jobs_dir),
                             "--reviews-dir", str(self.reviews_dir), "--output", str(output)])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["status"], "FAIL")

    def test_invalid_cases_are_rejected_before_output_creation(self):
        mutations = []
        bad = snapshot()
        bad["cases"].append(copy.deepcopy(bad["cases"][0]))
        mutations.append(bad)
        bad = snapshot()
        bad["cases"][0]["answer"]["notices"] = [False]
        mutations.append(bad)
        bad = snapshot()
        bad["code_checks"][0]["status"] = "passed"
        mutations.append(bad)
        bad = snapshot()
        bad["cases"][0]["answer"]["question_id"] = "another.question"
        mutations.append(bad)
        bad = snapshot()
        bad["cases"][0]["answer"]["facts"] = []
        mutations.append(bad)
        for index, value in enumerate(mutations):
            self.snapshot_path.write_text(json.dumps(value), encoding="utf-8")
            output = self.root / ("bad-%d" % index)
            with self.assertRaises(ValueError):
                reviews.prepare(self.snapshot_path, output)
            self.assertFalse(output.exists())

    def test_import_has_no_domain_http_settings_or_existing_role_dependencies(self):
        code = ("import sys,json; import app.tools.question_flow_reviews; "
                "print(json.dumps([x for x in sys.modules if x.startswith(('app.domain','app.config','app.api','app.tools.agent_verification'))]))")
        result = subprocess.run([sys.executable, "-B", "-c", code], cwd=os.getcwd(),
                                capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout), [])


if __name__ == "__main__":
    unittest.main()
