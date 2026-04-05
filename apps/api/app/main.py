from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings
from app.diagnostics import configure_logging, create_trace_id, log_stage, parse_debug_header

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
