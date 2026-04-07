from __future__ import annotations

from typing import Dict

from app.config import settings
from app.domain.saju.golden import (
    GoldenBasicInfo,
    GoldenCaseInput,
    GoldenLuckCycleRow,
    GoldenPillarRow,
    GoldenSnapshot,
    PILLAR_LABEL_BY_KEY,
    apply_display_time_correction,
    calculate_daylight_saving_correction,
    format_datetime_minute,
    round_display_minutes,
    to_korean_branch,
    to_korean_gan_zhi,
    to_korean_stem,
)
from app.domain.saju.schemas import SajuPreviewRequest
from app.domain.saju.services.preview_orchestrator import create_saju_preview_response


GENDER_LABELS = {
    "male": "남자",
    "female": "여자",
}


def _build_pillar_table(response) -> Dict[str, GoldenPillarRow]:
    pillar_table: Dict[str, GoldenPillarRow] = {}
    for key in ["year", "month", "day", "time"]:
        pillar = getattr(response.manse.pillars, key)
        pillar_table[key] = GoldenPillarRow(
            key=key,
            label=PILLAR_LABEL_BY_KEY[key],
            gan_zhi=to_korean_gan_zhi(pillar.gan_zhi or ""),
            stem=to_korean_stem(pillar.stem or ""),
            stem_ten_god=pillar.stem_ten_god or "",
            branch=to_korean_branch(pillar.branch or ""),
            branch_ten_god=pillar.branch_ten_god or "",
            hidden_stems=[to_korean_stem(stem) for stem in pillar.hidden_stems],
            twelve_fortune=pillar.twelve_fortune or "",
            twelve_shinsal=pillar.twelve_shinsal or "",
        )
    return pillar_table


def build_actual_golden_snapshot(*, case_input: GoldenCaseInput) -> GoldenSnapshot:
    payload = SajuPreviewRequest(
        calendar_type=case_input.calendar_type,
        birth_date=case_input.birth_date,
        birth_time=case_input.birth_time,
        is_birth_time_estimated=False,
        is_lunar_leap_month=case_input.is_lunar_leap_month,
        gender=case_input.gender,
        region_id=case_input.region_id,
        debug=True,
    )
    response = create_saju_preview_response(
        payload=payload,
        trace_id=f"golden-{case_input.case_id}",
        debug_requested=True,
        service_name=settings.app_name,
    )

    daylight_saving_offset_minutes = calculate_daylight_saving_correction(
        tzid=response.region.tzid,
        offset_minutes=response.time_correction.offset_minutes,
    )
    solar_birth_datetime = format_datetime_minute(response.calendar_normalization.normalized_solar_datetime)
    regional_offset_minutes = round_display_minutes(response.region.regional_time_offset_minutes)

    return GoldenSnapshot(
        basic_info=GoldenBasicInfo(
            solar_birth_datetime=solar_birth_datetime,
            lunar_birth_datetime=format_datetime_minute(response.calendar_normalization.normalized_lunar_datetime),
            gender_label=GENDER_LABELS[case_input.gender],
            birth_place=response.region.city,
            corrected_datetime=apply_display_time_correction(
                solar_birth_datetime=solar_birth_datetime,
                regional_time_offset_minutes=regional_offset_minutes,
                daylight_saving_offset_minutes=daylight_saving_offset_minutes,
            ),
            regional_time_offset_minutes=regional_offset_minutes,
            daylight_saving_offset_minutes=daylight_saving_offset_minutes,
        ),
        pillar_table=_build_pillar_table(response),
        luck_cycles=[
            GoldenLuckCycleRow(
                start_age=cycle.start_age,
                gan_zhi=to_korean_gan_zhi(cycle.gan_zhi),
                stem=to_korean_stem(cycle.gan_zhi),
                branch=to_korean_branch(cycle.gan_zhi),
            )
            for cycle in response.manse.luck_cycles
            if to_korean_gan_zhi(cycle.gan_zhi)
        ],
    )
