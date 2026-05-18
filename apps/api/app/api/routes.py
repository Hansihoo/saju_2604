"""이 파일은 HTTP endpoint를 정의하고 service 계층으로 요청을 전달한다."""

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Query, Request

from app.config import settings
from app.diagnostics import capture_saju_request_event, to_json_safe
from app.domain.saju.schemas import (
    RegionSearchResponse,
    RegionSuggestion,
    SajuFreeDetailResponse,
    SajuPreviewRequest,
    SajuPreviewResponse,
)
from app.domain.saju.services.preview_orchestrator import create_saju_preview_response
from app.domain.saju.services.region_catalog import search_regions

router = APIRouter()


def _request_method(request: Request) -> str:
    return getattr(request, "method", "POST")


def _request_path(request: Request) -> str:
    request_url = getattr(request, "url", None)
    return getattr(request_url, "path", "/saju/preview")


def _is_http_request(request: Request) -> bool:
    return hasattr(request, "method") and hasattr(request, "url")


@router.get("/")
def read_root() -> Dict[str, str]:
    """루트 경로에서 API 기본 정보를 반환한다."""
    return {
        "service": settings.app_name,
        "message": "suju-insight API is running",
    }


@router.get("/health")
def read_health() -> Dict[str, Any]:
    """헬스 체크에 사용할 서비스 상태 정보를 반환한다."""
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.api_version,
        "message": "suju-insight API bootstrap is ready.",
        "focus": ["contracts", "trace", "time-correction", "calendar-normalization", "saju-engine"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/regions/search", response_model=RegionSearchResponse)
def search_regions_endpoint(
    request: Request,
    q: str = Query(default="", min_length=0),
    limit: int = Query(default=5, ge=1, le=10),
) -> RegionSearchResponse:
    """검색어에 맞는 지역 후보를 API 응답으로 반환한다."""
    items = [RegionSuggestion(**region) for region in search_regions(query=q, limit=limit)]
    return RegionSearchResponse(
        trace_id=request.state.trace_id,
        items=items,
        total=len(items),
    )


@router.post("/saju/preview", response_model=SajuPreviewResponse)
def create_saju_preview(
    payload: SajuPreviewRequest,
    request: Request,
) -> SajuPreviewResponse:
    """사주 미리보기 요청을 받아 파이프라인을 실행한다."""
    payload_snapshot = to_json_safe(payload)
    request.state.saju_preview_payload = payload_snapshot
    response = create_saju_preview_response(
        payload=payload,
        trace_id=request.state.trace_id,
        debug_requested=request.state.debug_requested,
        service_name=settings.app_name,
    )
    if _is_http_request(request):
        capture_saju_request_event(
            enabled=settings.request_log_enabled,
            log_path=settings.request_log_path,
            max_bytes=settings.request_log_max_bytes,
            backup_count=settings.request_log_backup_count,
            service=settings.app_name,
            trace_id=request.state.trace_id,
            method=_request_method(request),
            path=_request_path(request),
            status_code=200,
            payload=payload_snapshot,
            debug_requested=request.state.debug_requested,
            stage="completed",
            meta={"pipeline_status": response.pipeline_status},
        )
    return response


@router.post("/saju/free-detail", response_model=SajuFreeDetailResponse)
def create_saju_free_detail(
    payload: SajuPreviewRequest,
    request: Request,
) -> SajuFreeDetailResponse:
    """Return the free detailed interpretation as a lazy-loadable report."""
    payload_snapshot = to_json_safe(payload)
    request.state.saju_preview_payload = payload_snapshot
    preview_response = create_saju_preview_response(
        payload=payload,
        trace_id=request.state.trace_id,
        debug_requested=request.state.debug_requested,
        service_name=settings.app_name,
    )
    interpretation = preview_response.result.interpretation
    if interpretation is None:  # pragma: no cover - defensive guard; generator returns fallback on LLM failure.
        raise RuntimeError("free detail interpretation was not generated")

    response = SajuFreeDetailResponse(
        trace_id=preview_response.trace_id,
        pipeline_status=preview_response.pipeline_status,
        interpretation=interpretation,
        detail_report=interpretation,
        debug_trace=preview_response.debug_trace,
    )
    if _is_http_request(request):
        capture_saju_request_event(
            enabled=settings.request_log_enabled,
            log_path=settings.request_log_path,
            max_bytes=settings.request_log_max_bytes,
            backup_count=settings.request_log_backup_count,
            service=settings.app_name,
            trace_id=request.state.trace_id,
            method=_request_method(request),
            path=_request_path(request),
            status_code=200,
            payload=payload_snapshot,
            debug_requested=request.state.debug_requested,
            stage="completed",
            meta={"pipeline_status": response.pipeline_status},
        )
    return response
