from typing import Dict, List

from fastapi import HTTPException

from app.domain.saju.analysis import AnalysisResult
from app.domain.saju.calendar_normalization import CalendarNormalizationResult
from app.domain.saju.engine import SajuCalculationResult
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
from app.domain.saju.services.birth_time_policy import resolve_birth_time_policy
from app.domain.saju.time_correction import TimeCorrectionResult


def _summarize_visible_pillars(
    saju_calculation: SajuCalculationResult,
    visible_pillar_keys: List[str],
) -> str:
    return " / ".join(saju_calculation.pillars[key].gan_zhi for key in visible_pillar_keys)


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
    saju_calculation: SajuCalculationResult,
    analysis_result: AnalysisResult,
    trace_id: str,
    debug_requested: bool,
) -> SajuPreviewResponse:
    birth_time_policy = resolve_birth_time_policy(payload)
    hour_pillar_enabled = birth_time_policy.hour_pillar_enabled
    visible_pillar_summary = _summarize_visible_pillars(
        saju_calculation=saju_calculation,
        visible_pillar_keys=birth_time_policy.visible_pillar_keys,
    )
    limitations: List[str] = []
    if payload.is_birth_time_estimated:
        limitations.append(
            "Birth time is estimated, so the pipeline calculates with 00:00 internally and hides hour-pillar-dependent output until the real time is known."
        )

    evidence_sections = {
        "elements": EvidenceSection(
            title="Five Elements",
            status="ready",
            summary=(
                "Element balance from the engine: "
                f"wood {analysis_result.visible_element_counts['wood']}, "
                f"fire {analysis_result.visible_element_counts['fire']}, "
                f"earth {analysis_result.visible_element_counts['earth']}, "
                f"metal {analysis_result.visible_element_counts['metal']}, "
                f"water {analysis_result.visible_element_counts['water']}."
                + (
                    " Hour-pillar contribution is hidden because the birth time is estimated."
                    if payload.is_birth_time_estimated
                    else ""
                )
            ),
        ),
        "ten_gods": EvidenceSection(
            title="Ten Gods",
            status="ready",
            summary=(
                "Stem-level Ten Gods from the engine: "
                f"year {saju_calculation.ten_god_stems['year']}, "
                f"month {saju_calculation.ten_god_stems['month']}, "
                f"day {saju_calculation.ten_god_stems['day']}"
                + (
                    ". Time-pillar Ten Gods are hidden because the birth time is estimated."
                    if payload.is_birth_time_estimated
                    else f", time {saju_calculation.ten_god_stems['time']}."
                )
            ),
        ),
        "luck_cycles": EvidenceSection(
            title="Luck Cycles",
            status="disabled" if not hour_pillar_enabled else "ready",
            summary=(
                "Luck-cycle details are hidden because the birth time is estimated."
                if not hour_pillar_enabled
                else (
                    "First active decade cycle: "
                    f"{saju_calculation.luck_cycles[1].gan_zhi} "
                    f"({saju_calculation.luck_cycles[1].start_year}-{saju_calculation.luck_cycles[1].end_year})."
                    if len(saju_calculation.luck_cycles) > 1
                    else "Luck-cycle data is available but shorter than expected."
                )
            ),
        ),
    }

    result = SajuPreviewResult(
        overview=(
            f"This preview uses a real saju calculation core for {region.city}, "
            f"with visible pillars {visible_pillar_summary}. "
            f"{'The hour pillar is hidden because the birth time is estimated. ' if payload.is_birth_time_estimated else ''}"
            "The analysis engine and LLM phrasing are still mock layers."
        ),
        strengths=[
            "The current flow preserves calendar type, leap-month intent, region selection, normalized time context, real saju pillar output, and deterministic baseline analysis in one contract.",
            analysis_result.strengths[0],
        ],
        cautions=[
            "This response now uses a real saju calculation engine and a deterministic baseline analysis, but the final narrative layer is still provisional.",
            analysis_result.cautions[0],
        ],
        love=f"Baseline attraction profile score: {analysis_result.charm_score}/100. Narrative refinement will come after the LLM layer is connected.",
        career=f"Baseline career fit score: {analysis_result.career_score}/100, derived from the current visible element profile.",
        wealth=f"Baseline wealth score: {analysis_result.wealth_score}/100. This stays conservative and rule-based at this stage.",
        action_advice=analysis_result.action_advice,
        limitations=limitations,
        disabled_sections=birth_time_policy.disabled_sections,
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
                    status="passed",
                    note=(
                        f"Calculated visible pillars {visible_pillar_summary}"
                        + (
                            " with the time pillar hidden by policy."
                            if payload.is_birth_time_estimated
                            else ""
                        )
                    ),
                ),
                DebugCheckpoint(
                    stage="analysis_engine",
                    status="passed",
                    note=(
                        f"Internal grade {analysis_result.internal_grade}, "
                        f"balance {analysis_result.balance_score}, "
                        f"missing elements {', '.join(analysis_result.missing_elements) or 'none'}"
                    ),
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
                "effective_birth_time": birth_time_policy.effective_birth_time,
                "is_birth_time_estimated": str(payload.is_birth_time_estimated).lower(),
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
            saju_calculation="passed",
            analysis_engine="passed",
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
