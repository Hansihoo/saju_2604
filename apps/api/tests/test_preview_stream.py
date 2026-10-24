import asyncio
import json
import unittest
from threading import Event
from unittest.mock import patch

import httpx

from app.api.preview_stream import preview_events
from app.domain.saju.schemas import SajuPreviewRequest, SajuPreviewResponse
from app.domain.saju.services.preview_orchestrator import create_saju_preview_response
from app.main import app


class PreviewStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_first_signal_and_heartbeat_arrive_before_slow_result_one_call(self):
        release = Event()
        calls = []

        def run(progress):
            calls.append("run")
            progress("calculating")
            progress("writing")
            release.wait(2)
            return {"trace_id": "synthetic"}

        events = preview_events(run, heartbeat_seconds=0.01)
        async def next_stage():
            while True:
                frame = json.loads(await events.__anext__())
                if frame["type"] != "heartbeat":
                    return frame
        try:
            accepted = json.loads(await events.__anext__())
            self.assertEqual(accepted["stage"], "accepted")
            self.assertEqual(calls, [])
            self.assertEqual((await asyncio.wait_for(next_stage(), 2))["stage"], "calculating")
            self.assertEqual((await asyncio.wait_for(next_stage(), 2))["stage"], "writing")
            self.assertEqual(json.loads(await events.__anext__())["type"], "heartbeat")
            self.assertEqual(calls, ["run"])
            release.set()
            frames = [json.loads(frame) async for frame in events]
            self.assertEqual(frames[-1]["type"], "result")
        finally:
            release.set()
            await events.aclose()

    async def test_disconnect_before_worker_starts_never_runs_pipeline(self):
        calls = []
        events = preview_events(lambda progress: calls.append("run"))
        await events.__anext__()
        await events.aclose()
        self.assertEqual(calls, [])

    async def test_disconnect_stops_before_subsequent_phase(self):
        release = Event()
        finished = Event()
        later_calls = []

        def run(progress):
            try:
                progress("calculating")
                release.wait(2)
                progress("writing")
                later_calls.append("generation")
                return {}
            finally:
                finished.set()

        events = preview_events(run, heartbeat_seconds=0.01)
        await events.__anext__()
        while json.loads(await events.__anext__())["type"] == "heartbeat":
            pass
        await events.aclose()
        release.set()
        for _ in range(100):
            if finished.is_set():
                break
            await asyncio.sleep(0.005)
        self.assertTrue(finished.is_set())
        self.assertEqual(later_calls, [])

    async def test_worker_errors_are_terminal_and_do_not_expose_diagnostics(self):
        def run(progress):
            raise RuntimeError("private birth input/provider credentials")
        frames = [json.loads(frame) async for frame in preview_events(run)]
        self.assertEqual([item["type"] for item in frames], ["stage", "error"])
        self.assertEqual(frames[-1]["status"], 500)
        self.assertNotIn("private", json.dumps(frames))

    async def test_fallback_stream_schema_real_milestones_and_legacy_facts(self):
        payload = {"birth_date": "1997-09-18", "birth_time": "14:30", "region_id": "kr-seoul", "locale": "ko"}
        with patch("app.config.settings.llm_provider", "fallback"):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
                headers = {"X-Saju-Verification-Provider": "fallback", "X-Trace-Id": "stream-test"}
                response = await client.post("/saju/preview-stream", json=payload, headers=headers)
                legacy = await client.post("/saju/preview", json=payload, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/x-ndjson", response.headers["content-type"])
        self.assertEqual(response.headers["cache-control"], "private, no-store")
        frames = [json.loads(line) for line in response.text.splitlines()]
        self.assertEqual([item["stage"] for item in frames if item["type"] == "stage"], ["accepted", "calculating", "writing"])
        data = frames[-1]["data"]
        SajuPreviewResponse(**data)
        for field in ("pillars", "signals", "calculation_basis"):
            self.assertEqual(data["result"].get(field), legacy.json()["result"].get(field))

    async def test_verification_guard_rejects_stream_before_work(self):
        with patch("app.config.settings.llm_provider", "openai"), patch("app.api.routes.create_saju_preview_response") as run:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
                response = await client.post("/saju/preview-stream", json={"birth_date": "1997-09-18", "birth_time": "14:30", "region_id": "kr-seoul"}, headers={"X-Saju-Verification-Provider": "fallback"})
        self.assertEqual(response.status_code, 409)
        run.assert_not_called()

    async def test_invalid_input_rejected_before_stream_or_generation(self):
        with patch("app.api.routes.create_saju_preview_response") as run:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
                response = await client.post("/saju/preview-stream", json={"birth_date": "1997-02-31"})
        self.assertEqual(response.status_code, 422)
        run.assert_not_called()

    def test_writing_signal_follows_actual_analysis_and_not_failed_calculation(self):
        phases = []
        payload = SajuPreviewRequest(birth_date="1997-09-18", birth_time="14:30", region_id="kr-seoul")
        with patch("app.domain.saju.services.preview_orchestrator.calculate_saju", side_effect=ValueError("calculation failed")), patch("app.domain.saju.services.preview_orchestrator.build_preview_response") as render:
            with self.assertRaises(ValueError):
                create_saju_preview_response(payload=payload, trace_id="stream-failure", debug_requested=False, service_name="test", on_progress=phases.append)
        self.assertEqual(phases, ["calculating"])
        render.assert_not_called()

    def test_writing_signal_is_not_emitted_when_period_or_interpretation_facts_fail(self):
        phases = []
        payload = SajuPreviewRequest(birth_date="1997-09-18", birth_time="14:30", region_id="kr-seoul")
        with patch("app.domain.saju.services.build_preview_response.build_interpretation_payload", side_effect=ValueError("facts failed")), patch("app.domain.saju.services.build_preview_response._generate_free_preview_safely") as generate:
            with self.assertRaises(ValueError):
                create_saju_preview_response(payload=payload, trace_id="facts-failure", debug_requested=False, service_name="test", report_mode="free_preview", on_progress=phases.append)
        self.assertEqual(phases, ["calculating"])
        generate.assert_not_called()
