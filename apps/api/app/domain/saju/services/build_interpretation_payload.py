"""Builds the structured interpretation payload from preview data."""

from __future__ import annotations

from datetime import date, datetime
import re
from typing import Dict, Iterable, List, Sequence, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python 3.8 fallback
    from backports.zoneinfo import ZoneInfo

from app.domain.saju.llm_payload import (
    InterpretationCareerFacts,
    InterpretationCountMetric,
    InterpretationCurrentFlowContext,
    InterpretationEvidenceItem,
    InterpretationInputProfile,
    InterpretationLoveFacts,
    InterpretationLuckCycle,
    InterpretationPayload,
    InterpretationSignalBlock,
    InterpretationSpecialStar,
    InterpretationSupplementaryPosition,
    InterpretationTimeContext,
    InterpretationVisiblePillar,
    InterpretationWealthFacts,
)
from app.domain.saju.localization import (
    OutputLocale,
    localize_branch,
    localize_ganzhi,
    localize_pillar_label,
    localize_special_star_label,
    localize_stem,
    localize_ten_god,
)
from app.domain.saju.schemas import SajuPreviewRequest, SajuPreviewResponse


OUTPUT_SECTIONS = [
    "core_analysis",
    "love",
    "career",
    "wealth",
    "luck_flow",
]

NARRATIVE_RULES = [
    "Use only the provided facts and signals.",
    "Do not recalculate saju, manse, timing corrections, pillars, ten gods, special stars, scores, or luck cycles.",
    "Use profile.locale as the only output language.",
    "If profile.locale is ko, write in Hangul only and do not use Hanja.",
    "If profile.locale is en, write in English only and do not use Korean or Hanja.",
    "Do not expose numeric scores or point-based phrasing.",
    "Use scores only as internal tone-strength signals.",
    "Each section should be easy to read but include short user-facing basis chips.",
    "Use the label 풀이 포인트 for short basis chips.",
    "Use the label 전문가 노트 for a short explanation of the interpretation logic.",
    "Do not use raw evidence IDs in user-facing text.",
    "Do not use the English word evidence in user-facing text.",
    "Use current_flow for current-period commentary in love, career, wealth, and luck-flow sections.",
    "Use love_facts, career_facts, and wealth_facts when writing the matching sections.",
    "Special stars are supporting indicators only, not sole proof.",
    "Keep the tone grounded and avoid exaggerated certainty.",
    "If the birth time is estimated, explicitly acknowledge the hidden hour-pillar limitations.",
    "Core analysis must include standout traits, comparison, strengths, risks, and direction.",
    "Love must include relationship style, marriage traits, good match, difficult match, advice, and current timing.",
    "Career must include work style, suitable environment, risks, strategy, and current timing.",
    "Wealth must include flow type, earning pattern, spending risk, cautions, and management direction.",
    "Luck flow must focus on current and next cycle only.",
]

LOVE_STAR_KEYWORDS = ("dohwa", "hongyeom", "mokyok", "wangji", "hamji", "yeokma")
CAREER_STAR_KEYWORDS = ("munchang", "hakdang", "hagwan", "jangseong", "yangin", "goegang", "cheonmun")
WEALTH_STAR_KEYWORDS = ("gongmang", "woldeok", "taegeuk")

TEN_GOD_GROUPS = {
    "peer": ("비견", "겁재"),
    "output": ("식신", "상관"),
    "wealth": ("편재", "정재"),
    "officer": ("편관", "정관"),
    "resource": ("편인", "정인"),
}

TEN_GOD_GROUP_LABELS = {
    "ko": {
        "peer": "비겁",
        "output": "식상",
        "wealth": "재성",
        "officer": "관성",
        "resource": "인성",
    },
    "en": {
        "peer": "Peer stars",
        "output": "Output stars",
        "wealth": "Wealth stars",
        "officer": "Officer stars",
        "resource": "Resource stars",
    },
}

PARTNER_STAR_LABELS = {
    "ko": {
        "male": "재성",
        "female": "관성",
    },
    "en": {
        "male": "Wealth star",
        "female": "Officer star",
    },
}

SPOUSE_HOUSE_LABELS = {
    "ko": "배우자궁",
    "en": "Spouse house",
}

ENGLISH_ALIAS_RE = re.compile(r"^[A-Za-z][A-Za-z\s.'-]*$")


def _resolve_locale(request: SajuPreviewRequest) -> OutputLocale:
    return getattr(request, "locale", "ko")


def _localize_region_display_name(response: SajuPreviewResponse, locale: OutputLocale) -> str:
    if locale == "ko":
        return response.region.display_name

    for alias in response.region.aliases:
        if ENGLISH_ALIAS_RE.match(alias):
            return f"{alias}, South Korea"

    return "South Korea"


def _local_today(tzid: str) -> date:
    return datetime.now(ZoneInfo(tzid)).date()


def _calculate_current_age(birth_date: date, today: date) -> int:
    age = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1
    return max(age, 0)


def _build_visible_pillars(
    response: SajuPreviewResponse,
    locale: OutputLocale,
) -> List[InterpretationVisiblePillar]:
    pillars: List[InterpretationVisiblePillar] = []
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
                    display_label=localize_pillar_label(key, locale),
                    display_gan_zhi=localize_ganzhi(pillar.gan_zhi, locale),
                    display_stem=localize_stem(pillar.stem, locale),
                    display_branch=localize_branch(pillar.branch, locale),
                )
            )
    return pillars


def _build_evidence(response: SajuPreviewResponse) -> List[InterpretationEvidenceItem]:
    return [
        InterpretationEvidenceItem(
            key=key,
            title=evidence.title,
            status=evidence.status,
            summary=evidence.summary,
        )
        for key, evidence in response.result.evidence_sections.items()
    ]


def _build_luck_cycles(
    response: SajuPreviewResponse,
    locale: OutputLocale,
) -> List[InterpretationLuckCycle]:
    if not response.manse.luck_cycles_enabled:
        return []

    return [
        InterpretationLuckCycle(
            start_age=cycle.start_age,
            end_age=cycle.end_age,
            start_year=cycle.start_year,
            end_year=cycle.end_year,
            gan_zhi=cycle.gan_zhi,
            display_gan_zhi=localize_ganzhi(cycle.gan_zhi, locale),
        )
        for cycle in response.manse.luck_cycles
    ]


def _find_current_and_next_luck_cycles(
    luck_cycles: Sequence[InterpretationLuckCycle],
    current_year: int,
) -> Tuple[InterpretationLuckCycle | None, InterpretationLuckCycle | None]:
    if not luck_cycles:
        return None, None

    active_index = next(
        (
            index
            for index, cycle in enumerate(luck_cycles)
            if cycle.start_year <= current_year <= cycle.end_year
        ),
        None,
    )

    if active_index is not None:
        next_index = active_index + 1
        return luck_cycles[active_index], luck_cycles[next_index] if next_index < len(luck_cycles) else None

    future_index = next((index for index, cycle in enumerate(luck_cycles) if current_year < cycle.start_year), None)
    if future_index is not None:
        return None, luck_cycles[future_index]

    return luck_cycles[-1], None


def _build_current_flow_context(
    request: SajuPreviewRequest,
    response: SajuPreviewResponse,
    luck_cycles: Sequence[InterpretationLuckCycle],
) -> InterpretationCurrentFlowContext:
    today = _local_today(response.region.tzid)
    current_year = today.year
    current_age = _calculate_current_age(request.birth_date, today)
    active_luck_cycle, next_luck_cycle = _find_current_and_next_luck_cycles(luck_cycles, current_year)
    return InterpretationCurrentFlowContext(
        current_year=current_year,
        current_age=current_age,
        active_luck_cycle=active_luck_cycle,
        next_luck_cycle=next_luck_cycle,
    )


def _build_supplementary_positions(
    response: SajuPreviewResponse,
    locale: OutputLocale,
) -> List[InterpretationSupplementaryPosition]:
    positions = response.manse.supplementary_positions
    return [
        InterpretationSupplementaryPosition(
            key=position.key,
            label=position.label,
            gan_zhi=position.gan_zhi,
            display_label=position.label if locale == "ko" else position.label,
            display_gan_zhi=localize_ganzhi(position.gan_zhi, locale),
        )
        for position in [
            positions.tai_yuan,
            positions.ming_gong,
            positions.shen_gong,
            positions.tai_xi,
        ]
    ]


def _build_special_stars(
    response: SajuPreviewResponse,
    locale: OutputLocale,
) -> List[InterpretationSpecialStar]:
    stars: List[InterpretationSpecialStar] = []
    for star in response.manse.special_stars:
        if not star.active:
            continue
        stars.append(
            InterpretationSpecialStar(
                key=star.key,
                label=star.label,
                tier=star.tier,
                category=star.category,
                usage_summary=star.usage_summary,
                matched_pillars=[match.pillar_key for match in star.matches],
                evidence_id=f"star:{star.key}",
                display_label=localize_special_star_label(star.key, star.label, locale),
            )
        )
    return stars


def _ten_god_distribution(response: SajuPreviewResponse) -> Dict[str, int]:
    return dict(response.manse.analysis.visible_ten_god_distribution)


def _sum_ten_gods(distribution: Dict[str, int], names: Iterable[str]) -> int:
    return sum(distribution.get(name, 0) for name in names)


def _metric(locale: OutputLocale, key: str, count: int) -> InterpretationCountMetric:
    return InterpretationCountMetric(
        key=key,
        label=TEN_GOD_GROUP_LABELS[locale][key],
        count=count,
    )


def _active_star_labels_by_keywords(
    stars: Sequence[InterpretationSpecialStar],
    keywords: Sequence[str],
    limit: int = 4,
) -> List[str]:
    items: List[str] = []
    for star in stars:
        if any(keyword in star.key for keyword in keywords):
            items.append(star.display_label)
        if len(items) >= limit:
            break
    return items


def _build_love_facts(
    request: SajuPreviewRequest,
    response: SajuPreviewResponse,
    locale: OutputLocale,
    stars: Sequence[InterpretationSpecialStar],
) -> InterpretationLoveFacts:
    distribution = _ten_god_distribution(response)
    partner_group = "wealth" if request.gender == "male" else "officer"
    partner_count = _sum_ten_gods(distribution, TEN_GOD_GROUPS[partner_group])
    return InterpretationLoveFacts(
        score=response.result.signals.charm_score,
        spouse_house_label=SPOUSE_HOUSE_LABELS[locale],
        spouse_house_branch=localize_branch(response.manse.pillars.day.branch or "", locale),
        spouse_house_ten_god=localize_ten_god(response.manse.pillars.day.branch_ten_god or "", locale),
        partner_star_label=PARTNER_STAR_LABELS[locale][request.gender],
        partner_star_count=partner_count,
        active_star_labels=_active_star_labels_by_keywords(stars, LOVE_STAR_KEYWORDS),
    )


def _build_career_facts(
    response: SajuPreviewResponse,
    locale: OutputLocale,
    stars: Sequence[InterpretationSpecialStar],
) -> InterpretationCareerFacts:
    distribution = _ten_god_distribution(response)
    key_ten_gods = [
        _metric(locale, "officer", _sum_ten_gods(distribution, TEN_GOD_GROUPS["officer"])),
        _metric(locale, "resource", _sum_ten_gods(distribution, TEN_GOD_GROUPS["resource"])),
        _metric(locale, "output", _sum_ten_gods(distribution, TEN_GOD_GROUPS["output"])),
    ]
    return InterpretationCareerFacts(
        score=response.result.signals.career_score,
        month_pillar_label=localize_pillar_label("month", locale),
        month_pillar_gan_zhi=localize_ganzhi(response.manse.pillars.month.gan_zhi or "", locale),
        month_stem_ten_god=localize_ten_god(response.manse.pillars.month.stem_ten_god or "", locale),
        key_ten_gods=key_ten_gods,
        active_star_labels=_active_star_labels_by_keywords(stars, CAREER_STAR_KEYWORDS),
    )


def _build_wealth_facts(
    response: SajuPreviewResponse,
    locale: OutputLocale,
    stars: Sequence[InterpretationSpecialStar],
) -> InterpretationWealthFacts:
    distribution = _ten_god_distribution(response)
    key_ten_gods = [
        _metric(locale, "wealth", _sum_ten_gods(distribution, TEN_GOD_GROUPS["wealth"])),
        _metric(locale, "output", _sum_ten_gods(distribution, TEN_GOD_GROUPS["output"])),
        _metric(locale, "peer", _sum_ten_gods(distribution, TEN_GOD_GROUPS["peer"])),
    ]
    missing_elements = list(response.result.signals.missing_elements)
    return InterpretationWealthFacts(
        score=response.result.signals.wealth_score,
        key_ten_gods=key_ten_gods,
        active_star_labels=_active_star_labels_by_keywords(stars, WEALTH_STAR_KEYWORDS),
        missing_elements=missing_elements,
    )


def build_interpretation_payload(
    *,
    request: SajuPreviewRequest,
    response: SajuPreviewResponse,
) -> InterpretationPayload:
    locale = _resolve_locale(request)
    effective_birth_time = "00:00" if request.is_birth_time_estimated else request.birth_time
    visible_pillars = _build_visible_pillars(response, locale)
    luck_cycles = _build_luck_cycles(response, locale)
    special_stars = _build_special_stars(response, locale)

    return InterpretationPayload(
        output_sections=OUTPUT_SECTIONS,
        profile=InterpretationInputProfile(
            locale=locale,
            calendar_type=request.calendar_type,
            birth_date=request.birth_date.isoformat(),
            birth_time=effective_birth_time,
            is_birth_time_estimated=request.is_birth_time_estimated,
            is_lunar_leap_month=request.is_lunar_leap_month,
            gender=request.gender,
            region_id=request.region_id,
            region_display_name=_localize_region_display_name(response, locale),
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
        visible_pillars=visible_pillars,
        day_master=localize_stem(response.manse.meta.day_master, locale),
        element_counts={
            "wood": response.manse.elements.wood,
            "fire": response.manse.elements.fire,
            "earth": response.manse.elements.earth,
            "metal": response.manse.elements.metal,
            "water": response.manse.elements.water,
        },
        ten_god_stems={
            "year": localize_ten_god(response.manse.pillars.year.stem_ten_god or "", locale),
            "month": localize_ten_god(response.manse.pillars.month.stem_ten_god or "", locale),
            "day": localize_ten_god(response.manse.pillars.day.stem_ten_god or "", locale),
            "time": localize_ten_god(response.manse.pillars.time.stem_ten_god or "", locale),
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
        luck_cycles=luck_cycles,
        current_flow=_build_current_flow_context(request, response, luck_cycles),
        love_facts=_build_love_facts(request, response, locale, special_stars),
        career_facts=_build_career_facts(response, locale, special_stars),
        wealth_facts=_build_wealth_facts(response, locale, special_stars),
        supplementary_positions=_build_supplementary_positions(response, locale),
        special_stars=special_stars,
        limitations=list(response.result.limitations),
        disabled_sections=list(response.result.disabled_sections),
        notes=list(response.manse.notes),
        narrative_rules=NARRATIVE_RULES,
        prompt_seed=(
            f"Use {locale} only. Build a grounded saju reading for {_localize_region_display_name(response, locale)} "
            f"with focus on current flow, love, career, wealth, and structure."
        ),
    )
