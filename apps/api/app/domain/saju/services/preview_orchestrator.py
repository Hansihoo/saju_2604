from app.diagnostics import log_stage
from app.domain.saju.adapters import SajuCalculationError
from app.domain.saju.calendar_normalization import CalendarNormalizationError, normalize_calendar
from app.domain.saju.schemas import SajuPreviewRequest, SajuPreviewResponse
from app.domain.saju.services.analyze_saju import analyze_saju
from app.domain.saju.services.birth_time_policy import resolve_birth_time_policy
from app.domain.saju.services.build_preview_response import build_preview_response
from app.domain.saju.services.calculate_saju import calculate_saju
from app.domain.saju.services.region_catalog import find_region_by_id
from app.domain.saju.time_correction import (
    TimeCorrectionError,
    apply_regional_solar_correction,
    calculate_daylight_saving_offset_minutes,
    normalize_birth_datetime,
)


def create_saju_preview_response(
    *,
    payload: SajuPreviewRequest,
    trace_id: str,
    debug_requested: bool,
    service_name: str,
) -> SajuPreviewResponse:
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
            birth_time=payload.birth_time,
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
            birth_time=payload.birth_time,
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

    try:
        saju_calculation = calculate_saju(
            corrected_solar_datetime=regional_solar_correction.corrected_solar_datetime,
            gender=payload.gender,
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
            "year_pillar": saju_calculation.pillars["year"].gan_zhi,
            "month_pillar": saju_calculation.pillars["month"].gan_zhi,
            "day_pillar": saju_calculation.pillars["day"].gan_zhi,
            "time_pillar": saju_calculation.pillars["time"].gan_zhi,
        },
    )

    birth_time_policy = resolve_birth_time_policy(payload)
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
        debug_requested=debug_requested or payload.debug,
    )
