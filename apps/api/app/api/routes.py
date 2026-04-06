from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Query, Request

from app.config import settings
from app.domain.saju.schemas import (
    RegionSearchResponse,
    RegionSuggestion,
    SajuPreviewRequest,
    SajuPreviewResponse,
)
from app.domain.saju.services.preview_orchestrator import create_saju_preview_response
from app.domain.saju.services.region_catalog import search_regions

router = APIRouter()


@router.get("/")
def read_root() -> Dict[str, str]:
    return {
        "service": settings.app_name,
        "message": "suju-insight API is running",
    }


@router.get("/health")
def read_health() -> Dict[str, Any]:
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
    return create_saju_preview_response(
        payload=payload,
        trace_id=request.state.trace_id,
        debug_requested=request.state.debug_requested,
        service_name=settings.app_name,
    )
