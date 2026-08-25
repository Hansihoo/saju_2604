"""이 파일은 해석 fallback을 포맷하는 로직을 담는다."""

from typing import Dict, List

from app.domain.saju.interpretation import InterpretationLocale, InterpretationNarrative
from app.domain.saju.llm_payload import InterpretationPayload
from app.domain.saju.schemas import ElementKey


def _luck_cycle_start_age_text(cycle, *, locale: InterpretationLocale) -> str:
    if cycle.start_age_years is not None and cycle.start_age_months is not None:
        if locale == "ko":
            return f"{cycle.start_age_years}세 {cycle.start_age_months}개월"
        return f"age {cycle.start_age_years}y {cycle.start_age_months}m"
    return f"{cycle.start_age}세" if locale == "ko" else f"age {cycle.start_age}"


ELEMENT_LABELS: Dict[InterpretationLocale, Dict[ElementKey, str]] = {
    "ko": {
        "wood": "목",
        "fire": "화",
        "earth": "토",
        "metal": "금",
        "water": "수",
    },
    "en": {
        "wood": "Wood",
        "fire": "Fire",
        "earth": "Earth",
        "metal": "Metal",
        "water": "Water",
    },
}

def _join_elements(locale: InterpretationLocale, values: List[ElementKey]) -> str:
    """오행 목록 관련 값을 반환하거나 처리한다."""
    labels = ELEMENT_LABELS[locale]
    return ", ".join(labels[value] for value in values)


def _visible_pillar_text(payload: InterpretationPayload) -> str:
    """기둥 텍스트 관련 값을 반환하거나 처리한다."""
    return " / ".join(item.gan_zhi for item in payload.visible_pillars)


def _balance_tone(locale: InterpretationLocale, missing_elements: List[ElementKey]) -> str:
    """tone 관련 값을 반환하거나 처리한다."""
    if locale == "ko":
        if not missing_elements:
            return "현재 보이는 오행이 함께 드러나므로, 상황에 따라 강점의 쓰임을 살피는 편이 좋습니다."
        if len(missing_elements) == 1:
            return "한 기운이 상대적으로 약하게 보여, 생활 리듬으로 보완하는 편이 좋습니다."
        return "강한 부분과 보완할 부분이 함께 보여, 한쪽으로 치우치지 않는 선택이 중요합니다."

    if not missing_elements:
        return "The visible elements appear together, so their practical use matters more than a fixed label."
    if len(missing_elements) == 1:
        return "One element is relatively weak, so routine can help support the balance."
    return "Strengths and areas to support appear together, so avoid leaning too hard on one side."


def _format_summary(locale: InterpretationLocale, payload: InterpretationPayload) -> str:
    """요약을 포맷한다."""
    pillars = _visible_pillar_text(payload)
    tone = _balance_tone(locale, payload.signals.missing_elements)
    if locale == "ko":
        summary = (
            f"{payload.profile.region_display_name} 기준으로 확인된 기둥은 {pillars}입니다. "
            f"현재 보이는 오행의 강약을 함께 살펴봅니다. {tone}"
        )
        if payload.profile.is_birth_time_estimated:
            summary += " 출생시간이 미상이어서 시주 기반 해석은 제외했습니다."
        return summary

    summary = (
        f"Using {payload.profile.region_display_name} as the location basis, the visible pillars are "
        f"{pillars}. The reading considers the visible element pattern together. {tone}"
    )
    if payload.profile.is_birth_time_estimated:
        summary += " Hour-pillar-dependent interpretation is hidden because the birth time is estimated."
    return summary


def _format_strengths(locale: InterpretationLocale, payload: InterpretationPayload) -> List[str]:
    """strengths을 포맷한다."""
    items: List[str] = []
    dominant = _join_elements(locale, payload.signals.dominant_elements)

    if locale == "ko":
        if dominant:
            items.append(f"현재 보이는 오행에서는 {dominant} 기운이 상대적으로 중심을 잡고 있습니다.")
        else:
            items.append("현재 보이는 오행에서는 특정 기운이 과도하게 튀지 않습니다.")
        items.append("관계·일·금전은 각각의 기둥과 십성 근거를 함께 살펴봅니다.")
        return items

    if dominant:
        items.append(f"In the visible balance, {dominant} takes the lead.")
    else:
        items.append("No single element is overly dominant in the visible balance.")
    items.append("Relationships, work, and wealth are considered through their own pillar and Ten-God facts.")
    return items


def _format_cautions(locale: InterpretationLocale, payload: InterpretationPayload) -> List[str]:
    """cautions을 포맷한다."""
    items: List[str] = []
    missing = _join_elements(locale, payload.signals.missing_elements)

    if locale == "ko":
        if missing:
            items.append(f"{missing} 기운은 상대적으로 약해 한쪽으로 치우친 판단이 나오기 쉽습니다.")
        else:
            items.append("뚜렷하게 비어 있는 오행은 보이지 않지만 상황에 따라 기복은 생길 수 있습니다.")
    else:
        if missing:
            items.append(f"{missing} is relatively weak, so decisions can lean to one side.")
        else:
            items.append("No major deficiency stands out, but the flow can still fluctuate by context.")

    if payload.limitations:
        items.append(payload.limitations[0])
    elif locale == "ko":
        items.append("현재 단계의 해석은 계산된 사실을 요약한 초안이며 과장된 단정은 피합니다.")
    else:
        items.append("This stage stays close to computed facts and avoids exaggerated certainty.")

    return items


def _format_action(locale: InterpretationLocale, payload: InterpretationPayload) -> str:
    """action을 포맷한다."""
    missing = _join_elements(locale, payload.signals.missing_elements)
    first_cycle = payload.luck_cycles[0] if payload.luck_cycles else None

    if locale == "ko":
        base = (
            f"{missing} 기운을 보완하는 생활 리듬과 선택 기준을 두면 균형을 회복하는 데 도움이 됩니다."
            if missing
            else "강한 기운을 유지하되 한쪽 판단에 과하게 기대지 않도록 생활 리듬을 조절하는 편이 좋습니다."
        )
        if first_cycle is not None:
            age_text = _luck_cycle_start_age_text(first_cycle, locale=locale)
            return (
                f"{base} 현재 확인된 첫 대운은 {age_text}부터 시작하는 "
                f"{first_cycle.gan_zhi} 흐름입니다."
            )
        return base

    base = (
        f"Support {missing} in your routines and decisions to improve balance."
        if missing
        else "Keep your strengths steady while avoiding over-reliance on one side."
    )
    if first_cycle is not None:
        age_text = _luck_cycle_start_age_text(first_cycle, locale=locale)
        return (
            f"{base} The first verified decade cycle starts at {age_text} "
            f"with {first_cycle.gan_zhi}."
        )
    return base


def format_interpretation_fallback(
    *,
    payload: InterpretationPayload,
    locale: InterpretationLocale = "ko",
) -> InterpretationNarrative:
    """구조화된 해석 payload로 fallback 서술문을 생성한다."""
    return InterpretationNarrative(
        locale=locale,
        summary=_format_summary(locale, payload),
        strengths=_format_strengths(locale, payload),
        cautions=_format_cautions(locale, payload),
        love=(
            "관계는 배우자궁과 반복되는 생활 리듬을 함께 살펴봅니다."
            if locale == "ko"
            else "Relationships are considered through spouse-house facts and repeated daily rhythm."
        ),
        career=(
            "일은 월주와 십성의 역할 신호를 함께 살펴봅니다."
            if locale == "ko"
            else "Work is considered through the month pillar and Ten-God role signals."
        ),
        wealth=(
            "금전은 재성·식상 신호와 실제 소비 습관을 함께 살펴봅니다."
            if locale == "ko"
            else "Wealth is considered through wealth/output signals and practical spending habits."
        ),
        action_advice=_format_action(locale, payload),
    )
