import json
import logging
from typing import Any, Dict, Optional
from uuid import uuid4


def configure_logging(log_level: str) -> None:
    logging.basicConfig(level=getattr(logging, log_level.upper(), logging.INFO))


def create_trace_id() -> str:
    return f"trc_{uuid4().hex[:12]}"


def parse_debug_header(value: Optional[str]) -> bool:
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
