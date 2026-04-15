"""이 파일은 골든 케이스 스냅샷을 조립하는 로직을 담는다."""

from __future__ import annotations

from typing import Dict

from app.config import settings
from app.domain.saju.golden import (
    GOLDEN_SPECIAL_STAR_ORDER,
    PILLAR_SORT_ORDER,
    GoldenBasicInfo,
    GoldenCaseInput,
    GoldenLuckCycleHeader,
    GoldenLuckCycleRow,
    GoldenPillarRow,
    GoldenSpecialStarRow,
    GoldenSnapshot,
    PILLAR_LABEL_BY_KEY,
    apply_display_time_correction,
    calculate_daylight_saving_correction,
    derive_display_minutes_from_longitude,
    format_datetime_minute,
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


def _normalize_special_star_key(value: str) -> str | None:
    """특수 신살 key를 정규화한다."""
    for key, _label in GOLDEN_SPECIAL_STAR_ORDER:
        if value == key or value.startswith(f"{key}-"):
            return key
    return None


def _build_pillar_table(response) -> Dict[str, GoldenPillarRow]:
    """기둥 표을 조립한다."""
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


def _collapse_special_stars(response) -> list[GoldenSpecialStarRow]:
    """특수 신살 목록을 합친다."""
    collapsed: Dict[str, set[str]] = {key: set() for key, _label in GOLDEN_SPECIAL_STAR_ORDER}
    active_flags: Dict[str, bool] = {key: False for key, _label in GOLDEN_SPECIAL_STAR_ORDER}

    for star in response.manse.special_stars:
        root_key = _normalize_special_star_key(star.key)
        if root_key not in collapsed:
            continue
        active_flags[root_key] = active_flags[root_key] or star.active
        for match in star.matches:
            collapsed[root_key].add(match.pillar_key)

    return [
        GoldenSpecialStarRow(
            key=key,
            label=label,
            active=active_flags[key],
            matched_pillars=sorted(collapsed[key], key=lambda item: PILLAR_SORT_ORDER[item]),
        )
        for key, label in GOLDEN_SPECIAL_STAR_ORDER
    ]


def build_actual_golden_snapshot(*, case_input: GoldenCaseInput) -> GoldenSnapshot:
    """actual 골든 케이스 스냅샷을 조립한다."""
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
    regional_offset_minutes = derive_display_minutes_from_longitude(response.region.longitude)

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
        luck_cycle_header=GoldenLuckCycleHeader(
            start_age=response.manse.luck_cycles[0].start_age if response.manse.luck_cycles else 0,
            reference_pillar=to_korean_gan_zhi(response.manse.pillars.month.gan_zhi or ""),
        ),
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
        special_stars=_collapse_special_stars(response),
    )
