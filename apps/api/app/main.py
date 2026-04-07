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
from app.diagnostics import configure_logging, create_trace_id, log_stage, parse_debug_header
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


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError):
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
    detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "trace_id": request.state.trace_id,
            "stage": detail.get("stage", "request"),
            "error_code": detail.get("error_code", "HTTP_ERROR"),
            "message": detail.get("message", "The request failed."),
        },
    )


@app.middleware("http")
async def trace_middleware(request: Request, call_next):
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
