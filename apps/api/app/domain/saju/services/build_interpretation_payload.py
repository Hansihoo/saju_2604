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
    InterpretationFavorablePeriod,
    InterpretationInputProfile,
    InterpretationLoveFacts,
    InterpretationLuckCycle,
    InterpretationLuckCycleAnalysis,
    InterpretationLuckFlowFacts,
    InterpretationPayload,
    InterpretationSignalBlock,
    InterpretationSpecialStar,
    InterpretationSupplementaryPosition,
    InterpretationTimeContext,
    InterpretationUncertaintyFlag,
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
from app.domain.saju.prompts.interpretation_report import get_interpretation_report_prompt
from app.domain.saju.schemas import SajuPreviewRequest, SajuPreviewResponse


OUTPUT_SECTIONS = [
    "core_analysis",
    "love",
    "career",
    "wealth",
    "luck_flow",
]
PROMPT_SPEC = get_interpretation_report_prompt()

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


def _build_uncertainty_summary(response: SajuPreviewResponse) -> List[InterpretationUncertaintyFlag]:
    return [
        InterpretationUncertaintyFlag(
            code=flag.code,
            severity=flag.severity,
            affected_fields=list(flag.affected_fields),
            user_message=flag.user_message,
        )
        for flag in response.result.uncertainty_summary
        if flag.severity in ("warning", "critical")
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
            start_age_years=cycle.start_age_years,
            start_age_months=cycle.start_age_months,
            start_age_total_months=cycle.start_age_total_months,
            change_age_years=cycle.change_age_years,
            change_age_months=cycle.change_age_months,
            change_age_total_months=cycle.change_age_total_months,
            start_datetime=cycle.start_datetime,
            change_datetime=cycle.change_datetime,
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


STEM_TRAITS = {
    "\u7532": ("wood", "yang"),
    "\u4e59": ("wood", "yin"),
    "\u4e19": ("fire", "yang"),
    "\u4e01": ("fire", "yin"),
    "\u620a": ("earth", "yang"),
    "\u5df1": ("earth", "yin"),
    "\u5e9a": ("metal", "yang"),
    "\u8f9b": ("metal", "yin"),
    "\u58ec": ("water", "yang"),
    "\u7678": ("water", "yin"),
}

BRANCH_ELEMENTS = {
    "\u5b50": "water",
    "\u4e11": "earth",
    "\u5bc5": "wood",
    "\u536f": "wood",
    "\u8fb0": "earth",
    "\u5df3": "fire",
    "\u5348": "fire",
    "\u672a": "earth",
    "\u7533": "metal",
    "\u9149": "metal",
    "\u620c": "earth",
    "\u4ea5": "water",
}

PRODUCES = {
    "wood": "fire",
    "fire": "earth",
    "earth": "metal",
    "metal": "water",
    "water": "wood",
}

CONTROLS = {
    "wood": "earth",
    "fire": "metal",
    "earth": "water",
    "metal": "wood",
    "water": "fire",
}

ELEMENT_LABELS = {
    "ko": {
        "wood": "목",
        "fire": "화",
        "earth": "토",
        "metal": "금",
        "water": "수",
    },
    "en": {
        "wood": "wood",
        "fire": "fire",
        "earth": "earth",
        "metal": "metal",
        "water": "water",
    },
}

DOMAIN_LABELS = {
    "ko": {
        "love": "연애와 관계",
        "career": "직장과 역할",
        "wealth": "금전 관리",
        "relationships": "관계 정리",
        "stability": "생활 안정",
        "visibility": "표현과 성과",
        "responsibility": "책임 있는 자리",
        "learning": "학습과 문서",
        "foundation": "생활 기반",
    },
    "en": {
        "love": "love and relationships",
        "career": "career and role",
        "wealth": "money management",
        "relationships": "relationship sorting",
        "stability": "life stability",
        "visibility": "visibility and output",
        "responsibility": "responsible roles",
        "learning": "learning and documents",
        "foundation": "life foundation",
    },
}

TEN_GOD_BY_GROUP = {
    "ko": {
        "peer": ("비견", "겁재"),
        "output": ("식신", "상관"),
        "wealth": ("편재", "정재"),
        "officer": ("편관", "정관"),
        "resource": ("편인", "정인"),
        "unknown": ("확인 대기", "확인 대기"),
    },
    "en": {
        "peer": ("Peer", "Rival"),
        "output": ("Expression", "Output"),
        "wealth": ("Indirect Wealth", "Direct Wealth"),
        "officer": ("Seven Killings", "Direct Officer"),
        "resource": ("Indirect Resource", "Direct Resource"),
        "unknown": ("Not available", "Not available"),
    },
}


def _unique(items: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _month_period_label(value: str | None, *, locale: OutputLocale) -> str:
    if not value:
        return ""
    match = re.match(r"^(\d{4})-(\d{2})", value)
    if not match:
        return value[:10]
    year, month = match.groups()
    if locale == "ko":
        return f"{year}년 {int(month)}월"
    return f"{year}-{month}"


def _cycle_period(cycle: InterpretationLuckCycle, locale: OutputLocale) -> str:
    start = _month_period_label(cycle.start_datetime, locale=locale)
    end = _month_period_label(cycle.change_datetime, locale=locale)
    if start and end:
        return f"{start} ~ {end}"
    return f"{cycle.start_year}-{cycle.end_year}"


def _stem_ten_god_group(day_stem: str, target_stem: str) -> Tuple[str, bool]:
    day = STEM_TRAITS.get(day_stem)
    target = STEM_TRAITS.get(target_stem)
    if not day or not target:
        return "unknown", True

    day_element, day_polarity = day
    target_element, target_polarity = target
    same_polarity = day_polarity == target_polarity

    if target_element == day_element:
        return "peer", same_polarity
    if PRODUCES[day_element] == target_element:
        return "output", same_polarity
    if CONTROLS[day_element] == target_element:
        return "wealth", same_polarity
    if CONTROLS[target_element] == day_element:
        return "officer", same_polarity
    if PRODUCES[target_element] == day_element:
        return "resource", same_polarity
    return "unknown", same_polarity


def _impact_level(score: int) -> str:
    if score >= 4:
        return "high"
    if score == 3:
        return "medium_high"
    if score == 2:
        return "medium"
    if score == 1:
        return "low_medium"
    return "low"


def _favorability_label(score: int) -> str:
    if score >= 5:
        return "high"
    if score >= 4:
        return "medium_high"
    if score >= 2:
        return "medium"
    if score == 1:
        return "low_medium"
    return "low"


def _group_luck_profile(group: str, locale: OutputLocale) -> Dict[str, List[str] | str]:
    if locale == "ko":
        profiles = {
            "peer": {
                "phase": "adjustment",
                "phase_label": "관계와 역할 재정리",
                "overall_tone": "adjustment",
                "domains": ["relationships"],
                "caution_domains": ["relationships", "wealth"],
                "good_for": ["관계 정리", "협업 기준 세우기", "역할 재배치"],
                "watch_out": ["경쟁", "공유 비용", "관계 피로"],
                "reason_tags": ["관계 신호 강화", "역할 조율"],
                "caution_tags": ["관계 피로", "비용 누수"],
                "actions": ["관계 경계 설정", "공동 비용 점검", "역할 범위 정리"],
                "summary": "확장보다 사람과 역할의 기준을 다시 세우는 시기",
            },
            "output": {
                "phase": "transition",
                "phase_label": "표현과 성과 방식 조정",
                "overall_tone": "transition",
                "domains": ["visibility", "career"],
                "caution_domains": ["relationships"],
                "good_for": ["표현 방식 개선", "성과물 만들기", "기술과 콘텐츠 정리"],
                "watch_out": ["말의 예민함", "과한 노출", "성급한 판단"],
                "reason_tags": ["표현 신호 강화", "결과물 중심"],
                "caution_tags": ["언어 충돌", "속도 과다"],
                "actions": ["말과 글의 기준 정리", "성과물 축적", "충동적 결정 줄이기"],
                "summary": "생각을 밖으로 꺼내 성과물로 정리하는 시기",
            },
            "wealth": {
                "phase": "building",
                "phase_label": "현실 성과와 자원 관리",
                "overall_tone": "stabilizing",
                "domains": ["wealth", "foundation"],
                "caution_domains": ["wealth", "relationships"],
                "good_for": ["금전 관리", "자산화", "현실 성과 고정"],
                "watch_out": ["지출 확대", "수익 집착", "관계 비용"],
                "reason_tags": ["현실성 강화", "자원 관리"],
                "caution_tags": ["지출 증가", "관계 비용"],
                "actions": ["지출 습관 점검", "관리 기준 만들기", "장기 계획 정리"],
                "summary": "성과를 생활 기반과 관리 구조로 묶는 시기",
            },
            "officer": {
                "phase": "stabilization",
                "phase_label": "책임과 역할 강화",
                "overall_tone": "stabilizing",
                "domains": ["career", "responsibility", "stability"],
                "caution_domains": ["career", "relationships"],
                "good_for": ["직장 안정", "책임 있는 자리", "역할 정리"],
                "watch_out": ["부담 증가", "압박감", "권위 충돌"],
                "reason_tags": ["책임 증가", "역할 강화"],
                "caution_tags": ["부담 증가", "압박감"],
                "actions": ["일의 경계 설정", "책임 범위 문서화", "체력 루틴 만들기"],
                "summary": "역할과 책임이 커지며 안정 구조를 만드는 시기",
            },
            "resource": {
                "phase": "preparation",
                "phase_label": "학습과 기반 준비",
                "overall_tone": "preparation",
                "domains": ["learning", "stability", "foundation"],
                "caution_domains": ["career"],
                "good_for": ["학습", "문서 정리", "자격과 기반 만들기"],
                "watch_out": ["생각 과다", "속도 저하", "의존성"],
                "reason_tags": ["기반 보강", "문서와 학습"],
                "caution_tags": ["실행 지연", "생각 과다"],
                "actions": ["생활 루틴 구축", "문서 정리", "학습 계획 세우기"],
                "summary": "바로 확장하기보다 다음 단계를 준비하는 시기",
            },
        }
    else:
        profiles = {
            "peer": {
                "phase": "adjustment",
                "phase_label": "relationship and role adjustment",
                "overall_tone": "adjustment",
                "domains": ["relationships"],
                "caution_domains": ["relationships", "wealth"],
                "good_for": ["relationship sorting", "collaboration standards", "role reset"],
                "watch_out": ["competition", "shared costs", "relationship fatigue"],
                "reason_tags": ["relationship signals", "role adjustment"],
                "caution_tags": ["relationship fatigue", "cost leakage"],
                "actions": ["set relationship boundaries", "review shared costs", "clarify roles"],
                "summary": "a period for resetting people and role standards before expansion",
            },
            "output": {
                "phase": "transition",
                "phase_label": "expression and output adjustment",
                "overall_tone": "transition",
                "domains": ["visibility", "career"],
                "caution_domains": ["relationships"],
                "good_for": ["communication style", "deliverables", "skill and content output"],
                "watch_out": ["sensitive wording", "overexposure", "rushed judgment"],
                "reason_tags": ["output signals", "deliverable focus"],
                "caution_tags": ["wording conflict", "too much speed"],
                "actions": ["clarify communication rules", "build deliverables", "reduce impulsive decisions"],
                "summary": "a period for turning thoughts into visible output",
            },
            "wealth": {
                "phase": "building",
                "phase_label": "practical results and resource management",
                "overall_tone": "stabilizing",
                "domains": ["wealth", "foundation"],
                "caution_domains": ["wealth", "relationships"],
                "good_for": ["money management", "asset planning", "fixing practical results"],
                "watch_out": ["larger spending", "profit fixation", "relationship costs"],
                "reason_tags": ["practicality", "resource management"],
                "caution_tags": ["spending increase", "relationship costs"],
                "actions": ["review spending habits", "build management rules", "organize long-term plans"],
                "summary": "a period for turning results into a more stable life base",
            },
            "officer": {
                "phase": "stabilization",
                "phase_label": "responsibility and role strengthening",
                "overall_tone": "stabilizing",
                "domains": ["career", "responsibility", "stability"],
                "caution_domains": ["career", "relationships"],
                "good_for": ["career stability", "responsible roles", "role clarity"],
                "watch_out": ["greater pressure", "heavier duty", "authority friction"],
                "reason_tags": ["more responsibility", "role strengthening"],
                "caution_tags": ["greater burden", "pressure"],
                "actions": ["set work boundaries", "document responsibility", "build energy routines"],
                "summary": "a period for forming stability through clearer roles and responsibility",
            },
            "resource": {
                "phase": "preparation",
                "phase_label": "learning and foundation preparation",
                "overall_tone": "preparation",
                "domains": ["learning", "stability", "foundation"],
                "caution_domains": ["career"],
                "good_for": ["learning", "documentation", "credentials and foundation"],
                "watch_out": ["overthinking", "slower execution", "dependency"],
                "reason_tags": ["foundation support", "learning and documents"],
                "caution_tags": ["execution delay", "overthinking"],
                "actions": ["build routines", "organize documents", "set a learning plan"],
                "summary": "a period for preparing the next step rather than expanding immediately",
            },
        }

    return profiles.get(group, profiles["resource"])


def _localized_domain_keys(keys: Iterable[str], locale: OutputLocale) -> List[str]:
    labels = DOMAIN_LABELS[locale]
    return _unique(labels.get(key, key) for key in keys)


def _cycle_analysis_score(
    *,
    group: str,
    stem_element: str | None,
    branch_element: str | None,
    missing_elements: Sequence[str],
    dominant_elements: Sequence[str],
) -> int:
    score = 1
    if group in {"wealth", "officer"}:
        score += 2
    elif group in {"resource", "output"}:
        score += 1

    if branch_element in missing_elements:
        score += 2
    if stem_element in missing_elements:
        score += 1
    if branch_element in dominant_elements and stem_element in dominant_elements:
        score -= 1
    if group == "peer":
        score -= 1
    return score


def _build_single_luck_cycle_analysis(
    *,
    cycle: InterpretationLuckCycle,
    day_master: str,
    response: SajuPreviewResponse,
    locale: OutputLocale,
    confidence: str,
) -> Tuple[int, InterpretationLuckCycleAnalysis]:
    stem = cycle.gan_zhi[0] if cycle.gan_zhi else ""
    branch = cycle.gan_zhi[1] if len(cycle.gan_zhi) > 1 else ""
    group, same_polarity = _stem_ten_god_group(day_master, stem)
    stem_element = STEM_TRAITS.get(stem, (None, None))[0]
    branch_element = BRANCH_ELEMENTS.get(branch)
    profile = _group_luck_profile(group, locale)
    missing_elements = response.result.signals.missing_elements
    dominant_elements = response.result.signals.dominant_elements
    score = _cycle_analysis_score(
        group=group,
        stem_element=stem_element,
        branch_element=branch_element,
        missing_elements=missing_elements,
        dominant_elements=dominant_elements,
    )
    favorability = _favorability_label(score)
    good_for = list(profile["good_for"])
    watch_out = list(profile["watch_out"])
    reason_tags = list(profile["reason_tags"])
    caution_tags = list(profile["caution_tags"])
    domains = list(profile["domains"])
    caution_domains = list(profile["caution_domains"])

    if branch_element in missing_elements:
        element_label = ELEMENT_LABELS[locale][branch_element]
        if locale == "ko":
            good_for.append(f"부족한 {element_label} 기운 보완")
            reason_tags.append("부족 오행 보완")
        else:
            good_for.append(f"supporting weaker {element_label} energy")
            reason_tags.append("supports a weaker element")
        domains.append("stability")

    if branch_element in dominant_elements:
        element_label = ELEMENT_LABELS[locale][branch_element]
        if locale == "ko":
            watch_out.append(f"이미 강한 {element_label} 기운 과다")
            caution_tags.append("강한 오행 과다")
        else:
            watch_out.append(f"overemphasis of already strong {element_label} energy")
            caution_tags.append("strong element overemphasis")
        caution_domains.append("stability")

    stem_ten_god = TEN_GOD_BY_GROUP[locale][group][0 if same_polarity else 1]
    career_score = 1 + int("career" in domains) + int("responsibility" in domains) + int(group == "officer")
    wealth_score = 1 + int("wealth" in domains) + int(group == "wealth") + int(branch_element in missing_elements)
    love_score = 1 + int("love" in domains) + int("relationships" in domains) + int(group in {"peer", "officer", "wealth"})
    relationship_score = 1 + int("relationships" in domains) + int(group == "peer")

    return score, InterpretationLuckCycleAnalysis(
        display_gan_zhi=cycle.display_gan_zhi,
        start_year=cycle.start_year,
        end_year=cycle.end_year,
        start_age=cycle.start_age,
        end_age=cycle.end_age,
        period=_cycle_period(cycle, locale),
        phase=str(profile["phase"]),
        phase_label=str(profile["phase_label"]),
        overall_tone=str(profile["overall_tone"]),
        cycle_rank=0,
        overall_favorability=favorability,
        confidence=confidence,
        stem_ten_god=stem_ten_god,
        branch_element=branch_element,
        favorable_domains=_localized_domain_keys(domains, locale),
        caution_domains=_localized_domain_keys(caution_domains, locale),
        good_for=_unique(good_for),
        watch_out=_unique(watch_out),
        reason_tags=_unique(reason_tags),
        caution_tags=_unique(caution_tags),
        love_impact=_impact_level(love_score),
        career_impact=_impact_level(career_score),
        wealth_impact=_impact_level(wealth_score),
        relationship_impact=_impact_level(relationship_score),
        summary=str(profile["summary"]),
    )


def _build_luck_cycle_analysis(
    *,
    request: SajuPreviewRequest,
    response: SajuPreviewResponse,
    locale: OutputLocale,
    luck_cycles: Sequence[InterpretationLuckCycle],
) -> List[InterpretationLuckCycleAnalysis]:
    if not luck_cycles or not response.manse.luck_cycles_enabled:
        return []

    confidence = "low" if request.is_birth_time_estimated else "medium"
    scored = [
        _build_single_luck_cycle_analysis(
            cycle=cycle,
            day_master=response.manse.meta.day_master,
            response=response,
            locale=locale,
            confidence=confidence,
        )
        for cycle in luck_cycles
    ]
    ranked = sorted(scored, key=lambda item: item[0], reverse=True)
    for rank, (_, analysis) in enumerate(ranked, start=1):
        analysis.cycle_rank = rank
    return [analysis for _, analysis in scored]


def _find_cycle_analysis(
    analyses: Sequence[InterpretationLuckCycleAnalysis],
    cycle: InterpretationLuckCycle | None,
) -> InterpretationLuckCycleAnalysis | None:
    if cycle is None:
        return None
    return next(
        (
            analysis
            for analysis in analyses
            if analysis.display_gan_zhi == cycle.display_gan_zhi
            and analysis.start_year == cycle.start_year
        ),
        None,
    )


def _build_favorable_periods(
    analyses: Sequence[InterpretationLuckCycleAnalysis],
    *,
    current_year: int,
) -> List[InterpretationFavorablePeriod]:
    relevant = [analysis for analysis in analyses if analysis.end_year >= current_year]
    if not relevant:
        relevant = list(analyses[-2:])
    chronological = sorted(relevant, key=lambda item: item.start_year)
    candidates = [
        analysis
        for analysis in chronological
        if analysis.overall_favorability in {"high", "medium_high", "medium"}
    ][:3]
    if not candidates and chronological:
        candidates = chronological[:1]
    return [
        InterpretationFavorablePeriod(
            period=analysis.period,
            luck_cycle=analysis.display_gan_zhi,
            favorable_for=analysis.favorable_domains[:4],
            reason_tags=analysis.reason_tags[:4],
            caution_tags=analysis.caution_tags[:4],
            confidence=analysis.confidence,
        )
        for analysis in candidates
    ]


def _build_luck_flow_facts(
    *,
    current_flow: InterpretationCurrentFlowContext,
    analyses: Sequence[InterpretationLuckCycleAnalysis],
    locale: OutputLocale,
) -> InterpretationLuckFlowFacts:
    current_analysis = _find_cycle_analysis(analyses, current_flow.active_luck_cycle)
    next_analysis = _find_cycle_analysis(analyses, current_flow.next_luck_cycle)
    favorable_periods = _build_favorable_periods(analyses, current_year=current_flow.current_year)

    if locale == "ko":
        if current_analysis and next_analysis:
            transition_summary = (
                f"현재와 다음 대운이 모두 {current_analysis.phase_label} 흐름으로 분류되어, "
                "큰 성격 전환보다 현재의 기준을 이어서 적용하는 흐름입니다."
                if current_analysis.phase_label == next_analysis.phase_label
                else f"현재는 {current_analysis.phase_label} 흐름이고, 다음은 {next_analysis.phase_label} 흐름으로 이동합니다."
            )
        else:
            transition_summary = "현재와 다음 대운 정보가 제한적이어서 큰 방향만 참고합니다."
        default_actions = ["관계 정리", "지출 습관 점검", "생활 루틴 구축", "일의 경계 설정"]
    else:
        if current_analysis and next_analysis:
            transition_summary = (
                "The current and next cycles share the same phase, so the reading focuses on carrying the current standards forward."
                if current_analysis.phase_label == next_analysis.phase_label
                else f"The current cycle is {current_analysis.phase_label}, moving toward {next_analysis.phase_label} next."
            )
        else:
            transition_summary = "Current and next luck-cycle details are limited, so only the broad direction is used."
        default_actions = [
            "sort relationships",
            "review spending habits",
            "build daily routines",
            "set work boundaries",
        ]

    action_tags = list(default_actions)
    if current_analysis:
        action_tags = _unique(list(current_analysis.good_for[:2]) + action_tags)

    return InterpretationLuckFlowFacts(
        current_phase=current_analysis.phase if current_analysis else "",
        current_phase_label=current_analysis.phase_label if current_analysis else "",
        current_luck_cycle=current_analysis.display_gan_zhi if current_analysis else "",
        current_period=current_analysis.period if current_analysis else "",
        next_luck_cycle=next_analysis.display_gan_zhi if next_analysis else "",
        next_period=next_analysis.period if next_analysis else "",
        next_phase=next_analysis.phase if next_analysis else "",
        next_phase_label=next_analysis.phase_label if next_analysis else "",
        favorable_periods=favorable_periods,
        transition_summary=transition_summary,
        now_action_tags=action_tags[:6],
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
    effective_birth_time = "unknown" if request.is_birth_time_estimated else request.birth_time
    visible_pillars = _build_visible_pillars(response, locale)
    luck_cycles = _build_luck_cycles(response, locale)
    special_stars = _build_special_stars(response, locale)
    current_flow = _build_current_flow_context(request, response, luck_cycles)
    luck_cycle_analysis = _build_luck_cycle_analysis(
        request=request,
        response=response,
        locale=locale,
        luck_cycles=luck_cycles,
    )
    luck_flow_facts = _build_luck_flow_facts(
        current_flow=current_flow,
        analyses=luck_cycle_analysis,
        locale=locale,
    )
    uncertainty_summary = _build_uncertainty_summary(response)
    narrative_rules = list(PROMPT_SPEC.narrative_rules)
    if uncertainty_summary:
        narrative_rules.append(
            "If uncertainty_summary is present, verbalize only those precomputed uncertainty flags; do not infer new uncertainty."
        )

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
            accuracy_mode=response.result.calculation_basis.accuracy_mode,
            primary_time_basis=response.result.calculation_basis.primary_time_basis,
            primary_input_datetime_to_lunar_python=(
                response.result.calculation_basis.primary_input_datetime_to_lunar_python
            ),
            primary_midnight_rule=response.result.calculation_basis.primary_midnight_rule,
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
            dominant_elements=response.result.signals.dominant_elements,
            missing_elements=response.result.signals.missing_elements,
        ),
        evidence=_build_evidence(response),
        uncertainty_summary=uncertainty_summary,
        luck_cycles=luck_cycles,
        current_flow=current_flow,
        luck_cycle_analysis=luck_cycle_analysis,
        luck_flow_facts=luck_flow_facts,
        love_facts=_build_love_facts(request, response, locale, special_stars),
        career_facts=_build_career_facts(response, locale, special_stars),
        wealth_facts=_build_wealth_facts(response, locale, special_stars),
        supplementary_positions=_build_supplementary_positions(response, locale),
        special_stars=special_stars,
        limitations=list(response.result.limitations),
        disabled_sections=list(response.result.disabled_sections),
        notes=list(response.manse.notes),
        narrative_rules=narrative_rules,
        prompt_seed=PROMPT_SPEC.build_prompt_seed(
            locale=locale,
            region_display_name=_localize_region_display_name(response, locale),
        ),
    )
