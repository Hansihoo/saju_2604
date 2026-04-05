from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Query, Request

from app.config import settings
from app.diagnostics import log_stage
from app.domain.saju.adapters import SajuCalculationError
from app.domain.saju.calendar_normalization import CalendarNormalizationError, normalize_calendar
from app.domain.saju.schemas import (
    RegionSearchResponse,
    RegionSuggestion,
    SajuPreviewRequest,
    SajuPreviewResponse,
)
from app.domain.saju.services.mock_preview import (
    build_mock_preview_response,
    find_region_by_id,
    search_regions,
)
from app.domain.saju.services.calculate_saju import calculate_saju
from app.domain.saju.time_correction import TimeCorrectionError, normalize_birth_datetime

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
    region = find_region_by_id(payload.region_id)
    log_stage(
        service=settings.app_name,
        trace_id=request.state.trace_id,
        stage="region_resolution",
        event="resolved",
        meta={"region_id": region.id, "tzid": region.tzid},
    )

    try:
        time_correction = normalize_birth_datetime(
            birth_date=payload.birth_date,
            birth_time=payload.birth_time,
            tzid=region.tzid,
        )
    except TimeCorrectionError as exc:
        log_stage(
            service=settings.app_name,
            trace_id=request.state.trace_id,
            stage="time_correction",
            event="failed",
            error_code=exc.error_code,
            meta=exc.meta,
        )
        raise

    log_stage(
        service=settings.app_name,
        trace_id=request.state.trace_id,
        stage="time_correction",
        event="normalized",
        meta={
            "normalized_utc_datetime": time_correction.normalized_utc_datetime,
            "ambiguous": time_correction.ambiguous,
            "fold": time_correction.fold,
        },
    )

    try:
        calendar_normalization = normalize_calendar(
            calendar_type=payload.calendar_type,
            birth_date=payload.birth_date,
            birth_time=payload.birth_time,
            is_lunar_leap_month=payload.is_lunar_leap_month,
        )
    except CalendarNormalizationError as exc:
        log_stage(
            service=settings.app_name,
            trace_id=request.state.trace_id,
            stage="calendar_normalization",
            event="failed",
            error_code=exc.error_code,
            meta=exc.meta,
        )
        raise

    log_stage(
        service=settings.app_name,
        trace_id=request.state.trace_id,
        stage="calendar_normalization",
        event="normalized",
        meta={
            "normalized_solar_datetime": calendar_normalization.normalized_solar_datetime,
            "normalized_lunar_datetime": calendar_normalization.normalized_lunar_datetime,
        },
    )

    try:
        saju_calculation = calculate_saju(
            calendar_normalization=calendar_normalization,
            gender=payload.gender,
        )
    except SajuCalculationError as exc:
        log_stage(
            service=settings.app_name,
            trace_id=request.state.trace_id,
            stage="saju_calculation",
            event="failed",
            error_code=exc.error_code,
            meta=exc.meta,
        )
        raise

    log_stage(
        service=settings.app_name,
        trace_id=request.state.trace_id,
        stage="saju_calculation",
        event="calculated",
        meta={
            "year_pillar": saju_calculation.pillars["year"].gan_zhi,
            "month_pillar": saju_calculation.pillars["month"].gan_zhi,
            "day_pillar": saju_calculation.pillars["day"].gan_zhi,
            "time_pillar": saju_calculation.pillars["time"].gan_zhi,
        },
    )

    debug_requested = request.state.debug_requested or payload.debug
    return build_mock_preview_response(
        payload=payload,
        region=region,
        time_correction=time_correction,
        calendar_normalization=calendar_normalization,
        saju_calculation=saju_calculation,
        trace_id=request.state.trace_id,
        debug_requested=debug_requested,
    )
