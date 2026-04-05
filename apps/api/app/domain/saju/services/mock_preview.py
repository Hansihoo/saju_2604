from typing import Dict, List

from fastapi import HTTPException

from app.domain.saju.mock_data import REGION_OPTIONS
from app.domain.saju.schemas import (
    DebugCheckpoint,
    DebugTrace,
    EvidenceSection,
    PipelineStatus,
    RegionSuggestion,
    SajuPreviewRequest,
    SajuPreviewResponse,
    SajuPreviewResult,
)


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
            "error_code": "REGION_NOT_SELECTED",
            "message": "A valid region must be selected from the suggestion list.",
        },
    )


def build_mock_preview_response(
    *,
    payload: SajuPreviewRequest,
    region: RegionSuggestion,
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
            "It verifies the input contract, trace flow, and result layout before the real engine is connected."
        ),
        strengths=[
            "The current flow already preserves calendar type, birth time, gender, and region selection in one contract.",
            "The response shape is stable enough to connect the real engine without rewriting the UI later.",
        ],
        cautions=[
            "This response is a mock preview, not a real saju calculation.",
            "Time correction, calendar normalization, and the calculation engine are still scheduled for later phases.",
        ],
        love="Relationship guidance will be generated after the analysis engine is connected.",
        career="Career fit will be based on code-driven scoring, then translated into natural language.",
        wealth="Wealth analysis will stay conservative and evidence-based rather than exaggerated.",
        action_advice="Use this sprint to validate the contract, region selection flow, and debug trace before real calculation work starts.",
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
                    status="skipped",
                    note="Skipped in mock preview mode.",
                ),
                DebugCheckpoint(
                    stage="calendar_normalization",
                    status="skipped",
                    note="Skipped in mock preview mode.",
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
                "gender": payload.gender,
                "region_id": payload.region_id,
                "tzid": region.tzid,
            },
        )

    return SajuPreviewResponse(
        trace_id=trace_id,
        pipeline_status=PipelineStatus(),
        region=region,
        result=result,
        debug_trace=debug_trace,
    )
