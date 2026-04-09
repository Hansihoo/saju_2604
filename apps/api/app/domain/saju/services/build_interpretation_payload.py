from typing import List

from app.domain.saju.llm_payload import (
    InterpretationEvidenceItem,
    InterpretationInputProfile,
    InterpretationLuckCycle,
    InterpretationPayload,
    InterpretationSignalBlock,
    InterpretationSupplementaryPosition,
    InterpretationTimeContext,
    InterpretationVisiblePillar,
)
from app.domain.saju.schemas import SajuPreviewRequest, SajuPreviewResponse


OUTPUT_SECTIONS = [
    "summary",
    "strengths",
    "cautions",
    "love",
    "career",
    "wealth",
    "action_advice",
]

NARRATIVE_RULES = [
    "Use only the provided facts and signals.",
    "Do not recalculate saju, luck cycles, or element counts.",
    "Keep the tone grounded and avoid exaggerated certainty.",
    "If the birth time is estimated, explicitly acknowledge the hidden hour-pillar limitations.",
    "Prefer concise Korean output unless the user explicitly requests another language.",
]


def _build_visible_pillars(response: SajuPreviewResponse) -> List[InterpretationVisiblePillar]:
    pillars = []
    for key in response.result.signals.visible_pillar_keys:
        pillar = getattr(response.manse.pillars, key)
        if pillar.gan_zhi and pillar.stem and pillar.branch:
            pillars.append(
                InterpretationVisiblePillar(
                    key=key,
                    label=pillar.label,
                    gan_zhi=pillar.gan_zhi,
                    stem=pillar.stem,
                    branch=pillar.branch,
                )
            )
    return pillars


def _build_evidence(response: SajuPreviewResponse) -> List[InterpretationEvidenceItem]:
    items: List[InterpretationEvidenceItem] = []
    for key, evidence in response.result.evidence_sections.items():
        items.append(
            InterpretationEvidenceItem(
                key=key,
                title=evidence.title,
                status=evidence.status,
                summary=evidence.summary,
            )
        )
    return items


def _build_luck_cycles(response: SajuPreviewResponse) -> List[InterpretationLuckCycle]:
    if not response.manse.luck_cycles_enabled:
        return []

    return [
        InterpretationLuckCycle(
            start_age=cycle.start_age,
            end_age=cycle.end_age,
            start_year=cycle.start_year,
            end_year=cycle.end_year,
            gan_zhi=cycle.gan_zhi,
        )
        for cycle in response.manse.luck_cycles
    ]


def _build_supplementary_positions(
    response: SajuPreviewResponse,
) -> List[InterpretationSupplementaryPosition]:
    positions = response.manse.supplementary_positions
    return [
        InterpretationSupplementaryPosition(
            key=position.key,
            label=position.label,
            gan_zhi=position.gan_zhi,
        )
        for position in [
            positions.tai_yuan,
            positions.ming_gong,
            positions.shen_gong,
            positions.tai_xi,
        ]
    ]


def build_interpretation_payload(
    *,
    request: SajuPreviewRequest,
    response: SajuPreviewResponse,
) -> InterpretationPayload:
    return InterpretationPayload(
        output_sections=OUTPUT_SECTIONS,
        profile=InterpretationInputProfile(
            calendar_type=request.calendar_type,
            birth_date=request.birth_date.isoformat(),
            birth_time=request.birth_time,
            is_birth_time_estimated=request.is_birth_time_estimated,
            is_lunar_leap_month=request.is_lunar_leap_month,
            gender=request.gender,
            region_id=request.region_id,
            region_display_name=response.region.display_name,
            tzid=response.region.tzid,
        ),
        time_context=InterpretationTimeContext(
            normalized_local_datetime=response.time_correction.normalized_local_datetime,
            normalized_utc_datetime=response.time_correction.normalized_utc_datetime,
            corrected_solar_datetime=response.regional_solar_correction.corrected_solar_datetime,
            regional_time_offset_minutes=response.regional_solar_correction.regional_time_offset_minutes,
            daylight_saving_offset_minutes=response.regional_solar_correction.daylight_saving_offset_minutes,
            correction_basis=response.regional_solar_correction.correction_basis,
        ),
        visible_pillars=_build_visible_pillars(response),
        day_master=response.manse.meta.day_master,
        element_counts={
            "wood": response.manse.elements.wood,
            "fire": response.manse.elements.fire,
            "earth": response.manse.elements.earth,
            "metal": response.manse.elements.metal,
            "water": response.manse.elements.water,
        },
        ten_god_stems={
            "year": response.manse.pillars.year.stem_ten_god or "",
            "month": response.manse.pillars.month.stem_ten_god or "",
            "day": response.manse.pillars.day.stem_ten_god or "",
            "time": response.manse.pillars.time.stem_ten_god or "",
        },
        signals=InterpretationSignalBlock(
            internal_grade=response.result.signals.internal_grade,
            balance_score=response.result.signals.balance_score,
            charm_score=response.result.signals.charm_score,
            wealth_score=response.result.signals.wealth_score,
            career_score=response.result.signals.career_score,
            leadership_score=response.result.signals.leadership_score,
            dominant_elements=response.result.signals.dominant_elements,
            missing_elements=response.result.signals.missing_elements,
        ),
        evidence=_build_evidence(response),
        luck_cycles=_build_luck_cycles(response),
        supplementary_positions=_build_supplementary_positions(response),
        limitations=list(response.result.limitations),
        disabled_sections=list(response.result.disabled_sections),
        notes=list(response.manse.notes),
        narrative_rules=NARRATIVE_RULES,
        prompt_seed=(
            f"{response.region.display_name} 기준으로 계산된 사실 정보만 사용해 "
            f"{', '.join(OUTPUT_SECTIONS)} 순서의 해석 초안을 만든다."
        ),
    )
