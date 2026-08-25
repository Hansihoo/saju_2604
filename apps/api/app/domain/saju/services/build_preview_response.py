"""이 파일은 미리보기 응답을 조립하는 로직을 담는다."""

from dataclasses import asdict
from typing import List, Literal, Optional, Tuple

from app.config import settings
from app.diagnostics import log_stage
from app.domain.saju.analysis import AnalysisResult
from app.domain.saju.calendar_normalization import CalendarNormalizationResult
from app.domain.saju.engine import SajuCalculationResult
from app.domain.saju.interpretation import FreePreviewReport
from app.domain.saju.schemas import (
    BirthTimeContextSummary,
    CalendarNormalizationSummary,
    CandidateChartSummary,
    CalculationBasisSummary,
    DebugCheckpoint,
    DebugTrace,
    EvidenceSection,
    InternalAnalysisDebug,
    PipelineStatus,
    RegionalSolarCorrectionSummary,
    SajuPreviewRequest,
    SajuPreviewResponse,
    SajuPreviewResult,
    SajuResultSignals,
    TimeCorrectionSummary,
    UncertaintyFlagSummary,
)
from app.domain.saju.services.accuracy_mode import CalculationBasis
from app.domain.saju.services.birth_time_policy import resolve_birth_time_policy
from app.domain.saju.services.build_interpretation_payload import build_interpretation_payload
from app.domain.saju.services.build_manse import build_manse_data
from app.domain.saju.services.build_period_flows import build_period_flows
from app.domain.saju.services.detect_uncertainty import UncertaintyFlag
from app.domain.saju.services.generate_free_preview import (
    build_fallback_free_preview_report,
    generate_free_preview_report,
)
from app.domain.saju.services.generate_interpretation import generate_interpretation_report
from app.domain.saju.services.generate_candidate_charts import CandidateChart
from app.domain.saju.localization import localize_ganzhi, localize_ten_god
from app.domain.saju.time_correction import (
    BirthTimeContext,
    RegionalSolarCorrectionResult,
    TimeCorrectionResult,
    build_birth_time_context,
)


SUCCESSFUL_LLM_PROVIDERS = frozenset({"openai", "codex"})
ReportRenderMode = Literal["all", "free_preview", "interpretation", "none"]
PUBLIC_SCORING_FIELDS = (
    "balance_score",
    "charm_score",
    "wealth_score",
    "career_score",
    "leadership_score",
    "internal_grade",
)


def _summarize_visible_pillars(
    saju_calculation: SajuCalculationResult,
    visible_pillar_keys: List[str],
) -> str:
    """표시 대상 기둥 목록 관련 값을 반환하거나 처리한다."""
    return " / ".join(saju_calculation.pillars[key].gan_zhi for key in visible_pillar_keys)


def _build_result_signals(
    *,
    saju_calculation: SajuCalculationResult,
    analysis_result: AnalysisResult,
    visible_pillar_keys: List[str],
) -> SajuResultSignals:
    """결과 신호 목록을 조립한다."""
    return SajuResultSignals(
        visible_pillar_keys=visible_pillar_keys,
        visible_pillar_values=[saju_calculation.pillars[key].gan_zhi for key in visible_pillar_keys],
        dominant_elements=analysis_result.dominant_elements,
        missing_elements=analysis_result.missing_elements,
        balance_score=analysis_result.balance_score,
        charm_score=analysis_result.charm_score,
        wealth_score=analysis_result.wealth_score,
        career_score=analysis_result.career_score,
        leadership_score=analysis_result.leadership_score,
        internal_grade=analysis_result.internal_grade,
    )


def _redact_public_scoring(response: SajuPreviewResponse) -> None:
    """Keep heuristic scores available only while the server assembles internal reports."""
    for field_name in PUBLIC_SCORING_FIELDS:
        setattr(response.result.signals, field_name, None)
        setattr(response.manse.analysis, field_name, None)


def _generate_free_preview_safely(
    *,
    interpretation_payload,
    trace_id: str,
    service_name: str,
) -> Tuple[Optional[FreePreviewReport], str]:
    try:
        free_preview = generate_free_preview_report(
            payload=interpretation_payload,
            trace_id=trace_id,
            service_name=service_name,
        )
        status = "success" if free_preview.provider in SUCCESSFUL_LLM_PROVIDERS else "fallback"
        return free_preview, status
    except Exception as exc:  # pragma: no cover - defensive boundary for preview API resilience.
        log_stage(
            service=service_name,
            trace_id=trace_id,
            stage="free_preview_formatting",
            event="fallback_used",
            error_code=exc.__class__.__name__,
            meta={"reason": "free_preview_exception"},
        )
        try:
            return build_fallback_free_preview_report(interpretation_payload), "fallback"
        except Exception as fallback_exc:  # pragma: no cover - last-resort API resilience.
            log_stage(
                service=service_name,
                trace_id=trace_id,
                stage="free_preview_formatting",
                event="failed",
                error_code=fallback_exc.__class__.__name__,
                meta={"reason": "free_preview_fallback_exception"},
            )
            return None, "failed"


def build_preview_response(
    *,
    payload: SajuPreviewRequest,
    region,
    time_correction: TimeCorrectionResult,
    calendar_normalization: CalendarNormalizationResult,
    regional_solar_correction: RegionalSolarCorrectionResult,
    saju_calculation: SajuCalculationResult,
    analysis_result: AnalysisResult,
    trace_id: str,
    debug_requested: bool,
    calculation_basis: CalculationBasis,
    candidate_charts: Optional[List[CandidateChart]] = None,
    uncertainty_flags: Optional[List[UncertaintyFlag]] = None,
    birth_time_context: Optional[BirthTimeContext] = None,
    report_mode: ReportRenderMode = "all",
) -> SajuPreviewResponse:
    """파이프라인 결과들을 모아 최종 preview API 응답으로 조립한다."""
    birth_time_policy = resolve_birth_time_policy(payload)
    hour_pillar_enabled = birth_time_policy.hour_pillar_enabled
    manse = build_manse_data(
        saju_calculation=saju_calculation,
        analysis_result=analysis_result,
        birth_time_policy=birth_time_policy,
    )
    signals = _build_result_signals(
        saju_calculation=saju_calculation,
        analysis_result=analysis_result,
        visible_pillar_keys=birth_time_policy.visible_pillar_keys,
    )
    visible_pillar_summary = _summarize_visible_pillars(
        saju_calculation=saju_calculation,
        visible_pillar_keys=birth_time_policy.visible_pillar_keys,
    )
    first_luck_cycle = saju_calculation.luck_cycles[0] if saju_calculation.luck_cycles else None
    limitations: List[str] = []
    if payload.is_birth_time_estimated:
        interval = birth_time_policy.birth_time_interval
        interval_text = (
            f"{interval.start} to {interval.end}"
            if interval is not None
            else "the full birth date"
        )
        limitations.append(
            "Birth time is unknown. 00:00 is used only as an internal placeholder, "
            f"and the possible birth-time interval is {interval_text}. "
            "Hour-pillar, luck-cycle, and interval-sensitive outputs should be treated as unconfirmed."
        )
    uncertainty_flag_summaries = [
        UncertaintyFlagSummary(**asdict(flag))
        for flag in (uncertainty_flags or [])
    ]
    uncertainty_summary = [
        flag
        for flag in uncertainty_flag_summaries
        if flag.severity in ("warning", "critical")
    ]
    calculation_basis_summary = CalculationBasisSummary(**asdict(calculation_basis))
    is_placeholder_time = payload.is_birth_time_estimated
    placeholder_reason = "birth_time_unknown" if is_placeholder_time else None

    if payload.locale == "ko":
        preview_overview = f"{region.city} 기준으로 확인된 기둥은 {visible_pillar_summary}입니다."
        preview_love = "관계 해석은 배우자궁과 현재 흐름을 함께 살펴봅니다."
        preview_career = "일 해석은 월주와 십성의 역할 신호를 함께 살펴봅니다."
        preview_wealth = "금전 해석은 재성·식상 신호와 생활 패턴을 함께 살펴봅니다."
        preview_action_advice = "강한 기운은 성과에 쓰고, 약한 기운은 생활 리듬과 환경으로 보완해 보세요."
    else:
        preview_overview = f"Visible pillars for {region.city}: {visible_pillar_summary}."
        preview_love = "Relationship reading considers spouse-house facts and the current flow together."
        preview_career = "Work reading considers the month pillar and Ten-God role signals together."
        preview_wealth = "Wealth reading considers wealth/output signals and practical habits together."
        preview_action_advice = "Use the strong side for results and support weaker elements through routine and environment."

    element_labels = (
        {"wood": "목", "fire": "화", "earth": "토", "metal": "금", "water": "수"}
        if payload.locale == "ko"
        else {"wood": "wood", "fire": "fire", "earth": "earth", "metal": "metal", "water": "water"}
    )
    element_summary = ", ".join(
        f"{element_labels[key]} {analysis_result.visible_element_counts[key]}"
        for key in ("wood", "fire", "earth", "metal", "water")
    )
    localized_ten_gods = {
        key: localize_ten_god(value, payload.locale)
        for key, value in saju_calculation.ten_god_stems.items()
    }
    first_luck_cycle_label = (
        localize_ganzhi(first_luck_cycle.gan_zhi, payload.locale)
        if first_luck_cycle is not None
        else ""
    )

    if payload.locale == "ko":
        evidence_sections = {
            "elements": EvidenceSection(
                title="오행 분포",
                status="ready",
                summary=(
                    f"보이는 사주 기둥 기준 오행 출현 수: {element_summary}."
                    + (
                        " 출생시간을 몰라 시주 오행은 포함하지 않았습니다."
                        if payload.is_birth_time_estimated
                        else ""
                    )
                ),
            ),
            "ten_gods": EvidenceSection(
                title="십성 신호",
                status="ready",
                summary=(
                    "천간에 드러난 십성 신호: "
                    f"연주 {localized_ten_gods['year']}, "
                    f"월주 {localized_ten_gods['month']}, "
                    f"일주 {localized_ten_gods['day']}"
                    + (
                        ". 출생시간을 몰라 시주 십성은 제외했습니다."
                        if payload.is_birth_time_estimated
                        else f", 시주 {localized_ten_gods['time']}."
                    )
                ),
            ),
            "luck_cycles": EvidenceSection(
                title="대운 흐름",
                status="disabled" if not hour_pillar_enabled else "ready",
                summary=(
                    "출생시간을 몰라 시간에 민감한 대운 흐름은 표시하지 않습니다."
                    if not hour_pillar_enabled
                    else (
                        "첫 대운 시작 구간: "
                        f"{first_luck_cycle_label} 대운 ({first_luck_cycle.start_year}~{first_luck_cycle.end_year})."
                        if first_luck_cycle is not None
                        else "대운 자료가 충분하지 않아 큰 흐름만 참고합니다."
                    )
                ),
            ),
        }
    else:
        evidence_sections = {
            "elements": EvidenceSection(
                title="Five Elements",
                status="ready",
                summary=(
                    "Element balance from the calculation: "
                    f"{element_summary}."
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
                    "Stem-level signals: "
                    f"year {localized_ten_gods['year']}, "
                    f"month {localized_ten_gods['month']}, "
                    f"day {localized_ten_gods['day']}"
                    + (
                        ". Time-pillar signals are hidden because the birth time is estimated."
                        if payload.is_birth_time_estimated
                        else f", time {localized_ten_gods['time']}."
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
                        "First cycle: "
                        f"{first_luck_cycle_label} ({first_luck_cycle.start_year}-{first_luck_cycle.end_year})."
                        if first_luck_cycle is not None
                        else "Luck-cycle data is available but shorter than expected."
                    )
                ),
            ),
        }

    preview_result = SajuPreviewResult(
        overview=preview_overview,
        strengths=[
            f"Dominant visible elements: {', '.join(analysis_result.dominant_elements) or 'none'}.",
            analysis_result.strengths[0],
        ],
        cautions=[
            (
                f"Missing visible elements: {', '.join(analysis_result.missing_elements)}."
                if analysis_result.missing_elements
                else "No missing visible elements were detected."
            ),
            analysis_result.cautions[0],
        ],
        love=preview_love,
        career=preview_career,
        wealth=preview_wealth,
        action_advice=preview_action_advice,
        limitations=limitations,
        disabled_sections=birth_time_policy.disabled_sections,
        evidence_sections=evidence_sections,
        calculation_basis=calculation_basis_summary,
        uncertainty_summary=uncertainty_summary,
        hour_pillar_enabled=hour_pillar_enabled,
        signals=signals,
    )
    period_flows = build_period_flows(
        payload=payload,
        region=region,
        saju_calculation=saju_calculation,
    )

    base_response = SajuPreviewResponse(
        trace_id=trace_id,
        pipeline_status=PipelineStatus(
            time_correction="passed",
            calendar_normalization="passed",
            regional_solar_correction="passed",
            saju_calculation="passed",
            analysis_engine="passed",
            llm_formatting="skipped",
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
            is_placeholder_time=is_placeholder_time,
            placeholder_reason=placeholder_reason,
        ),
        regional_solar_correction=RegionalSolarCorrectionSummary(
            source_solar_datetime=regional_solar_correction.source_solar_datetime,
            corrected_solar_datetime=regional_solar_correction.corrected_solar_datetime,
            longitude=regional_solar_correction.longitude,
            regional_time_offset_minutes=regional_solar_correction.regional_time_offset_minutes,
            daylight_saving_offset_minutes=regional_solar_correction.daylight_saving_offset_minutes,
            correction_basis=regional_solar_correction.correction_basis,
            is_placeholder_time=is_placeholder_time,
            placeholder_reason=placeholder_reason,
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
            is_placeholder_time=is_placeholder_time,
            placeholder_reason=placeholder_reason,
        ),
        manse=manse,
        period_flows=period_flows,
        result=preview_result,
        debug_trace=None,
    )
    if report_mode == "none":
        return base_response

    interpretation_payload = build_interpretation_payload(request=payload, response=base_response)
    free_preview = None
    free_preview_status = "skipped"
    if report_mode in {"all", "free_preview"}:
        free_preview, free_preview_status = _generate_free_preview_safely(
            interpretation_payload=interpretation_payload,
            trace_id=trace_id,
            service_name=settings.app_name,
        )

    interpretation = None
    llm_status = "skipped"
    if report_mode in {"all", "interpretation"}:
        interpretation = generate_interpretation_report(
            payload=interpretation_payload,
            trace_id=trace_id,
            service_name=settings.app_name,
        )
        llm_status = "passed" if interpretation.provider in SUCCESSFUL_LLM_PROVIDERS else "failed"

    overview_text = preview_result.overview
    if interpretation is not None:
        overview_text = interpretation.summary.headline.strip()
        if interpretation.summary.overview.strip():
            overview_text = f"{overview_text} {interpretation.summary.overview}".strip()

    result = SajuPreviewResult(
        overview=overview_text,
        strengths=preview_result.strengths,
        cautions=preview_result.cautions,
        love=preview_result.love,
        career=preview_result.career,
        wealth=preview_result.wealth,
        action_advice=preview_result.action_advice,
        interpretation=interpretation,
        free_preview=free_preview,
        limitations=limitations,
        disabled_sections=birth_time_policy.disabled_sections,
        evidence_sections=evidence_sections,
        calculation_basis=calculation_basis_summary,
        uncertainty_summary=uncertainty_summary,
        hour_pillar_enabled=hour_pillar_enabled,
        signals=signals,
    )

    debug_trace = None
    if debug_requested:
        resolved_birth_time_context = birth_time_context or build_birth_time_context(
            time_correction=time_correction,
            normalized_solar_datetime=calendar_normalization.normalized_solar_datetime,
            regional_solar_correction=regional_solar_correction,
        )
        birth_time_context = BirthTimeContextSummary(
            **asdict(resolved_birth_time_context)
        )
        candidate_chart_summaries = [
            CandidateChartSummary(**asdict(candidate_chart))
            for candidate_chart in (candidate_charts or [])
        ]
        llm_note = "Structured interpretation was deferred."
        llm_error_code = None
        if interpretation is not None:
            llm_note = (
                "Structured interpretation finished via "
                f"{interpretation.provider}."
                + (
                    f" Fallback reason: {interpretation.diagnostics.fallback_reason}."
                    if interpretation.provider == "fallback" and interpretation.diagnostics
                    else f" Model {interpretation.model}."
                )
            )
            llm_error_code = (
                interpretation.diagnostics.fallback_reason
                if interpretation.provider == "fallback" and interpretation.diagnostics
                else None
            )
        free_preview_note = "Free preview was not requested."
        free_preview_error_code = None
        if free_preview is not None:
            free_preview_note = (
                "Free preview finished via "
                f"{free_preview.provider}."
                + (
                    f" Fallback reason: {free_preview.diagnostics.fallback_reason}."
                    if (
                        free_preview.provider == "fallback"
                        and free_preview.diagnostics
                        and free_preview.diagnostics.fallback_reason
                    )
                    else ""
                )
            )
            free_preview_error_code = (
                free_preview.diagnostics.fallback_reason
                if free_preview.provider == "fallback" and free_preview.diagnostics
                else "free_preview_failed" if free_preview_status == "failed" else None
            )
        debug_trace = DebugTrace(
            stage_order=[
                "input_validation",
                "region_resolution",
                "time_correction",
                "calendar_normalization",
                "regional_solar_correction",
                "saju_calculation",
                "analysis_engine",
                "llm_formatting",
                "free_preview_formatting",
            ],
            failed_stage=(
                "llm_formatting"
                if llm_status == "failed"
                else "free_preview_formatting"
                if free_preview_status in {"fallback", "failed"}
                else None
            ),
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
                    stage="regional_solar_correction",
                    status="passed",
                    note=(
                        f"Applied {regional_solar_correction.regional_time_offset_minutes} minutes"
                        f" and DST {regional_solar_correction.daylight_saving_offset_minutes} minutes "
                        f"at longitude {regional_solar_correction.longitude} -> "
                        f"{regional_solar_correction.corrected_solar_datetime}"
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
                        f"balance {analysis_result.balance_score}/100"
                    ),
                ),
                DebugCheckpoint(
                    stage="llm_formatting",
                    status=llm_status,
                    note=llm_note,
                    error_code=llm_error_code,
                ),
                DebugCheckpoint(
                    stage="free_preview_formatting",
                    status=(
                        "passed"
                        if free_preview_status == "success"
                        else "failed" if free_preview_status in {"fallback", "failed"} else "skipped"
                    ),
                    note=free_preview_note,
                    error_code=free_preview_error_code,
                ),
            ],
            request_echo={
                "calendar_type": payload.calendar_type,
                "birth_date": payload.birth_date.isoformat(),
                "birth_time": payload.birth_time,
                "gender": payload.gender,
                "region_id": payload.region_id,
                "accuracy_mode": payload.accuracy_mode,
                "trace_id": trace_id,
            },
            accuracy_mode=payload.accuracy_mode,
            internal_analysis=InternalAnalysisDebug(
                balance_score=analysis_result.balance_score,
                charm_score=analysis_result.charm_score,
                wealth_score=analysis_result.wealth_score,
                career_score=analysis_result.career_score,
                leadership_score=analysis_result.leadership_score,
                internal_grade=analysis_result.internal_grade,
            ),
            calculation_basis=calculation_basis_summary,
            birth_time_context=birth_time_context,
            year_month_boundary_context=saju_calculation.year_month_boundary_context,
            candidate_charts=candidate_chart_summaries,
            uncertainty_flags=uncertainty_flag_summaries,
        )

    base_response.pipeline_status = PipelineStatus(
        time_correction="passed",
        calendar_normalization="passed",
        regional_solar_correction="passed",
        saju_calculation="passed",
        analysis_engine="passed",
        llm_formatting=llm_status,
        free_preview_formatting=free_preview_status,
    )
    base_response.result = result
    base_response.debug_trace = debug_trace
    _redact_public_scoring(base_response)
    return base_response
