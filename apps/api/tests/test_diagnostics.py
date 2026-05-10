import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from app.diagnostics import capture_saju_request_event


class RequestCaptureDiagnosticsTests(unittest.TestCase):
    def test_captures_saju_preview_request_as_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_path = Path(tmp_dir) / "requests.jsonl"

            capture_saju_request_event(
                enabled=True,
                log_path=str(log_path),
                service="suju-insight",
                trace_id="trc_test",
                method="POST",
                path="/saju/preview",
                status_code=422,
                payload={"birth_date": date(2024, 2, 10), "birth_time": "10:30"},
                debug_requested=True,
                stage="input_validation",
                error_code="INPUT_SCHEMA_ERROR",
                message="Request validation failed.",
                meta={"details": [{"loc": ["body", "region_id"]}]},
            )

            [line] = log_path.read_text(encoding="utf-8").splitlines()
            record = json.loads(line)

        self.assertEqual(record["trace_id"], "trc_test")
        self.assertEqual(record["path"], "/saju/preview")
        self.assertEqual(record["status_code"], 422)
        self.assertEqual(record["selected_parameters"]["birth_date"], "2024-02-10")
        self.assertEqual(record["selected_parameters"]["birth_time"], "10:30")
        self.assertEqual(record["payload"]["birth_date"], "2024-02-10")
        self.assertEqual(record["payload"]["birth_time"], "10:30")
        self.assertEqual(record["error_code"], "INPUT_SCHEMA_ERROR")
        self.assertEqual(
            record["replay_command"],
            "python -m app.tools.replay_saju_request_log --trace-id trc_test",
        )
        self.assertTrue(record["debug_requested"])
        self.assertEqual(record["meta"]["details"][0]["loc"], ["body", "region_id"])

    def test_skips_non_saju_paths_and_disabled_capture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_path = Path(tmp_dir) / "requests.jsonl"
            capture_saju_request_event(
                enabled=True,
                log_path=str(log_path),
                service="suju-insight",
                trace_id="trc_health",
                method="GET",
                path="/health",
                status_code=200,
                payload=None,
                debug_requested=False,
            )
            capture_saju_request_event(
                enabled=False,
                log_path=str(log_path),
                service="suju-insight",
                trace_id="trc_disabled",
                method="POST",
                path="/saju/preview",
                status_code=200,
                payload={},
                debug_requested=False,
            )

            self.assertFalse(log_path.exists())


if __name__ == "__main__":
    unittest.main()
