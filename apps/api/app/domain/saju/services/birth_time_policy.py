from dataclasses import dataclass
from typing import List

from app.domain.saju.schemas import SajuPreviewRequest


@dataclass
class BirthTimePolicyResult:
    is_birth_time_estimated: bool
    effective_birth_time: str
    hour_pillar_enabled: bool
    visible_pillar_keys: List[str]
    disabled_sections: List[str]


def resolve_birth_time_policy(payload: SajuPreviewRequest) -> BirthTimePolicyResult:
    if payload.is_birth_time_estimated:
        return BirthTimePolicyResult(
            is_birth_time_estimated=True,
            effective_birth_time="00:00",
            hour_pillar_enabled=False,
            visible_pillar_keys=["year", "month", "day"],
            disabled_sections=["time_pillar", "luck_cycles", "hour_based_interpretation"],
        )

    return BirthTimePolicyResult(
        is_birth_time_estimated=False,
        effective_birth_time=payload.birth_time,
        hour_pillar_enabled=True,
        visible_pillar_keys=["year", "month", "day", "time"],
        disabled_sections=[],
    )
