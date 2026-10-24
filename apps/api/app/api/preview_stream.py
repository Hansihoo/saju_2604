"""Request-scoped progress; no stored jobs, birth-data URLs or extra inference."""

import asyncio
import json
from contextlib import suppress
from threading import Event
from typing import Any, AsyncIterator, Callable, Dict

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from starlette.concurrency import run_in_threadpool

from app.domain.saju.adapters import SajuCalculationError
from app.domain.saju.calendar_normalization import CalendarNormalizationError
from app.domain.saju.time_correction import TimeCorrectionError

PROGRESS_VERSION = "saju-preview-progress-v1"
HEARTBEAT_SECONDS = 10


class PreviewStreamClosed(Exception):
    """Stop at the next pipeline boundary after the client disconnects."""


def _line(frame: Dict[str, Any]) -> str:
    return json.dumps({"version": PROGRESS_VERSION, **frame}, ensure_ascii=False) + "\n"


def _error_frame(exc: Exception) -> Dict[str, Any]:
    # Raw exception messages/metadata may contain input or provider diagnostics.
    if isinstance(exc, (TimeCorrectionError, CalendarNormalizationError, SajuCalculationError)):
        return {"type": "error", "status": 400, "error": {"error_code": exc.error_code}}
    if isinstance(exc, HTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        return {"type": "error", "status": exc.status_code,
                "error": {"error_code": detail.get("error_code", "REQUEST_FAILED")}}
    return {"type": "error", "status": 500, "error": {"error_code": "INTERNAL_SERVER_ERROR"}}


async def preview_events(
    run: Callable[[Callable[[str], None]], Any],
    *,
    heartbeat_seconds: float = HEARTBEAT_SECONDS,
) -> AsyncIterator[str]:
    """Use the existing bounded Starlette thread pool for one pipeline call.

    A heartbeat confirms this response is connected, not model token progress.
    Already-running synchronous provider calls retain their existing timeout;
    disconnecting cannot forcibly interrupt them. No subsequent phase is started.
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    closed = Event()

    def emit(frame: Dict[str, Any]) -> None:
        if closed.is_set():
            raise PreviewStreamClosed()
        loop.call_soon_threadsafe(queue.put_nowait, frame)

    def progress(stage: str) -> None:
        if stage not in {"calculating", "writing"}:
            raise ValueError("Unknown preview progress stage")
        emit({"type": "stage", "stage": stage})

    def work() -> None:
        try:
            if closed.is_set():
                return
            response = run(progress)
            emit({"type": "result", "data": jsonable_encoder(response, exclude_none=True)})
        except PreviewStreamClosed:
            return
        except Exception as exc:
            if not closed.is_set():
                with suppress(PreviewStreamClosed):
                    emit(_error_frame(exc))

    # Accepted is sent before a slow worker/LLM can hold up the first byte.
    worker = None
    try:
        yield _line({"type": "stage", "stage": "accepted"})
        worker = asyncio.create_task(run_in_threadpool(work))
        while True:
            try:
                frame = await asyncio.wait_for(queue.get(), timeout=heartbeat_seconds)
            except asyncio.TimeoutError:
                yield _line({"type": "heartbeat"})
                continue
            yield _line(frame)
            if frame["type"] in {"result", "error"}:
                break
    finally:
        closed.set()
        if worker is not None:
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker
