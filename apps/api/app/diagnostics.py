"""이 파일은 요청 trace와 구조화된 로깅 도구를 제공한다."""

import json
import logging
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
