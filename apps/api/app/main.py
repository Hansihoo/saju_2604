"""이 파일은 FastAPI app을 생성하고 공통 미들웨어와 예외 처리기를 등록한다."""

from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import router
from app.config import settings
from app.domain.saju.adapters import SajuCalculationError
from app.domain.saju.calendar_normalization import CalendarNormalizationError
from app.diagnostics import (
    capture_saju_request_event,
    configure_logging,
    create_trace_id,
    log_stage,
    parse_debug_header,
)
from app.domain.saju.time_correction import TimeCorrectionError

app = FastAPI(
    title=settings.app_name,
    version=settings.api_version,
    summary="Saju web service backend bootstrap",
)

configure_logging(settings.log_level)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _capture_failed_saju_request(
    *,
    request: Request,
    status_code: int,
    stage: str,
    error_code: str,
    message: str,
    payload=None,
    meta=None,
) -> None:
    capture_saju_request_event(
        enabled=settings.request_log_enabled,
        log_path=settings.request_log_path,
        max_bytes=settings.request_log_max_bytes,
        backup_count=settings.request_log_backup_count,
        service=settings.app_name,
        trace_id=getattr(request.state, "trace_id", "unknown"),
        method=request.method,
        path=request.url.path,
        status_code=status_code,
        payload=payload if payload is not None else getattr(request.state, "saju_preview_payload", None),
        debug_requested=getattr(request.state, "debug_requested", False),
        stage=stage,
        error_code=error_code,
        message=message,
        meta=meta,
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError):
    """Return a structured response for request schema validation failures."""
    _capture_failed_saju_request(
        request=request,
        status_code=422,
        stage="input_validation",
        error_code="INPUT_SCHEMA_ERROR",
        message="Request validation failed.",
        payload=getattr(exc, "body", None),
        meta={"details": exc.errors()},
    )
    return JSONResponse(
        status_code=422,
        content={
            "trace_id": request.state.trace_id,
            "stage": "input_validation",
            "error_code": "INPUT_SCHEMA_ERROR",
            "message": "Request validation failed.",
            "details": exc.errors(),
        },
    )


@app.exception_handler(TimeCorrectionError)
async def handle_time_correction_error(request: Request, exc: TimeCorrectionError):
    """Return a structured response for time-correction failures."""
    _capture_failed_saju_request(
        request=request,
        status_code=400,
        stage=exc.stage,
        error_code=exc.error_code,
        message=exc.message,
        meta=exc.meta,
    )
    return JSONResponse(
        status_code=400,
        content={
            "trace_id": request.state.trace_id,
            "stage": exc.stage,
            "error_code": exc.error_code,
            "message": exc.message,
            "meta": exc.meta if request.state.debug_requested else {},
        },
    )


@app.exception_handler(CalendarNormalizationError)
async def handle_calendar_normalization_error(request: Request, exc: CalendarNormalizationError):
    """Return a structured response for calendar-normalization failures."""
    _capture_failed_saju_request(
        request=request,
        status_code=400,
        stage="calendar_normalization",
        error_code=exc.error_code,
        message=exc.message,
        meta=exc.meta,
    )
    return JSONResponse(
        status_code=400,
        content={
            "trace_id": request.state.trace_id,
            "stage": "calendar_normalization",
            "error_code": exc.error_code,
            "message": exc.message,
            "meta": exc.meta if request.state.debug_requested else {},
        },
    )


@app.exception_handler(SajuCalculationError)
async def handle_saju_calculation_error(request: Request, exc: SajuCalculationError):
    """Return a structured response for saju calculation failures."""
    _capture_failed_saju_request(
        request=request,
        status_code=400,
        stage="saju_calculation",
        error_code=exc.error_code,
        message=exc.message,
        meta=exc.meta,
    )
    return JSONResponse(
        status_code=400,
        content={
            "trace_id": request.state.trace_id,
            "stage": "saju_calculation",
            "error_code": exc.error_code,
            "message": exc.message,
            "meta": exc.meta if request.state.debug_requested else {},
        },
    )


@app.exception_handler(StarletteHTTPException)
async def handle_http_exception(request: Request, exc: StarletteHTTPException):
    """Return a structured response for general HTTP exceptions."""
    detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
    _capture_failed_saju_request(
        request=request,
        status_code=exc.status_code,
        stage=detail.get("stage", "request"),
        error_code=detail.get("error_code", "HTTP_ERROR"),
        message=detail.get("message", "The request failed."),
        meta={"detail": detail},
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "trace_id": request.state.trace_id,
            "stage": detail.get("stage", "request"),
            "error_code": detail.get("error_code", "HTTP_ERROR"),
            "message": detail.get("message", "The request failed."),
        },
    )


@app.exception_handler(Exception)
async def handle_unexpected_exception(request: Request, exc: Exception):
    """Return a structured response for unexpected server errors."""
    _capture_failed_saju_request(
        request=request,
        status_code=500,
        stage="request",
        error_code="INTERNAL_SERVER_ERROR",
        message="Unexpected server error.",
        meta={"error_type": type(exc).__name__},
    )
    return JSONResponse(
        status_code=500,
        content={
            "trace_id": request.state.trace_id,
            "stage": "request",
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "Unexpected server error.",
        },
    )


@app.middleware("http")
async def trace_middleware(request: Request, call_next):
    """각 요청에 trace 정보를 부여하고 처리 결과를 로깅한다."""
    started_at = perf_counter()
    trace_id = request.headers.get("X-Trace-Id") or create_trace_id()
    request.state.trace_id = trace_id
    request.state.debug_requested = settings.debug_enabled or parse_debug_header(
        request.headers.get("X-Saju-Debug")
    )

    response = await call_next(request)
    duration_ms = int((perf_counter() - started_at) * 1000)
    response.headers["X-Trace-Id"] = trace_id

    log_stage(
        service=settings.app_name,
        trace_id=trace_id,
        stage="request",
        event=f"{request.method} {request.url.path}",
        duration_ms=duration_ms,
        meta={"debug_requested": request.state.debug_requested},
    )
    return response


app.include_router(router)
