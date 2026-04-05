from typing import Dict, List

from fastapi import HTTPException

from app.domain.saju.calendar_normalization import CalendarNormalizationResult
from app.domain.saju.mock_data import REGION_OPTIONS
from app.domain.saju.schemas import (
    CalendarNormalizationSummary,
    DebugCheckpoint,
    DebugTrace,
    EvidenceSection,
    PipelineStatus,
    RegionSuggestion,
    SajuPreviewRequest,
    SajuPreviewResponse,
    SajuPreviewResult,
    TimeCorrectionSummary,
)
from app.domain.saju.time_correction import TimeCorrectionResult


def search_regions(*, query: str, limit: int) -> List[Dict[str, str]]:
    normalized = query.strip().lower()
    if not normalized:
        return REGION_OPTIONS[:limit]

    starts_with: List[Dict[str, str]] = []
    contains: List[Dict[str, str]] = []
    for region in REGION_OPTIONS:
        haystack = " ".join(
            [
                region["display_name"],
                region["country"],
                region["city"],
                region["tzid"],
            ]
        ).lower()
        if region["city"].lower().startswith(normalized) or region["display_name"].lower().startswith(normalized):
            starts_with.append(region)
        elif normalized in haystack:
            contains.append(region)

    return (starts_with + contains)[:limit]


def find_region_by_id(region_id: str) -> RegionSuggestion:
    for region in REGION_OPTIONS:
        if region["id"] == region_id:
            return RegionSuggestion(**region)

    raise HTTPException(
        status_code=400,
        detail={
            "stage": "region_resolution",
            "error_code": "REGION_NOT_SELECTED",
            "message": "A valid region must be selected from the suggestion list.",
        },
    )


def build_mock_preview_response(
    *,
    payload: SajuPreviewRequest,
    region: RegionSuggestion,
    time_correction: TimeCorrectionResult,
    calendar_normalization: CalendarNormalizationResult,
    trace_id: str,
    debug_requested: bool,
) -> SajuPreviewResponse:
    hour_pillar_enabled = not payload.is_birth_time_estimated
    limitations: List[str] = []
    if payload.is_birth_time_estimated:
        limitations.append(
            "Birth time is estimated. Hour-pillar-dependent sections will stay limited until the real time is known."
        )

    evidence_sections = {
        "elements": EvidenceSection(
            title="Five Elements",
            status="coming_soon",
            summary="The element balance will be unlocked after the real calculation engine is connected.",
        ),
        "ten_gods": EvidenceSection(
            title="Ten Gods",
            status="coming_soon",
            summary="This section is reserved for normalized Ten Gods output from the engine adapter.",
        ),
        "luck_cycles": EvidenceSection(
            title="Luck Cycles",
            status="disabled" if not hour_pillar_enabled else "coming_soon",
            summary=(
                "Luck-cycle details are hidden because the birth time is estimated."
                if not hour_pillar_enabled
                else "This section will show decade luck-cycle details after engine integration."
            ),
        ),
    }

    result = SajuPreviewResult(
        overview=(
            f"This preview uses mock reading data for {region.city}. "
            "It verifies the input contract, region lookup, time correction, calendar normalization, and result layout before the real engine is connected."
        ),
        strengths=[
            "The current flow preserves calendar type, leap-month intent, region selection, and normalized time context in one contract.",
            "The response shape is stable enough to connect the real engine without rewriting the UI later.",
        ],
        cautions=[
            "This response is a mock preview, not a real saju calculation.",
            "The actual saju engine and analysis engine are still scheduled for later phases.",
        ],
        love="Relationship guidance will be generated after the analysis engine is connected.",
        career="Career fit will be based on code-driven scoring, then translated into natural language.",
        wealth="Wealth analysis will stay conservative and evidence-based rather than exaggerated.",
        action_advice="Use this sprint to validate region lookup, time correction, lunar/solar normalization, and the trace flow before real calculation work starts.",
        limitations=limitations,
        evidence_sections=evidence_sections,
        hour_pillar_enabled=hour_pillar_enabled,
    )

    debug_trace = None
    if debug_requested:
        debug_trace = DebugTrace(
            stage_order=[
                "input_validation",
                "region_resolution",
                "time_correction",
                "calendar_normalization",
                "saju_calculation",
                "analysis_engine",
                "llm_formatting",
            ],
            checkpoints=[
                DebugCheckpoint(stage="input_validation", status="passed"),
                DebugCheckpoint(
                    stage="region_resolution",
                    status="passed",
                    note=f"Resolved {region.display_name} -> {region.tzid}",
                ),
                DebugCheckpoint(
                    stage="time_correction",
                    status="passed",
                    note=(
                        f"Normalized {time_correction.source_local_datetime} "
                        f"to {time_correction.normalized_utc_datetime}"
                    ),
                ),
                DebugCheckpoint(
                    stage="calendar_normalization",
                    status="passed",
                    note=(
                        f"Solar {calendar_normalization.normalized_solar_datetime} / "
                        f"Lunar {calendar_normalization.normalized_lunar_datetime}"
                    ),
                ),
                DebugCheckpoint(
                    stage="saju_calculation",
                    status="skipped",
                    note="The real engine adapter is not connected in this sprint.",
                ),
                DebugCheckpoint(
                    stage="analysis_engine",
                    status="skipped",
                    note="The analysis engine is scheduled for a later sprint.",
                ),
                DebugCheckpoint(
                    stage="llm_formatting",
                    status="skipped",
                    note="The LLM formatter is scheduled for a later sprint.",
                ),
            ],
            request_echo={
                "calendar_type": payload.calendar_type,
                "birth_date": payload.birth_date.isoformat(),
                "birth_time": payload.birth_time,
                "is_lunar_leap_month": str(payload.is_lunar_leap_month).lower(),
                "gender": payload.gender,
                "region_id": payload.region_id,
                "tzid": region.tzid,
                "normalized_local_datetime": time_correction.normalized_local_datetime,
                "normalized_utc_datetime": time_correction.normalized_utc_datetime,
                "normalized_solar_datetime": calendar_normalization.normalized_solar_datetime,
                "normalized_lunar_datetime": calendar_normalization.normalized_lunar_datetime,
            },
        )

    return SajuPreviewResponse(
        trace_id=trace_id,
        pipeline_status=PipelineStatus(
            time_correction="passed",
            calendar_normalization="passed",
        ),
        region=region,
        time_correction=TimeCorrectionSummary(
            tzid=time_correction.tzid,
            source_local_datetime=time_correction.source_local_datetime,
            normalized_local_datetime=time_correction.normalized_local_datetime,
            normalized_utc_datetime=time_correction.normalized_utc_datetime,
            offset_minutes=time_correction.offset_minutes,
            ambiguous=time_correction.ambiguous,
            fold=time_correction.fold,
        ),
        calendar_normalization=CalendarNormalizationSummary(
            calendar_type=calendar_normalization.calendar_type,
            is_lunar_leap_month=calendar_normalization.is_lunar_leap_month,
            input_date=calendar_normalization.input_date,
            input_time=calendar_normalization.input_time,
            normalized_solar_datetime=calendar_normalization.normalized_solar_datetime,
            normalized_lunar_datetime=calendar_normalization.normalized_lunar_datetime,
            solar_year=calendar_normalization.solar_year,
            solar_month=calendar_normalization.solar_month,
            solar_day=calendar_normalization.solar_day,
            solar_hour=calendar_normalization.solar_hour,
            solar_minute=calendar_normalization.solar_minute,
            lunar_year=calendar_normalization.lunar_year,
            lunar_month=calendar_normalization.lunar_month,
            lunar_day=calendar_normalization.lunar_day,
        ),
        result=result,
        debug_trace=debug_trace,
    )
