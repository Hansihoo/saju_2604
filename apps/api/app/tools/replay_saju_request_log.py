"""Replay a captured /saju/preview request from the local JSONL request log."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from pydantic import ValidationError

from app.config import settings
from app.domain.saju.adapters import SajuCalculationError
from app.domain.saju.calendar_normalization import CalendarNormalizationError
from app.domain.saju.schemas import SajuPreviewRequest
from app.domain.saju.services.preview_orchestrator import create_saju_preview_response
from app.domain.saju.time_correction import TimeCorrectionError


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _model_dump_json(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return json.loads(model.json())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay a captured saju preview request.")
    parser.add_argument("--trace-id", help="Replay the latest log entry matching this trace id.")
    parser.add_argument("--log-path", default=settings.request_log_path)
    parser.add_argument(
        "--last",
        action="store_true",
        help="Replay the latest saju preview request instead of the latest failed request.",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Use the configured LLM provider during replay. Defaults to fallback formatting.",
    )
    return parser.parse_args()


def iter_records(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Request log does not exist: {path}")

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        yield json.loads(line)


def select_record(records: Iterable[Dict[str, Any]], *, trace_id: Optional[str], last: bool) -> Dict[str, Any]:
    candidates = [record for record in records if record.get("path") == "/saju/preview"]
    if trace_id:
        candidates = [record for record in candidates if record.get("trace_id") == trace_id]
    elif not last:
        candidates = [record for record in candidates if int(record.get("status_code") or 0) >= 400]

    if not candidates:
        raise LookupError("No matching saju preview request log entry found.")
    return candidates[-1]


def main() -> None:
    args = parse_args()
    record = select_record(
        iter_records(Path(args.log_path)),
        trace_id=args.trace_id,
        last=args.last,
    )

    if not args.use_llm:
        from app.domain.saju.services import generate_interpretation

        generate_interpretation.settings.llm_provider = "fallback"

    try:
        payload = SajuPreviewRequest(**(record.get("payload") or {}))
    except ValidationError as exc:
        print(
            json.dumps(
                {
                    "trace_id": record.get("trace_id"),
                    "status": "validation_error",
                    "payload": record.get("payload"),
                    "errors": exc.errors(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    try:
        response = create_saju_preview_response(
            payload=payload,
            trace_id=f"replay-{record.get('trace_id', 'unknown')}",
            debug_requested=True,
            service_name=settings.app_name,
        )
    except TimeCorrectionError as exc:
        print_error(record, stage=exc.stage, error_code=exc.error_code, message=exc.message, meta=exc.meta)
        return
    except CalendarNormalizationError as exc:
        print_error(
            record,
            stage="calendar_normalization",
            error_code=exc.error_code,
            message=exc.message,
            meta=exc.meta,
        )
        return
    except SajuCalculationError as exc:
        print_error(
            record,
            stage="saju_calculation",
            error_code=exc.error_code,
            message=exc.message,
            meta=exc.meta,
        )
        return
    except Exception as exc:
        print_error(
            record,
            stage="request",
            error_code="INTERNAL_SERVER_ERROR",
            message="Unexpected server error.",
            meta={"error_type": type(exc).__name__},
        )
        return
    print(
        json.dumps(
            {
                "source_trace_id": record.get("trace_id"),
                "replayed_status": "ok",
                "response": _model_dump_json(response),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def print_error(
    record: Dict[str, Any],
    *,
    stage: str,
    error_code: str,
    message: str,
    meta: Dict[str, Any],
) -> None:
    print(
        json.dumps(
            {
                "source_trace_id": record.get("trace_id"),
                "replayed_status": "error",
                "stage": stage,
                "error_code": error_code,
                "message": message,
                "payload": record.get("payload"),
                "meta": meta,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
