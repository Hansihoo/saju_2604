"""Tokenless basic chart and individually selected factual question endpoints."""

from fastapi import APIRouter, HTTPException, Request, Response

from app.config import settings
from app.diagnostics import capture_saju_request_event, to_json_safe
from app.domain.saju.question_reading import (
    QuestionUnavailable, create_basic_reading, create_question_reading,
)
from app.domain.saju.question_schemas import SajuBasicResponse, SajuQuestionRequest, SajuQuestionResponse
from app.domain.saju.schemas import SajuPreviewRequest
from app.domain.saju.services.preview_orchestrator import create_saju_preview_response


router = APIRouter()


def _record(request, payload, response):
    snapshot = to_json_safe(payload)
    request.state.saju_preview_payload = snapshot
    capture_saju_request_event(
        enabled=settings.request_log_enabled, log_path=settings.request_log_path,
        max_bytes=settings.request_log_max_bytes, backup_count=settings.request_log_backup_count,
        service=settings.app_name, trace_id=request.state.trace_id, method=request.method,
        path=request.url.path, status_code=200, payload=snapshot, debug_requested=False,
        include_input=settings.request_log_include_input, stage="completed",
        meta={"provider": "deterministic", "response_mode": response.response_mode})


def _private(response):
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Pragma"] = "no-cache"


@router.post("/saju/basic", response_model=SajuBasicResponse)
def create_saju_basic(payload: SajuPreviewRequest, request: Request, response: Response):
    _private(response)
    result = create_basic_reading(payload=payload, trace_id=request.state.trace_id,
                                  service_name=settings.app_name, calculate=create_saju_preview_response)
    _record(request, payload, result)
    return result


@router.post("/saju/question", response_model=SajuQuestionResponse)
def create_saju_question(payload: SajuQuestionRequest, request: Request, response: Response):
    _private(response)
    try:
        result = create_question_reading(payload=payload, trace_id=request.state.trace_id,
                                        service_name=settings.app_name, calculate=create_saju_preview_response)
    except QuestionUnavailable as exc:
        raise HTTPException(status_code=409, detail={"error_code": "QUESTION_UNAVAILABLE", "message": str(exc)}) from exc
    _record(request, payload.input, result)
    return result
