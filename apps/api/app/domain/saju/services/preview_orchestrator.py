"""이 파일은 사주 미리보기 파이프라인 전체 순서를 지휘한다."""

from app.config import settings
from app.diagnostics import log_stage
from app.domain.saju.adapters import SajuCalculationError
from app.domain.saju.calendar_normalization import CalendarNormalizationError, normalize_calendar
from app.domain.saju.schemas import SajuPreviewRequest, SajuPreviewResponse
from app.domain.saju.services.analyze_saju import analyze_saju
from app.domain.saju.services.accuracy_mode import resolve_calculation_basis
from app.domain.saju.services.birth_time_policy import resolve_birth_time_policy
from app.domain.saju.services.build_preview_response import build_preview_response
from app.domain.saju.services.calculate_saju import calculate_saju
from app.domain.saju.services.detect_uncertainty import detect_uncertainty
from app.domain.saju.services.generate_candidate_charts import generate_candidate_charts
from app.domain.saju.services.region_catalog import find_region_by_id
from app.domain.saju.time_correction import (
    TimeCorrectionError,
    apply_regional_solar_correction,
    build_birth_time_context,
    calculate_daylight_saving_offset_minutes,
    normalize_birth_datetime,
)


def create_saju_preview_response(
    *,
    payload: SajuPreviewRequest,
    trace_id: str,
    debug_requested: bool,
    service_name: str,
    render_reports: bool = True,
) -> SajuPreviewResponse:
    """사주 미리보기 파이프라인 전단계를 실행하고 최종 응답을 만든다."""
    birth_time_policy = resolve_birth_time_policy(payload)
    region = find_region_by_id(payload.region_id)
    log_stage(
        service=service_name,
        trace_id=trace_id,
        stage="region_resolution",
        event="resolved",
        meta={"region_id": region.id, "tzid": region.tzid},
    )

    try:
        time_correction = normalize_birth_datetime(
            birth_date=payload.birth_date,
            birth_time=birth_time_policy.effective_birth_time,
            tzid=region.tzid,
        )
    except TimeCorrectionError as exc:
        log_stage(
            service=service_name,
            trace_id=trace_id,
            stage="time_correction",
            event="failed",
            error_code=exc.error_code,
            meta=exc.meta,
        )
        raise

    log_stage(
        service=service_name,
        trace_id=trace_id,
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
            birth_time=birth_time_policy.effective_birth_time,
            is_lunar_leap_month=payload.is_lunar_leap_month,
        )
    except CalendarNormalizationError as exc:
        log_stage(
            service=service_name,
            trace_id=trace_id,
            stage="calendar_normalization",
            event="failed",
            error_code=exc.error_code,
            meta=exc.meta,
        )
        raise

    log_stage(
        service=service_name,
        trace_id=trace_id,
        stage="calendar_normalization",
        event="normalized",
        meta={
            "normalized_solar_datetime": calendar_normalization.normalized_solar_datetime,
            "normalized_lunar_datetime": calendar_normalization.normalized_lunar_datetime,
        },
    )

    daylight_saving_offset_minutes = calculate_daylight_saving_offset_minutes(
        tzid=region.tzid,
        offset_minutes=time_correction.offset_minutes,
    )

    try:
        regional_solar_correction = apply_regional_solar_correction(
            normalized_solar_datetime=calendar_normalization.normalized_solar_datetime,
            longitude=region.longitude,
            regional_time_offset_minutes=region.regional_time_offset_minutes,
            daylight_saving_offset_minutes=daylight_saving_offset_minutes,
            correction_basis=region.correction_basis,
        )
    except TimeCorrectionError as exc:
        log_stage(
            service=service_name,
            trace_id=trace_id,
            stage="regional_solar_correction",
            event="failed",
            error_code=exc.error_code,
            meta=exc.meta,
        )
        raise

    log_stage(
        service=service_name,
        trace_id=trace_id,
        stage="regional_solar_correction",
        event="corrected",
        meta={
            "source_solar_datetime": regional_solar_correction.source_solar_datetime,
            "corrected_solar_datetime": regional_solar_correction.corrected_solar_datetime,
            "longitude": regional_solar_correction.longitude,
            "regional_time_offset_minutes": regional_solar_correction.regional_time_offset_minutes,
            "daylight_saving_offset_minutes": regional_solar_correction.daylight_saving_offset_minutes,
        },
    )

    birth_time_context = build_birth_time_context(
        time_correction=time_correction,
        normalized_solar_datetime=calendar_normalization.normalized_solar_datetime,
        regional_solar_correction=regional_solar_correction,
    )
    calculation_basis = resolve_calculation_basis(
        accuracy_mode=payload.accuracy_mode,
        birth_time_context=birth_time_context,
    )

    try:
        saju_calculation = calculate_saju(
            corrected_solar_datetime=calculation_basis.primary_input_datetime_to_lunar_python,
            gender=payload.gender,
            tzid=region.tzid,
            day_pillar_basis_datetime=calculation_basis.primary_day_pillar_basis_datetime,
            use_canonical_year_month_pillars=settings.use_canonical_year_month_pillars,
        )
    except SajuCalculationError as exc:
        log_stage(
            service=service_name,
            trace_id=trace_id,
            stage="saju_calculation",
            event="failed",
            error_code=exc.error_code,
            meta=exc.meta,
        )
        raise

    log_stage(
        service=service_name,
        trace_id=trace_id,
        stage="saju_calculation",
        event="calculated",
        meta={
            "accuracy_mode": calculation_basis.accuracy_mode,
            "primary_time_basis": calculation_basis.primary_time_basis,
            "primary_input_datetime_to_lunar_python": calculation_basis.primary_input_datetime_to_lunar_python,
            "primary_day_pillar_basis_datetime": calculation_basis.primary_day_pillar_basis_datetime,
            "year_pillar": saju_calculation.pillars["year"].gan_zhi,
            "month_pillar": saju_calculation.pillars["month"].gan_zhi,
            "day_pillar": saju_calculation.pillars["day"].gan_zhi,
            "time_pillar": saju_calculation.pillars["time"].gan_zhi,
            "iljin_query_date": saju_calculation.meta.get("iljin_query_date", ""),
            "canonical_year_month_enabled": settings.use_canonical_year_month_pillars,
            "year_pillar_source": saju_calculation.year_month_boundary_context.get(
                "year_pillar_source",
                "",
            ),
            "month_pillar_source": saju_calculation.year_month_boundary_context.get(
                "month_pillar_source",
                "",
            ),
        },
    )

    candidate_charts = (
        []
        if birth_time_policy.is_birth_time_estimated
        else generate_candidate_charts(
            birth_time_context=birth_time_context,
            time_correction=time_correction,
            primary_calculation=saju_calculation,
            gender=payload.gender,
            tzid=region.tzid,
        )
    )
    uncertainty_flags = detect_uncertainty(
        birth_time_policy=birth_time_policy,
        time_correction=time_correction,
        calendar_normalization=calendar_normalization,
        regional_solar_correction=regional_solar_correction,
        birth_time_context=birth_time_context,
        primary_chart=saju_calculation,
        candidate_charts=candidate_charts,
    )
    debug_enabled = debug_requested or payload.debug

    analysis_result = analyze_saju(
        saju_calculation=saju_calculation,
        visible_pillar_keys=birth_time_policy.visible_pillar_keys,
    )
    log_stage(
        service=service_name,
        trace_id=trace_id,
        stage="analysis_engine",
        event="analyzed",
        meta={
            "internal_grade": analysis_result.internal_grade,
            "balance_score": analysis_result.balance_score,
            "missing_elements": ",".join(analysis_result.missing_elements) or "none",
        },
    )

    return build_preview_response(
        payload=payload,
        region=region,
        time_correction=time_correction,
        calendar_normalization=calendar_normalization,
        regional_solar_correction=regional_solar_correction,
        saju_calculation=saju_calculation,
        analysis_result=analysis_result,
        trace_id=trace_id,
        debug_requested=debug_enabled,
        calculation_basis=calculation_basis,
        candidate_charts=candidate_charts,
        uncertainty_flags=uncertainty_flags,
        birth_time_context=birth_time_context,
        render_reports=render_reports,
    )
