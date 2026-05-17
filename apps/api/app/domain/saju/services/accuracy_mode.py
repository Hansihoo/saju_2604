"""Select the primary calculation basis for preview accuracy modes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.domain.saju.time_correction import BirthTimeContext


AccuracyMode = Literal["legacy", "standard_time", "mean_solar_time", "compare"]


@dataclass(frozen=True)
class CalculationBasis:
    accuracy_mode: AccuracyMode
    primary_candidate_id: str
    primary_time_basis: str
    primary_midnight_rule: str
    primary_input_datetime_to_lunar_python: str
    primary_day_pillar_basis_datetime: str
    legacy_corrected_solar_datetime: str
    compare_candidates_enabled: bool


def resolve_calculation_basis(
    *,
    accuracy_mode: AccuracyMode,
    birth_time_context: BirthTimeContext,
) -> CalculationBasis:
    """Return the selected primary input without changing legacy correction fields."""
    if accuracy_mode == "standard_time":
        return CalculationBasis(
            accuracy_mode=accuracy_mode,
            primary_candidate_id="standard_local",
            primary_time_basis="standard_local",
            primary_midnight_rule="sect1_23_changes_day",
            primary_input_datetime_to_lunar_python=birth_time_context.standard_local_datetime,
            primary_day_pillar_basis_datetime=birth_time_context.standard_local_datetime,
            legacy_corrected_solar_datetime=birth_time_context.legacy_corrected_solar_datetime,
            compare_candidates_enabled=False,
        )

    if accuracy_mode == "mean_solar_time":
        return CalculationBasis(
            accuracy_mode=accuracy_mode,
            primary_candidate_id="mean_solar",
            primary_time_basis="mean_solar",
            primary_midnight_rule="sect1_23_changes_day",
            primary_input_datetime_to_lunar_python=birth_time_context.mean_solar_datetime,
            primary_day_pillar_basis_datetime=birth_time_context.mean_solar_datetime,
            legacy_corrected_solar_datetime=birth_time_context.legacy_corrected_solar_datetime,
            compare_candidates_enabled=False,
        )

    return CalculationBasis(
        accuracy_mode=accuracy_mode,
        primary_candidate_id="legacy_corrected",
        primary_time_basis="legacy_corrected",
        primary_midnight_rule="sect1_23_changes_day",
        primary_input_datetime_to_lunar_python=birth_time_context.legacy_corrected_solar_datetime,
        primary_day_pillar_basis_datetime=birth_time_context.normalized_solar_datetime,
        legacy_corrected_solar_datetime=birth_time_context.legacy_corrected_solar_datetime,
        compare_candidates_enabled=accuracy_mode == "compare",
    )
