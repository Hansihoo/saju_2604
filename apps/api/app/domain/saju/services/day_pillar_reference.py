"""Day-pillar reference lookup backed by the checked-in KASI table."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.domain.saju.reference_calendar import lookup_lunar_reference_by_solar_date


@dataclass(frozen=True)
class DayPillarReference:
    gan_zhi: str
    stem: str
    branch: str
    civil_date: str
    day_pillar_basis_date: str
    iljin_query_date: str
    reference_date: str
    source: str
    matched_lunar_python: str
    rule: str = "sect1_23_changes_day"


def get_day_pillar_reference_date(input_dt: datetime, sect: int) -> str:
    if sect == 1 and input_dt.hour >= 23:
        return (input_dt + timedelta(days=1)).date().isoformat()
    return input_dt.date().isoformat()


def resolve_day_pillar_reference(
    *,
    input_dt: datetime,
    sect: int,
    lunar_python_gan_zhi: str,
) -> DayPillarReference:
    reference_date = get_day_pillar_reference_date(input_dt, sect)
    record = lookup_lunar_reference_by_solar_date(date.fromisoformat(reference_date))
    if record is None or len(record.day_ganzhi_hanja) < 2:
        return DayPillarReference(
            gan_zhi=lunar_python_gan_zhi,
            stem=lunar_python_gan_zhi[0] if lunar_python_gan_zhi else "",
            branch=lunar_python_gan_zhi[1] if len(lunar_python_gan_zhi) > 1 else "",
            civil_date=input_dt.date().isoformat(),
            day_pillar_basis_date=reference_date,
            iljin_query_date=reference_date,
            reference_date="",
            source="lunar_python_fallback",
            matched_lunar_python="",
        )

    return DayPillarReference(
        gan_zhi=record.day_ganzhi_hanja,
        stem=record.day_ganzhi_hanja[0],
        branch=record.day_ganzhi_hanja[1],
        civil_date=input_dt.date().isoformat(),
        day_pillar_basis_date=record.solar_date,
        iljin_query_date=record.solar_date,
        reference_date=record.solar_date,
        source="kasi_lunar_reference",
        matched_lunar_python=str(lunar_python_gan_zhi == record.day_ganzhi_hanja).lower(),
    )
