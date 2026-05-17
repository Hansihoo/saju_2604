"""Detect uncertainty flags from deterministic saju calculation candidates."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from lunar_python import Solar

from app.domain.saju.calendar_normalization import CalendarNormalizationResult
from app.domain.saju.engine import SajuCalculationResult
from app.domain.saju.services.birth_time_policy import BirthTimePolicyResult
from app.domain.saju.services.day_pillar_reference import resolve_day_pillar_reference
from app.domain.saju.services.generate_candidate_charts import CandidateChart
from app.domain.saju.services.solar_term_boundaries import (
    SolarTermBoundary,
    find_jie_inside_interval,
    nearest_solar_term_boundary,
)
from app.domain.saju.time_correction import (
    BirthTimeContext,
    RegionalSolarCorrectionResult,
    TimeCorrectionResult,
)


Severity = str
CRITICAL_FIELDS = {"year_pillar", "month_pillar", "day_pillar"}
WARNING_FIELDS = {
    "hour_pillar",
    "luck_cycle_start_age",
    "luck_cycle_start_age_total_months",
    "luck_cycle_first_ganzhi",
}
NEAR_MIDNIGHT_THRESHOLD_MINUTES = 60
NEAR_SOLAR_TERM_INFO_MINUTES = 24 * 60
NEAR_SOLAR_TERM_WARNING_MINUTES = 120
NEAR_SOLAR_TERM_CRITICAL_MINUTES = 30
IPCHUN_TERM_NAMES = {"\u7acb\u6625", "\uc785\ucd98"}


@dataclass
class UncertaintyFlag:
    code: str
    severity: Severity
    affected_fields: List[str]
    user_message: str
    developer_message: str
    evidence: Dict[str, Any] = field(default_factory=dict)


def _candidate_ids(candidate: CandidateChart) -> Set[str]:
    return {candidate.candidate_id, *candidate.aliases}


def _find_candidate(candidates: Sequence[CandidateChart], candidate_id: str) -> Optional[CandidateChart]:
    for candidate in candidates:
        if candidate_id in _candidate_ids(candidate):
            return candidate
    return None


def _changed_fields(candidates: Iterable[CandidateChart]) -> Set[str]:
    fields: Set[str] = set()
    for candidate in candidates:
        fields.update(candidate.differences_from_primary.keys())
    return fields


def _candidate_evidence(candidate: CandidateChart) -> Dict[str, Any]:
    return {
        "candidate_id": candidate.candidate_id,
        "aliases": list(candidate.aliases),
        "time_basis": candidate.time_basis,
        "midnight_rule": candidate.midnight_rule,
        "input_datetime_to_lunar_python": candidate.input_datetime_to_lunar_python,
        "day_pillar_basis_datetime": candidate.day_pillar_basis_datetime,
        "iljin_query_date": candidate.iljin_query_date,
        "day_pillar_rule": candidate.day_pillar_rule,
        "year_pillar": candidate.year_pillar,
        "month_pillar": candidate.month_pillar,
        "day_pillar": candidate.day_pillar,
        "hour_pillar": candidate.hour_pillar,
        "luck_cycle_start_age": candidate.luck_cycle_start_age,
        "luck_cycle_start_age_years": candidate.luck_cycle_start_age_years,
        "luck_cycle_start_age_months": candidate.luck_cycle_start_age_months,
        "luck_cycle_start_age_total_months": candidate.luck_cycle_start_age_total_months,
        "luck_cycle_first_ganzhi": candidate.luck_cycle_first_ganzhi,
    }


def _compare_candidates(
    first: Optional[CandidateChart],
    second: Optional[CandidateChart],
    fields: Sequence[str],
) -> Set[str]:
    if first is None or second is None:
        return set()

    changed: Set[str] = set()
    for field_name in fields:
        if getattr(first, field_name) != getattr(second, field_name):
            changed.add(field_name)
    return changed


def _is_near_midnight(datetime_text: str) -> bool:
    value = datetime.strptime(datetime_text, "%Y-%m-%d %H:%M:%S")
    minutes = value.hour * 60 + value.minute + (1 if value.second else 0)
    return (
        minutes <= NEAR_MIDNIGHT_THRESHOLD_MINUTES
        or minutes >= (24 * 60) - NEAR_MIDNIGHT_THRESHOLD_MINUTES
    )


def _severity_from_fields(fields: Iterable[str]) -> Severity:
    field_set = set(fields)
    if field_set & CRITICAL_FIELDS:
        return "critical"
    if field_set & WARNING_FIELDS:
        return "warning"
    return "info"


def _primary_pillar_evidence(primary_chart: SajuCalculationResult) -> Dict[str, Any]:
    first_luck = primary_chart.luck_cycles[0] if primary_chart.luck_cycles else None
    return {
        "year_pillar": primary_chart.pillars["year"].gan_zhi,
        "month_pillar": primary_chart.pillars["month"].gan_zhi,
        "day_pillar": primary_chart.pillars["day"].gan_zhi,
        "hour_pillar": primary_chart.pillars["time"].gan_zhi,
        "luck_cycle_start_age": first_luck.start_age if first_luck else None,
        "luck_cycle_start_age_years": first_luck.start_age_years if first_luck else None,
        "luck_cycle_start_age_months": first_luck.start_age_months if first_luck else None,
        "luck_cycle_start_age_total_months": first_luck.start_age_total_months if first_luck else None,
        "luck_cycle_first_ganzhi": first_luck.gan_zhi if first_luck else None,
    }


def _solar_term_boundary_to_dict(boundary: SolarTermBoundary) -> Dict[str, Any]:
    payload = {
        "name": boundary.name,
        "datetime": boundary.datetime_text,
        "delta_seconds": boundary.delta_seconds,
        "delta_minutes": round(boundary.delta_seconds / 60.0, 3),
        "relation": boundary.relation,
        "is_jie": boundary.is_jie,
        "is_qi": boundary.is_qi,
        "provider": boundary.provider,
        "used_reference": boundary.used_reference,
    }
    if boundary.fallback_reason:
        payload["fallback_reason"] = boundary.fallback_reason
    if boundary.reference:
        payload["reference"] = boundary.reference
    return payload


def _solar_term_severity(delta_seconds: int) -> Optional[Severity]:
    delta_minutes = delta_seconds / 60.0
    if delta_minutes <= NEAR_SOLAR_TERM_CRITICAL_MINUTES:
        return "critical"
    if delta_minutes <= NEAR_SOLAR_TERM_WARNING_MINUTES:
        return "warning"
    if delta_minutes <= NEAR_SOLAR_TERM_INFO_MINUTES:
        return "info"
    return None


def _solar_term_affected_fields(term_name: str) -> List[str]:
    if term_name in IPCHUN_TERM_NAMES:
        return ["year_pillar", "month_pillar"]
    return ["month_pillar"]


def _birth_time_interval_to_dict(birth_time_policy: BirthTimePolicyResult) -> Optional[Dict[str, str]]:
    if birth_time_policy.birth_time_interval is None:
        return None

    return {
        "start": birth_time_policy.birth_time_interval.start,
        "end": birth_time_policy.birth_time_interval.end,
    }


def _normalized_solar_day_interval(
    calendar_normalization: CalendarNormalizationResult,
) -> Optional[Dict[str, Any]]:
    try:
        normalized_dt = datetime.strptime(
            calendar_normalization.normalized_solar_datetime,
            "%Y-%m-%d %H:%M:%S",
        )
    except ValueError:
        return None

    start_dt = normalized_dt.replace(hour=0, minute=0, second=0)
    end_dt = normalized_dt.replace(hour=23, minute=59, second=59)
    return {
        "start_dt": start_dt,
        "end_dt": end_dt,
        "start": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "end": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _day_pillar_for_midnight_rule(input_dt: datetime, sect: int) -> str:
    solar = Solar.fromYmdHms(
        input_dt.year,
        input_dt.month,
        input_dt.day,
        input_dt.hour,
        input_dt.minute,
        input_dt.second,
    )
    eight_char = solar.getLunar().getEightChar()
    eight_char.setSect(sect)
    day_reference = resolve_day_pillar_reference(
        input_dt=input_dt,
        sect=sect,
        lunar_python_gan_zhi=eight_char.getDay(),
    )
    return day_reference.gan_zhi


def _midnight_rule_day_pillar_evidence(day_start_dt: datetime) -> Optional[Dict[str, Any]]:
    boundary_dt = day_start_dt.replace(hour=23, minute=0, second=0)
    sect1_day_pillar = _day_pillar_for_midnight_rule(boundary_dt, 1)
    sect2_day_pillar = _day_pillar_for_midnight_rule(boundary_dt, 2)
    if sect1_day_pillar == sect2_day_pillar:
        return None

    return {
        "boundary_datetime": boundary_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "sect1_23_changes_day": {
            "midnight_rule": "sect1_23_changes_day",
            "day_pillar": sect1_day_pillar,
        },
        "sect2_00_changes_day": {
            "midnight_rule": "sect2_00_changes_day",
            "day_pillar": sect2_day_pillar,
        },
    }


def detect_uncertainty(
    *,
    birth_time_policy: BirthTimePolicyResult,
    time_correction: TimeCorrectionResult,
    calendar_normalization: CalendarNormalizationResult,
    regional_solar_correction: RegionalSolarCorrectionResult,
    birth_time_context: BirthTimeContext,
    primary_chart: SajuCalculationResult,
    candidate_charts: Sequence[CandidateChart],
) -> List[UncertaintyFlag]:
    """Return deterministic uncertainty flags without changing any primary calculation."""
    flags: List[UncertaintyFlag] = []

    if birth_time_policy.is_birth_time_estimated:
        flags.append(
            UncertaintyFlag(
                code="birth_time_unknown",
                severity="info",
                affected_fields=["time_pillar", "luck_cycles"],
                user_message="Birth time is unknown, so hour-based output is limited.",
                developer_message="BirthTimePolicy disabled time-pillar-dependent sections.",
                evidence={
                    "effective_birth_time": birth_time_policy.effective_birth_time,
                    "effective_birth_time_usage": "internal_placeholder_only",
                    "birth_time_interval": _birth_time_interval_to_dict(birth_time_policy),
                    "disabled_sections": list(birth_time_policy.disabled_sections),
                },
            )
        )

        solar_day_interval = _normalized_solar_day_interval(calendar_normalization)
        if solar_day_interval is not None:
            interval_evidence = {
                "birth_time_interval": _birth_time_interval_to_dict(birth_time_policy),
                "normalized_solar_day_interval": {
                    "start": solar_day_interval["start"],
                    "end": solar_day_interval["end"],
                },
            }

            jie_boundary = find_jie_inside_interval(
                solar_day_interval["start_dt"],
                solar_day_interval["end_dt"],
                timezone_id=birth_time_context.timezone_id,
            )
            if jie_boundary is not None:
                affected_fields = _solar_term_affected_fields(jie_boundary.name)
                flags.append(
                    UncertaintyFlag(
                        code="day_interval_contains_solar_term",
                        severity="info",
                        affected_fields=affected_fields,
                        user_message="The possible birth-time interval contains a solar-term boundary.",
                        developer_message="The unknown birth-time day contains a Jie boundary.",
                        evidence={
                            "provider": jie_boundary.provider,
                            "provider_apis": list(jie_boundary.provider_apis),
                            **interval_evidence,
                            "solar_term": _solar_term_boundary_to_dict(jie_boundary),
                        },
                    )
                )
                flags.append(
                    UncertaintyFlag(
                        code="year_or_month_pillar_may_change",
                        severity="critical",
                        affected_fields=affected_fields,
                        user_message="The year or month pillar may change within the unknown birth-time day.",
                        developer_message="A Jie boundary inside the day can change month pillar, and Ipchun can also change year pillar.",
                        evidence={
                            "provider": jie_boundary.provider,
                            "provider_apis": list(jie_boundary.provider_apis),
                            **interval_evidence,
                            "solar_term": _solar_term_boundary_to_dict(jie_boundary),
                        },
                    )
                )

            midnight_rule_evidence = _midnight_rule_day_pillar_evidence(solar_day_interval["start_dt"])
            if midnight_rule_evidence is not None:
                flags.append(
                    UncertaintyFlag(
                        code="day_pillar_uncertain_due_to_unknown_time",
                        severity="critical",
                        affected_fields=["day_pillar"],
                        user_message="The day pillar cannot be confirmed because the unknown birth-time interval includes the late-zi boundary.",
                        developer_message="At 23:00, sect1 and sect2 midnight rules produce different day pillars.",
                        evidence={
                            "provider": "lunar_python",
                            "provider_apis": ["Solar.getLunar", "Lunar.getEightChar", "EightChar.setSect"],
                            **interval_evidence,
                            **midnight_rule_evidence,
                        },
                    )
                )

        return flags

    if not birth_time_policy.is_birth_time_estimated and _is_near_midnight(
        birth_time_context.standard_local_datetime
    ):
        flags.append(
            UncertaintyFlag(
                code="near_midnight",
                severity="info",
                affected_fields=["day_pillar", "hour_pillar"],
                user_message="The birth time is close to a day boundary.",
                developer_message="standard_local_datetime is within the near-midnight threshold.",
                evidence={
                    "standard_local_datetime": birth_time_context.standard_local_datetime,
                    "threshold_minutes": NEAR_MIDNIGHT_THRESHOLD_MINUTES,
                },
            )
        )

    if birth_time_context.dst_offset_minutes != 0 or regional_solar_correction.daylight_saving_offset_minutes != 0:
        flags.append(
            UncertaintyFlag(
                code="timezone_dst_applied",
                severity="info",
                affected_fields=["standard_local_datetime", "corrected_solar_datetime"],
                user_message="Daylight-saving time was applied to the birth time.",
                developer_message="DST offset contributed to the observed time context.",
                evidence={
                    "dst_offset_minutes": birth_time_context.dst_offset_minutes,
                    "daylight_saving_offset_minutes": regional_solar_correction.daylight_saving_offset_minutes,
                    "timezone_id": birth_time_context.timezone_id,
                },
            )
        )

    if time_correction.ambiguous:
        flags.append(
            UncertaintyFlag(
                code="ambiguous_local_time",
                severity="info",
                affected_fields=["normalized_utc_datetime", "fold"],
                user_message="The local time is ambiguous in the selected timezone.",
                developer_message="zoneinfo marked the local time ambiguous; fold was selected deterministically.",
                evidence={
                    "timezone_id": time_correction.tzid,
                    "fold": time_correction.fold,
                    "source_local_datetime": time_correction.source_local_datetime,
                },
            )
        )

    if calendar_normalization.calendar_type == "lunar":
        flags.append(
            UncertaintyFlag(
                code="lunar_input_used",
                severity="info",
                affected_fields=["calendar_normalization"],
                user_message="The input date was provided as a lunar calendar date.",
                developer_message="Calendar normalization converted lunar input to solar input.",
                evidence={
                    "input_date": calendar_normalization.input_date,
                    "normalized_solar_datetime": calendar_normalization.normalized_solar_datetime,
                    "normalized_lunar_datetime": calendar_normalization.normalized_lunar_datetime,
                },
            )
        )

    if calendar_normalization.is_lunar_leap_month:
        flags.append(
            UncertaintyFlag(
                code="leap_month_input_used",
                severity="info",
                affected_fields=["calendar_normalization"],
                user_message="The input used a leap lunar month.",
                developer_message="Leap lunar month was enabled during calendar normalization.",
                evidence={
                    "input_date": calendar_normalization.input_date,
                    "normalized_solar_datetime": calendar_normalization.normalized_solar_datetime,
                },
            )
        )

    primary_input_datetime = primary_chart.meta.get(
        "corrected_solar_datetime",
        birth_time_context.corrected_solar_datetime,
    )
    nearest_solar_term = nearest_solar_term_boundary(
        primary_input_datetime,
        timezone_id=birth_time_context.timezone_id,
    )
    solar_term_severity = (
        _solar_term_severity(nearest_solar_term.delta_seconds)
        if nearest_solar_term is not None
        else None
    )
    if nearest_solar_term is not None and solar_term_severity is not None:
        flags.append(
            UncertaintyFlag(
                code="near_solar_term",
                severity=solar_term_severity,
                affected_fields=_solar_term_affected_fields(nearest_solar_term.name),
                user_message="The primary chart input is close to a solar-term boundary.",
                developer_message="The configured solar-term boundary provider found a nearby Jie boundary.",
                evidence={
                    "provider": nearest_solar_term.provider,
                    "provider_apis": list(nearest_solar_term.provider_apis),
                    "input_datetime_to_lunar_python": primary_input_datetime,
                    "thresholds_minutes": {
                        "info": NEAR_SOLAR_TERM_INFO_MINUTES,
                        "warning": NEAR_SOLAR_TERM_WARNING_MINUTES,
                        "critical": NEAR_SOLAR_TERM_CRITICAL_MINUTES,
                    },
                    "nearest_solar_term": _solar_term_boundary_to_dict(nearest_solar_term),
                },
            )
        )

    standard_candidate = _find_candidate(candidate_charts, "standard_local")
    mean_candidate = _find_candidate(candidate_charts, "mean_solar")
    standard_mean_changes = _compare_candidates(
        standard_candidate,
        mean_candidate,
        ("year_pillar", "month_pillar", "day_pillar", "hour_pillar"),
    )
    if "hour_pillar" in standard_mean_changes:
        flags.append(
            UncertaintyFlag(
                code="standard_vs_mean_solar_changes_hour_pillar",
                severity="warning",
                affected_fields=["hour_pillar"],
                user_message="The hour pillar changes between standard local time and mean solar time.",
                developer_message="standard_local and mean_solar candidates produce different hour pillars.",
                evidence={
                    "standard_local": _candidate_evidence(standard_candidate) if standard_candidate else None,
                    "mean_solar": _candidate_evidence(mean_candidate) if mean_candidate else None,
                    "changed_fields": sorted(standard_mean_changes),
                },
            )
        )

    sect1_candidate = _find_candidate(candidate_charts, "sect1_23_changes_day")
    sect2_candidate = _find_candidate(candidate_charts, "sect2_00_changes_day")
    midnight_rule_changes = _compare_candidates(
        sect1_candidate,
        sect2_candidate,
        ("day_pillar", "hour_pillar"),
    )
    if "day_pillar" in midnight_rule_changes:
        flags.append(
            UncertaintyFlag(
                code="midnight_rule_changes_day_pillar",
                severity="critical",
                affected_fields=["day_pillar"],
                user_message="The day pillar changes depending on the midnight rule.",
                developer_message="sect1 and sect2 candidates have different day pillars.",
                evidence={
                    "sect1_23_changes_day": _candidate_evidence(sect1_candidate) if sect1_candidate else None,
                    "sect2_00_changes_day": _candidate_evidence(sect2_candidate) if sect2_candidate else None,
                    "changed_fields": sorted(midnight_rule_changes),
                },
            )
        )
    if "hour_pillar" in midnight_rule_changes:
        flags.append(
            UncertaintyFlag(
                code="midnight_rule_changes_hour_pillar",
                severity="warning",
                affected_fields=["hour_pillar"],
                user_message="The hour pillar changes depending on the midnight rule.",
                developer_message="sect1 and sect2 candidates have different hour pillars.",
                evidence={
                    "sect1_23_changes_day": _candidate_evidence(sect1_candidate) if sect1_candidate else None,
                    "sect2_00_changes_day": _candidate_evidence(sect2_candidate) if sect2_candidate else None,
                    "changed_fields": sorted(midnight_rule_changes),
                },
            )
        )

    luck_cycle_candidates = [
        candidate
        for candidate in candidate_charts
        if (
            "luck_cycle_start_age" in candidate.differences_from_primary
            or "luck_cycle_start_age_total_months" in candidate.differences_from_primary
        )
    ]
    if luck_cycle_candidates:
        flags.append(
            UncertaintyFlag(
                code="luck_cycle_start_age_changed",
                severity="warning",
                affected_fields=["luck_cycle_start_age", "luck_cycle_start_age_total_months"],
                user_message="The first luck-cycle start age changes in one or more candidate charts.",
                developer_message="At least one candidate chart has a different first luck-cycle start age.",
                evidence={
                    "primary": _primary_pillar_evidence(primary_chart),
                    "candidates": [_candidate_evidence(candidate) for candidate in luck_cycle_candidates],
                },
            )
        )

    primary_changed_fields = _changed_fields(candidate_charts)
    if primary_changed_fields:
        flags.append(
            UncertaintyFlag(
                code="primary_differs_from_candidate",
                severity=_severity_from_fields(primary_changed_fields),
                affected_fields=sorted(primary_changed_fields),
                user_message="At least one candidate chart differs from the primary chart.",
                developer_message="Candidate chart comparison found differences from the primary calculation.",
                evidence={
                    "primary": _primary_pillar_evidence(primary_chart),
                    "changed_fields": sorted(primary_changed_fields),
                    "candidates": [
                        _candidate_evidence(candidate)
                        for candidate in candidate_charts
                        if candidate.differences_from_primary
                    ],
                },
            )
        )

    return flags
