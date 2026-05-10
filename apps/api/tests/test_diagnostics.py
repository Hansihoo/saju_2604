import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from app.diagnostics import capture_saju_request_event
from app.tools.replay_saju_request_log import get_record_payload, select_record


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
        self.assertNotIn("payload", record)
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

    def test_ignores_log_write_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_path = Path(tmp_dir) / "requests.jsonl"
            log_path.mkdir()

            with self.assertLogs("suju-insight", level="WARNING") as logs:
                capture_saju_request_event(
                    enabled=True,
                    log_path=str(log_path),
                    service="suju-insight",
                    trace_id="trc_write_failure",
                    method="POST",
                    path="/saju/preview",
                    status_code=200,
                    payload={"birth_date": "2024-02-10"},
                    debug_requested=False,
                )

        self.assertIn("write_failed", logs.output[0])

    def test_rotates_request_log_when_max_bytes_is_exceeded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_path = Path(tmp_dir) / "requests.jsonl"
            log_path.write_text("old request\n", encoding="utf-8")

            capture_saju_request_event(
                enabled=True,
                log_path=str(log_path),
                service="suju-insight",
                trace_id="trc_rotate",
                method="POST",
                path="/saju/preview",
                status_code=200,
                payload={"birth_date": "2024-02-10", "birth_time": "10:30"},
                debug_requested=False,
                max_bytes=20,
                backup_count=2,
            )

            rotated_path = Path(f"{log_path}.1")
            rotated_text = rotated_path.read_text(encoding="utf-8")
            [line] = log_path.read_text(encoding="utf-8").splitlines()
            record = json.loads(line)

        self.assertEqual(rotated_text, "old request\n")
        self.assertEqual(record["trace_id"], "trc_rotate")
        self.assertEqual(record["selected_parameters"]["birth_time"], "10:30")

    def test_replay_selection_prefers_selected_parameters_and_supports_legacy_payload(self) -> None:
        records = (
            {"path": "/health", "trace_id": "trc_health", "status_code": 200},
            {
                "path": "/saju/preview",
                "trace_id": "trc_old",
                "status_code": 500,
                "payload": {"birth_date": "2024-02-10"},
            },
            {
                "path": "/saju/preview",
                "trace_id": "trc_new",
                "status_code": 400,
                "selected_parameters": {"birth_date": "2025-03-10"},
            },
        )

        selected = select_record(records, trace_id=None, last=False)

        self.assertEqual(selected["trace_id"], "trc_new")
        self.assertEqual(get_record_payload(selected), {"birth_date": "2025-03-10"})
        self.assertEqual(get_record_payload({"payload": {"birth_date": "2024-02-10"}}), {"birth_date": "2024-02-10"})


if __name__ == "__main__":
    unittest.main()
