"""이 파일은 요청 trace와 구조화된 로깅 도구를 제공한다."""

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4


def configure_logging(log_level: str) -> None:
    """로깅을 설정한다."""
    logging.basicConfig(level=getattr(logging, log_level.upper(), logging.INFO))


def create_trace_id() -> str:
    """trace ID을 생성한다."""
    return f"trc_{uuid4().hex[:12]}"


def parse_debug_header(value: Optional[str]) -> bool:
    """디버그 header를 파싱한다."""
    return value in {"1", "true", "TRUE", "yes", "YES"}


def log_stage(
    *,
    service: str,
    trace_id: str,
    stage: str,
    event: str,
    level: int = logging.INFO,
    duration_ms: Optional[int] = None,
    error_code: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    """stage 관련 값을 반환하거나 처리한다."""
    logging.getLogger(service).log(
        level,
        json.dumps(
            {
                "service": service,
                "trace_id": trace_id,
                "stage": stage,
                "event": event,
                "duration_ms": duration_ms,
                "error_code": error_code,
                "meta": meta or {},
            },
            ensure_ascii=True,
        ),
    )


def to_json_safe(value: Any) -> Any:
    """Convert common runtime objects into JSON-safe values for diagnostics."""
    if hasattr(value, "model_dump"):
        return to_json_safe(value.model_dump(mode="json"))
    if hasattr(value, "dict"):
        return to_json_safe(value.dict())
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): to_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_json_safe(item) for item in value]
    return value


def capture_saju_request_event(
    *,
    enabled: bool,
    log_path: str,
    service: str,
    trace_id: str,
    method: str,
    path: str,
    status_code: int,
    payload: Any,
    debug_requested: bool,
    stage: Optional[str] = None,
    error_code: Optional[str] = None,
    message: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    """Append a structured saju request snapshot for local reproduction."""
    if not enabled or path.rstrip("/") != "/saju/preview":
        return

    target = Path(log_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    selected_parameters = to_json_safe(payload)
    record = {
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "service": service,
        "trace_id": trace_id,
        "method": method,
        "path": path,
        "status_code": status_code,
        "stage": stage,
        "error_code": error_code,
        "message": message,
        "debug_requested": debug_requested,
        "selected_parameters": selected_parameters,
        "payload": selected_parameters,
        "meta": to_json_safe(meta or {}),
        "replay_command": f"python -m app.tools.replay_saju_request_log --trace-id {trace_id}",
    }
    with target.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")
