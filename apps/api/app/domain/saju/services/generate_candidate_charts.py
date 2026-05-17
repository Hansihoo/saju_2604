"""Generate debug-only candidate charts for alternate birth-time bases."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from lunar_python import Solar

from app.domain.saju.engine import Gender, SajuCalculationResult
from app.domain.saju.services.calculate_luck_cycles import calculate_luck_cycles
from app.domain.saju.services.day_pillar_reference import (
    get_day_pillar_reference_date,
    resolve_day_pillar_reference,
)
from app.domain.saju.time_correction import (
    BirthTimeContext,
    STANDARD_OFFSET_BY_TZ,
    TimeCorrectionResult,
    calculate_daylight_saving_offset_minutes,
)

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python 3.8 fallback
    from backports.zoneinfo import ZoneInfo


@dataclass
class CandidateChartDifference:
    primary: Optional[str]
    candidate: Optional[str]


@dataclass
class CandidateChart:
    candidate_id: str
    time_basis: str
    midnight_rule: str
    input_datetime_to_lunar_python: str
    day_pillar_basis_datetime: str
    iljin_query_date: str
    day_pillar_rule: str
    year_pillar: str
    month_pillar: str
    day_pillar: str
    hour_pillar: str
    luck_cycle_start_age: Optional[int]
    luck_cycle_start_age_years: Optional[int]
    luck_cycle_start_age_months: Optional[int]
    luck_cycle_start_age_total_months: Optional[int]
    luck_cycle_first_ganzhi: Optional[str]
    differences_from_primary: Dict[str, CandidateChartDifference]
    aliases: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class _CandidateSpec:
    candidate_id: str
    time_basis: str
    midnight_rule: str
    input_datetime: str
    day_pillar_basis_datetime: str
    sect: int


def _parse_solar_datetime(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def _format_solar_datetime(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _calculate_candidate(
    *,
    spec: _CandidateSpec,
    gender: Gender,
    tzid: str,
    primary_calculation: SajuCalculationResult,
) -> CandidateChart:
    dt = _parse_solar_datetime(spec.input_datetime)
    day_pillar_lookup_dt = _parse_solar_datetime(spec.day_pillar_basis_datetime)
    day_time_dt = (
        day_pillar_lookup_dt
        if get_day_pillar_reference_date(day_pillar_lookup_dt, spec.sect)
        != get_day_pillar_reference_date(dt, spec.sect)
        else dt
    )
    solar = Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
    eight_char = solar.getLunar().getEightChar()
    eight_char.setSect(spec.sect)
    day_time_solar = Solar.fromYmdHms(
        day_time_dt.year,
        day_time_dt.month,
        day_time_dt.day,
        day_time_dt.hour,
        day_time_dt.minute,
        day_time_dt.second,
    )
    day_time_eight_char = day_time_solar.getLunar().getEightChar()
    day_time_eight_char.setSect(spec.sect)

    year_pillar = eight_char.getYear()
    month_pillar = eight_char.getMonth()
    day_reference = resolve_day_pillar_reference(
        input_dt=day_pillar_lookup_dt,
        sect=spec.sect,
        lunar_python_gan_zhi=day_time_eight_char.getDay(),
    )
    day_pillar = day_reference.gan_zhi
    hour_pillar = day_time_eight_char.getTime()
    luck_cycles = calculate_luck_cycles(
        gender=gender,
        normalized_birth_dt=dt,
        year_pillar=year_pillar,
        month_pillar=month_pillar,
        day_pillar=day_pillar,
        cycle_count=10,
        target_standard_offset_minutes=STANDARD_OFFSET_BY_TZ.get(tzid),
        timezone_id=tzid,
    )
    first_luck_cycle = luck_cycles[0] if luck_cycles else None
    luck_cycle_start_age = first_luck_cycle.start_age if first_luck_cycle else None
    luck_cycle_start_age_years = first_luck_cycle.start_age_years if first_luck_cycle else None
    luck_cycle_start_age_months = first_luck_cycle.start_age_months if first_luck_cycle else None
    luck_cycle_start_age_total_months = (
        first_luck_cycle.start_age_total_months if first_luck_cycle else None
    )
    luck_cycle_first_ganzhi = first_luck_cycle.gan_zhi if first_luck_cycle else None

    return CandidateChart(
        candidate_id=spec.candidate_id,
        time_basis=spec.time_basis,
        midnight_rule=spec.midnight_rule,
        input_datetime_to_lunar_python=spec.input_datetime,
        day_pillar_basis_datetime=spec.day_pillar_basis_datetime,
        iljin_query_date=day_reference.iljin_query_date,
        day_pillar_rule=day_reference.rule,
        year_pillar=year_pillar,
        month_pillar=month_pillar,
        day_pillar=day_pillar,
        hour_pillar=hour_pillar,
        luck_cycle_start_age=luck_cycle_start_age,
        luck_cycle_start_age_years=luck_cycle_start_age_years,
        luck_cycle_start_age_months=luck_cycle_start_age_months,
        luck_cycle_start_age_total_months=luck_cycle_start_age_total_months,
        luck_cycle_first_ganzhi=luck_cycle_first_ganzhi,
        differences_from_primary=_compare_to_primary(
            primary_calculation=primary_calculation,
            year_pillar=year_pillar,
            month_pillar=month_pillar,
            day_pillar=day_pillar,
            hour_pillar=hour_pillar,
            luck_cycle_start_age=luck_cycle_start_age,
            luck_cycle_start_age_total_months=luck_cycle_start_age_total_months,
            luck_cycle_first_ganzhi=luck_cycle_first_ganzhi,
        ),
    )


def _compare_to_primary(
    *,
    primary_calculation: SajuCalculationResult,
    year_pillar: str,
    month_pillar: str,
    day_pillar: str,
    hour_pillar: str,
    luck_cycle_start_age: Optional[int],
    luck_cycle_start_age_total_months: Optional[int],
    luck_cycle_first_ganzhi: Optional[str],
) -> Dict[str, CandidateChartDifference]:
    primary_first_luck = primary_calculation.luck_cycles[0] if primary_calculation.luck_cycles else None
    comparisons = {
        "year_pillar": (
            primary_calculation.pillars["year"].gan_zhi,
            year_pillar,
        ),
        "month_pillar": (
            primary_calculation.pillars["month"].gan_zhi,
            month_pillar,
        ),
        "day_pillar": (
            primary_calculation.pillars["day"].gan_zhi,
            day_pillar,
        ),
        "hour_pillar": (
            primary_calculation.pillars["time"].gan_zhi,
            hour_pillar,
        ),
        "luck_cycle_start_age": (
            str(primary_first_luck.start_age) if primary_first_luck else None,
            str(luck_cycle_start_age) if luck_cycle_start_age is not None else None,
        ),
        "luck_cycle_start_age_total_months": (
            str(primary_first_luck.start_age_total_months) if primary_first_luck else None,
            str(luck_cycle_start_age_total_months)
            if luck_cycle_start_age_total_months is not None
            else None,
        ),
        "luck_cycle_first_ganzhi": (
            primary_first_luck.gan_zhi if primary_first_luck else None,
            luck_cycle_first_ganzhi,
        ),
    }
    return {
        key: CandidateChartDifference(primary=primary_value, candidate=candidate_value)
        for key, (primary_value, candidate_value) in comparisons.items()
        if primary_value != candidate_value
    }


def _dedupe_key(candidate: CandidateChart) -> Tuple[str, str, str, str, Optional[int], Optional[str]]:
    return (
        candidate.year_pillar,
        candidate.month_pillar,
        candidate.day_pillar,
        candidate.hour_pillar,
        candidate.luck_cycle_start_age_total_months,
        candidate.luck_cycle_first_ganzhi,
    )


def _dedupe_candidates(candidates: Iterable[CandidateChart]) -> List[CandidateChart]:
    unique: Dict[Tuple[str, str, str, str, Optional[int], Optional[str]], CandidateChart] = {}
    ordered: List[CandidateChart] = []
    for candidate in candidates:
        key = _dedupe_key(candidate)
        existing = unique.get(key)
        if existing is None:
            unique[key] = candidate
            ordered.append(candidate)
            continue
        existing.aliases.append(candidate.candidate_id)
        for alias in candidate.aliases:
            if alias not in existing.aliases:
                existing.aliases.append(alias)
    return ordered


def _build_fold_specs(
    *,
    time_correction: TimeCorrectionResult,
    birth_time_context: BirthTimeContext,
) -> List[_CandidateSpec]:
    if not time_correction.ambiguous:
        return []

    naive_local = datetime.fromisoformat(time_correction.source_local_datetime)
    zone = ZoneInfo(time_correction.tzid)
    specs: List[_CandidateSpec] = []
    source_solar_datetime = _parse_solar_datetime(birth_time_context.normalized_solar_datetime)
    for fold in (0, 1):
        aware_local = naive_local.replace(tzinfo=zone, fold=fold)
        roundtrip = aware_local.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)
        if roundtrip != naive_local:
            continue
        utcoffset = aware_local.utcoffset()
        offset_minutes = int((utcoffset.total_seconds() if utcoffset else 0) // 60)
        daylight_saving_offset_minutes = calculate_daylight_saving_offset_minutes(
            tzid=time_correction.tzid,
            offset_minutes=offset_minutes,
        )
        corrected_dt = source_solar_datetime + timedelta(
            seconds=int(
                round(
                    (
                        birth_time_context.regional_time_offset_minutes
                        + daylight_saving_offset_minutes
                    )
                    * 60
                )
            )
        )
        specs.append(
            _CandidateSpec(
                candidate_id=f"fold_{fold}",
                time_basis=f"fold_{fold}",
                midnight_rule="sect1_23_changes_day",
                input_datetime=_format_solar_datetime(corrected_dt),
                day_pillar_basis_datetime=birth_time_context.normalized_solar_datetime,
                sect=1,
            )
        )
    return specs


def generate_candidate_charts(
    *,
    birth_time_context: BirthTimeContext,
    time_correction: TimeCorrectionResult,
    primary_calculation: SajuCalculationResult,
    gender: Gender,
    tzid: str,
) -> List[CandidateChart]:
    """Return debug-only candidate charts without mutating the primary result."""
    specs: List[_CandidateSpec] = [
        _CandidateSpec(
            candidate_id="legacy_corrected",
            time_basis="legacy_corrected",
            midnight_rule="sect1_23_changes_day",
            input_datetime=birth_time_context.legacy_corrected_solar_datetime,
            day_pillar_basis_datetime=birth_time_context.normalized_solar_datetime,
            sect=1,
        ),
        _CandidateSpec(
            candidate_id="standard_local",
            time_basis="standard_local",
            midnight_rule="sect1_23_changes_day",
            input_datetime=birth_time_context.standard_local_datetime,
            day_pillar_basis_datetime=birth_time_context.standard_local_datetime,
            sect=1,
        ),
        _CandidateSpec(
            candidate_id="mean_solar",
            time_basis="mean_solar",
            midnight_rule="sect1_23_changes_day",
            input_datetime=birth_time_context.mean_solar_datetime,
            day_pillar_basis_datetime=birth_time_context.mean_solar_datetime,
            sect=1,
        ),
        _CandidateSpec(
            candidate_id="sect1_23_changes_day",
            time_basis="standard_local",
            midnight_rule="sect1_23_changes_day",
            input_datetime=birth_time_context.standard_local_datetime,
            day_pillar_basis_datetime=birth_time_context.standard_local_datetime,
            sect=1,
        ),
        _CandidateSpec(
            candidate_id="sect2_00_changes_day",
            time_basis="standard_local",
            midnight_rule="sect2_00_changes_day",
            input_datetime=birth_time_context.standard_local_datetime,
            day_pillar_basis_datetime=birth_time_context.standard_local_datetime,
            sect=2,
        ),
    ]
    specs.extend(
        _build_fold_specs(
            time_correction=time_correction,
            birth_time_context=birth_time_context,
        )
    )

    candidates = [
        _calculate_candidate(
            spec=spec,
            gender=gender,
            tzid=tzid,
            primary_calculation=primary_calculation,
        )
        for spec in specs
    ]
    return _dedupe_candidates(candidates)
