"""Build tokenless daily and monthly flow guidance from deterministic chart facts.

The module deliberately keeps the output in the category of reference guidance.
It does not assign a score or claim that a specific event will happen.  The
current v1 rule table uses the target day's/month's stem Ten-God signal and a
small, explicit branch-relation table against the visible natal pillars.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, List, Optional, Sequence, Tuple

from lunar_python import Solar
from lunar_python.util import LunarUtil

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python 3.8 fallback
    from backports.zoneinfo import ZoneInfo

from app.domain.saju.engine import LuckCycle, SajuCalculationResult
from app.domain.saju.localization import (
    localize_branch,
    localize_ganzhi,
    localize_pillar_label,
    localize_stem,
    localize_ten_god,
)
from app.domain.saju.reference_calendar import lookup_lunar_reference_by_solar_date
from app.domain.saju.schemas import (
    PeriodFlow,
    PeriodFlowCycle,
    PeriodFlowEvidence,
    PeriodFlows,
    SajuPreviewRequest,
)
from app.domain.saju.services.birth_time_policy import resolve_birth_time_policy
from app.domain.saju.services.canonical_year_month import (
    MONTH_OFFSET_BY_TERM_ID,
    month_ganzhi_for_year_stem,
    year_ganzhi_for_saju_year,
)
from app.domain.saju.services.solar_term_boundaries import (
    JIE_TERM_IDS_IN_MONTH_ORDER,
    SolarTermBoundary,
    find_jie_boundary_by_term,
    list_jie_boundaries_for_years,
)


ELEMENT_LABELS = {
    "木": {"ko": "목", "en": "Wood"},
    "火": {"ko": "화", "en": "Fire"},
    "土": {"ko": "토", "en": "Earth"},
    "金": {"ko": "금", "en": "Metal"},
    "水": {"ko": "수", "en": "Water"},
}

TEN_GOD_GROUP_BY_LABEL = {
    "비견": "peer",
    "겁재": "peer",
    "식신": "output",
    "상관": "output",
    "편재": "wealth",
    "정재": "wealth",
    "편관": "officer",
    "정관": "officer",
    "편인": "resource",
    "정인": "resource",
    "일간": "peer",
}

RULES = {
    "peer": {
        "ko": {
            "headline": "기준과 역할을 정리하는 흐름",
            "summary": "내 기준을 분명히 하되 다른 사람의 몫까지 대신 맡지 않는 편이 흐름을 다루기 쉽습니다.",
            "focus": ["자기 기준", "역할 분담"],
            "actions": [
                "지금 지킬 기준을 한 문장으로 적어 보세요.",
                "공동 작업은 담당자와 마감부터 확인하세요.",
            ],
        },
        "en": {
            "headline": "A period to clarify standards and roles",
            "summary": "Keep your own standard clear without taking responsibility for someone else's share.",
            "focus": ["Personal standards", "Role boundaries"],
            "actions": [
                "Write down one standard you want to keep.",
                "Confirm ownership and deadlines in shared work.",
            ],
        },
    },
    "output": {
        "ko": {
            "headline": "표현과 결과물을 다듬는 흐름",
            "summary": "생각을 밖으로 꺼내 결과물로 묶을수록 흐름이 선명해집니다. 표현의 속도보다 마무리 기준을 먼저 보세요.",
            "focus": ["표현", "완성도"],
            "actions": [
                "해야 할 말을 초안이나 목록으로 먼저 꺼내세요.",
                "완료 조건을 정한 뒤 공개하거나 전달하세요.",
            ],
        },
        "en": {
            "headline": "A period to refine expression and output",
            "summary": "The signal is easier to use when ideas become a concrete output. Check the finish line before speeding up.",
            "focus": ["Expression", "Completion"],
            "actions": [
                "Put the idea into a draft or a short list first.",
                "Set the completion criteria before sharing it.",
            ],
        },
    },
    "wealth": {
        "ko": {
            "headline": "자원과 보상 기준을 관리하는 흐름",
            "summary": "들어오는 양보다 무엇이 남는지, 시간·돈·에너지가 어디로 새는지를 확인하는 편이 현실적입니다.",
            "focus": ["예산", "보상 기준"],
            "actions": [
                "반복 지출과 꼭 필요한 지출을 나눠 보세요.",
                "제안이나 거래는 기대보다 조건과 유지 비용을 확인하세요.",
            ],
        },
        "en": {
            "headline": "A period to manage resources and reward criteria",
            "summary": "Look at what remains after time, money, and energy are spent rather than only at what comes in.",
            "focus": ["Budget", "Reward criteria"],
            "actions": [
                "Separate recurring costs from essential costs.",
                "Check terms and carrying costs before accepting an offer or deal.",
            ],
        },
    },
    "officer": {
        "ko": {
            "headline": "책임과 마감 기준을 세우는 흐름",
            "summary": "해야 할 일과 평가 기준을 눈에 보이게 만들수록 부담이 줄어듭니다. 모든 요청을 한꺼번에 떠안지는 마세요.",
            "focus": ["책임 범위", "마감"],
            "actions": [
                "우선순위와 마감이 적힌 한 장짜리 목록을 만드세요.",
                "추가 요청에는 범위와 일정을 다시 합의하세요.",
            ],
        },
        "en": {
            "headline": "A period to define responsibility and deadlines",
            "summary": "Making duties and evaluation criteria visible can reduce pressure. Do not accept every request at once.",
            "focus": ["Scope of responsibility", "Deadlines"],
            "actions": [
                "Make a one-page list of priorities and deadlines.",
                "Reconfirm scope and timing when new requests arrive.",
            ],
        },
    },
    "resource": {
        "ko": {
            "headline": "배우고 회복하는 흐름",
            "summary": "새 정보를 바로 결론으로 만들기보다 정리하고 검증하는 시간이 도움이 됩니다. 회복을 일정에 넣어야 배운 것이 남습니다.",
            "focus": ["정리", "회복"],
            "actions": [
                "필요한 정보와 나중에 볼 정보를 분리해 두세요.",
                "집중 뒤에 쉬는 시간을 미리 배치하세요.",
            ],
        },
        "en": {
            "headline": "A period to learn and recover",
            "summary": "Give new information time to be organized and checked before turning it into a conclusion. Recovery helps learning stick.",
            "focus": ["Organization", "Recovery"],
            "actions": [
                "Separate information you need now from information for later.",
                "Schedule recovery time after focused work.",
            ],
        },
    },
}

BRANCH_RELATIONS = {
    frozenset({"子", "午"}): "clash",
    frozenset({"丑", "未"}): "clash",
    frozenset({"寅", "申"}): "clash",
    frozenset({"卯", "酉"}): "clash",
    frozenset({"辰", "戌"}): "clash",
    frozenset({"巳", "亥"}): "clash",
    frozenset({"子", "丑"}): "harmony",
    frozenset({"寅", "亥"}): "harmony",
    frozenset({"卯", "戌"}): "harmony",
    frozenset({"辰", "酉"}): "harmony",
    frozenset({"巳", "申"}): "harmony",
    frozenset({"午", "未"}): "harmony",
}

RELATION_COPY = {
    "clash": {
        "ko": {
            "label": "충",
            "detail": "일정 변경이나 조정이 먼저 필요할 수 있어요.",
            "action": "일정과 결정 사이에 여유를 두고, 충돌 가능성이 있는 일은 문서로 확인하세요.",
            "focus": "변경·조정",
        },
        "en": {
            "label": "Clash",
            "detail": "Schedule changes or adjustments may need attention first.",
            "action": "Leave room between plans and decisions, and document points that may conflict.",
            "focus": "Change and adjustment",
        },
    },
    "harmony": {
        "ko": {
            "label": "합",
            "detail": "사람과 일의 연결을 잘 활용하면 좋아요.",
            "action": "협업은 기대보다 역할과 결과물을 먼저 맞추세요.",
            "focus": "협업·연결",
        },
        "en": {
            "label": "Harmony",
            "detail": "Connections between people and work may be especially useful.",
            "action": "Align roles and deliverables before relying on collaboration.",
            "focus": "Connection and coordination",
        },
    },
    "same": {
        "ko": {
            "label": "같은 지지",
            "detail": "익숙한 방식이 반복될 수 있으니 한 번 더 점검해 보세요.",
            "action": "이미 하던 방식이 정말 필요한지 한 번만 다시 확인하세요.",
            "focus": "반복 점검",
        },
        "en": {
            "label": "Same branch",
            "detail": "Familiar patterns may repeat, so check once more before proceeding.",
            "action": "Check once whether the familiar approach is still necessary.",
            "focus": "Pattern review",
        },
    },
}

TERM_LABELS = {
    "ipchun": {"ko": "입춘", "en": "Start of Spring"},
    "gyeongchip": {"ko": "경칩", "en": "Awakening of Insects"},
    "cheongmyeong": {"ko": "청명", "en": "Clear and Bright"},
    "ipha": {"ko": "입하", "en": "Start of Summer"},
    "mangjong": {"ko": "망종", "en": "Grain in Ear"},
    "soseo": {"ko": "소서", "en": "Minor Heat"},
    "ipchu": {"ko": "입추", "en": "Start of Autumn"},
    "baengno": {"ko": "백로", "en": "White Dew"},
    "hallo": {"ko": "한로", "en": "Cold Dew"},
    "ipdong": {"ko": "입동", "en": "Start of Winter"},
    "daeseol": {"ko": "대설", "en": "Major Snow"},
    "sohan": {"ko": "소한", "en": "Minor Cold"},
}


@dataclass(frozen=True)
class _DayContext:
    gan_zhi: str
    source: str
    solar_date: str


@dataclass(frozen=True)
class _MonthContext:
    gan_zhi: str
    term_id: str
    start: SolarTermBoundary
    end: Optional[SolarTermBoundary]
    year_gan_zhi: str
    year_boundary: Optional[SolarTermBoundary]


def _parse_boundary(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def _term_id(boundary: SolarTermBoundary) -> str:
    value = boundary.reference.get("term_id")
    if value in MONTH_OFFSET_BY_TERM_ID:
        return str(value)
    return ""


def _period_term_label(term_id: str, locale: str) -> str:
    return TERM_LABELS.get(term_id, {"ko": term_id, "en": term_id}).get(locale, term_id)


def _resolve_day_context(target_date: date) -> _DayContext:
    record = lookup_lunar_reference_by_solar_date(target_date)
    if record is not None and len(record.day_ganzhi_hanja) >= 2:
        return _DayContext(
            gan_zhi=record.day_ganzhi_hanja,
            source="kasi_lunar_reference",
            solar_date=record.solar_date,
        )

    solar = Solar.fromYmdHms(target_date.year, target_date.month, target_date.day, 12, 0, 0)
    eight_char = solar.getLunar().getEightChar()
    eight_char.setSect(1)
    return _DayContext(
        gan_zhi=eight_char.getDay(),
        source="lunar_python_fallback",
        solar_date=target_date.isoformat(),
    )


def _find_month_context(as_of_local: datetime, timezone_id: str) -> _MonthContext:
    month_boundaries = [
        boundary
        for boundary in list_jie_boundaries_for_years(
            (as_of_local.year - 1, as_of_local.year, as_of_local.year + 1),
            timezone_id=timezone_id,
        )
        if _term_id(boundary) in JIE_TERM_IDS_IN_MONTH_ORDER
    ]
    current_dt = as_of_local.replace(tzinfo=None)
    previous = [
        boundary for boundary in month_boundaries if _parse_boundary(boundary.datetime_text) <= current_dt
    ]
    following = [
        boundary for boundary in month_boundaries if _parse_boundary(boundary.datetime_text) > current_dt
    ]
    if not previous:
        raise ValueError("monthly solar-term boundary is unavailable before the requested date")

    start = max(previous, key=lambda boundary: _parse_boundary(boundary.datetime_text))
    end = min(following, key=lambda boundary: _parse_boundary(boundary.datetime_text)) if following else None
    term_id = _term_id(start)
    if not term_id:
        raise ValueError("monthly solar-term boundary has no supported Jie term id")

    year_boundary = find_jie_boundary_by_term(
        as_of_local.year,
        "ipchun",
        timezone_id=timezone_id,
    )
    if year_boundary is None or current_dt >= _parse_boundary(year_boundary.datetime_text):
        saju_year = as_of_local.year
    else:
        saju_year = as_of_local.year - 1
    year_gan_zhi = year_ganzhi_for_saju_year(saju_year)
    month_gan_zhi = month_ganzhi_for_year_stem(year_gan_zhi[0], term_id)
    return _MonthContext(
        gan_zhi=month_gan_zhi,
        term_id=term_id,
        start=start,
        end=end,
        year_gan_zhi=year_gan_zhi,
        year_boundary=year_boundary,
    )


def _ten_god_for(day_stem: str, target_stem: str) -> str:
    return LunarUtil.SHI_SHEN.get(f"{day_stem}{target_stem}") or "日主"


def _ten_god_group(value: str) -> str:
    return TEN_GOD_GROUP_BY_LABEL.get(localize_ten_god(value, "ko"), "peer")


def _element_label(stem: str, locale: str) -> str:
    element = LunarUtil.WU_XING_GAN.get(stem, "")
    return ELEMENT_LABELS.get(element, {"ko": element, "en": element}).get(locale, element)


def _rule(value: str, locale: str) -> Dict[str, object]:
    group = _ten_god_group(value)
    return RULES[group][locale]  # type: ignore[index]


def _relation_matches(
    *,
    target_branch: str,
    saju_calculation: SajuCalculationResult,
    visible_keys: Sequence[str],
) -> List[Tuple[str, str, str]]:
    matches: List[Tuple[str, str, str]] = []
    priority = {"clash": 0, "harmony": 1, "same": 2}
    for key in visible_keys:
        pillar = saju_calculation.pillars[key]
        natal_branch = pillar.branch
        relation = "same" if target_branch == natal_branch else BRANCH_RELATIONS.get(
            frozenset({target_branch, natal_branch})
        )
        if relation:
            matches.append((relation, key, natal_branch))
    return sorted(matches, key=lambda item: (priority[item[0]], list(visible_keys).index(item[1])))


def _localized_relation(relation: str, locale: str) -> Dict[str, str]:
    return RELATION_COPY[relation][locale]  # type: ignore[index]


def _format_local_datetime(value: str, locale: str) -> str:
    parsed = _parse_boundary(value)
    if locale == "ko":
        return (
            f"{parsed.year}년 {parsed.month}월 {parsed.day}일 "
            f"{parsed.hour:02d}:{parsed.minute:02d}"
        )
    return f"{parsed.strftime('%b')} {parsed.day}, {parsed.year} {parsed.hour:02d}:{parsed.minute:02d}"


def _format_date_label(value: date, locale: str) -> str:
    if locale == "ko":
        return f"{value.year}년 {value.month}월 {value.day}일"
    return f"{value.strftime('%b')} {value.day}, {value.year}"


def _format_month_label(start: SolarTermBoundary, end: Optional[SolarTermBoundary], locale: str) -> str:
    start_dt = _parse_boundary(start.datetime_text)
    if locale == "ko":
        return f"{start_dt.year}년 {start_dt.month}월"
    return f"{start_dt.strftime('%B')} {start_dt.year}"


def _find_current_cycle(
    *,
    cycles: Sequence[LuckCycle],
    as_of_local: datetime,
    birth_time_estimated: bool,
) -> Optional[LuckCycle]:
    if birth_time_estimated:
        return None
    current_dt = as_of_local.replace(tzinfo=None)
    for cycle in cycles:
        if cycle.start_datetime and cycle.change_datetime:
            start = _parse_boundary(cycle.start_datetime)
            change = _parse_boundary(cycle.change_datetime)
            if start <= current_dt < change:
                return cycle
        elif cycle.start_year <= as_of_local.year <= cycle.end_year:
            return cycle
    return None


def _cycle_schema(cycle: Optional[LuckCycle]) -> Optional[PeriodFlowCycle]:
    if cycle is None:
        return None
    return PeriodFlowCycle(
        index=cycle.index,
        gan_zhi=cycle.gan_zhi,
        start_datetime=cycle.start_datetime,
        change_datetime=cycle.change_datetime,
    )


def _common_notes(*, locale: str, target_source: str, estimated: bool = False) -> List[str]:
    if locale == "ko":
        notes = [
            "사건 발생 여부나 점수를 예측하지 않고, 계산된 간지·십성·지지 관계를 행동 점검 문장으로만 연결했습니다.",
            "이 규칙은 v1 참고 기준이며, 결과를 확정적인 예언이나 의사결정의 유일한 근거로 사용하지 마세요.",
        ]
        if target_source == "lunar_python_fallback":
            notes.append("해당 날짜의 기준표가 없어 lunar_python 보정값을 사용했습니다.")
        if estimated:
            notes.append("출생시간 미상으로 시간에 민감한 대운 연결은 표시하지 않았습니다.")
        return notes

    notes = [
        "The flow connects calculated stems, Ten-God signals, and branch relations to action checks; it does not predict events or assign a score.",
        "This is a v1 reference rule set, not a guaranteed prediction or a sole basis for decisions.",
    ]
    if target_source == "lunar_python_fallback":
        notes.append("The checked-in date reference was unavailable, so a lunar_python fallback was used.")
    if estimated:
        notes.append("The birth time is estimated, so the time-sensitive luck-cycle connection is not shown.")
    return notes


def _build_relation_text(
    *,
    relation_match: Optional[Tuple[str, str, str]],
    locale: str,
    target_branch: str,
) -> Tuple[str, List[str], List[str], Optional[PeriodFlowEvidence]]:
    if relation_match is None:
        if locale == "ko":
            return "", [], [], None
        return "", [], [], None

    relation, pillar_key, natal_branch = relation_match
    relation_copy = _localized_relation(relation, locale)
    pillar_label = localize_pillar_label(pillar_key, locale)
    target_label = localize_branch(target_branch, locale)
    natal_label = localize_branch(natal_branch, locale)
    focus = [relation_copy["focus"]]
    actions = [relation_copy["action"]]
    detail = (
        f"{pillar_label} {natal_label}와 대상 지지 {target_label}의 {relation_copy['label']} 관계를 참고했습니다."
        if locale == "ko"
        else f"Compared {pillar_label} {natal_label} with target branch {target_label} as a {relation_copy['label']} relation."
    )
    evidence = PeriodFlowEvidence(
        label="지지 관계" if locale == "ko" else "Branch relation",
        value=relation_copy["label"],
        detail=detail,
        source="period_rule_v1",
    )
    return relation_copy["detail"], focus, actions, evidence


def build_period_flows(
    *,
    payload: SajuPreviewRequest,
    region,
    saju_calculation: SajuCalculationResult,
    as_of: Optional[datetime] = None,
) -> PeriodFlows:
    """Return the current local day's and solar-term month's reference flows."""
    locale = payload.locale
    zone = ZoneInfo(region.tzid)
    if as_of is None:
        as_of_local = datetime.now(zone)
    elif as_of.tzinfo is None:
        as_of_local = as_of.replace(tzinfo=zone)
    else:
        as_of_local = as_of.astimezone(zone)

    day_context = _resolve_day_context(as_of_local.date())
    month_context = _find_month_context(as_of_local, region.tzid)
    day_stem = saju_calculation.pillars["day"].stem
    birth_time_policy = resolve_birth_time_policy(payload)
    visible_keys = birth_time_policy.visible_pillar_keys
    current_cycle = _find_current_cycle(
        cycles=saju_calculation.luck_cycles,
        as_of_local=as_of_local,
        birth_time_estimated=payload.is_birth_time_estimated,
    )

    day_target = day_context.gan_zhi
    day_ten_god = _ten_god_for(day_stem, day_target[0])
    day_rule = _rule(day_ten_god, locale)
    day_relation = _relation_matches(
        target_branch=day_target[1],
        saju_calculation=saju_calculation,
        visible_keys=visible_keys,
    )
    day_relation_text, day_relation_focus, day_relation_actions, day_relation_evidence = _build_relation_text(
        relation_match=day_relation[0] if day_relation else None,
        locale=locale,
        target_branch=day_target[1],
    )
    day_label = _format_date_label(as_of_local.date(), locale)
    localized_day_ten_god = localize_ten_god(day_ten_god, locale)
    localized_day_gan_zhi = localize_ganzhi(day_target, locale)
    if locale == "ko":
        day_summary = str(day_rule["summary"])
        if day_relation_text:
            day_summary = f"{day_summary} {day_relation_text}"
        day_basis = "일진의 천간·일간 십성·지지 관계를 조합한 로컬 규칙 v1"
        day_evidence = [
            PeriodFlowEvidence(
                label="일진",
                value=localized_day_gan_zhi,
                detail=f"{day_label} 현지 날짜의 일진 기준값입니다.",
                source=day_context.source,
            ),
            PeriodFlowEvidence(
                label="일간과의 관계",
                value=localized_day_ten_god,
                detail=(
                    f"출생 일간 {localize_stem(day_stem, locale)}을 기준으로 오늘 천간의 십성을 계산했습니다."
                ),
                source="lunar_python_ten_god_table",
            ),
        ]
    else:
        day_summary = str(day_rule["summary"])
        if day_relation_text:
            day_summary = f"{day_summary} {day_relation_text}"
        day_basis = "Local v1 rules combining the day stem, natal day-stem Ten-God signal, and branch relation"
        day_evidence = [
            PeriodFlowEvidence(
                label="Day pillar",
                value=localized_day_gan_zhi,
                detail=f"Reference value for the local date {day_label}.",
                source=day_context.source,
            ),
            PeriodFlowEvidence(
                label="Relation to day stem",
                value=localized_day_ten_god,
                detail=f"Ten-God signal calculated from the natal day stem {localize_stem(day_stem, locale)}.",
                source="lunar_python_ten_god_table",
            ),
        ]
    if day_relation_evidence:
        day_evidence.append(day_relation_evidence)
    day_notes = _common_notes(
        locale=locale,
        target_source=day_context.source,
        estimated=payload.is_birth_time_estimated,
    )
    daily_flow = PeriodFlow(
        kind="today",
        period_start=as_of_local.date().isoformat(),
        period_end=as_of_local.date().isoformat(),
        period_label=day_label,
        target_gan_zhi=day_target,
        target_element=_element_label(day_target[0], locale),
        primary_signal=localized_day_ten_god,
        headline=str(day_rule["headline"]),
        summary=day_summary,
        focus=list(day_rule["focus"]) + day_relation_focus,  # type: ignore[arg-type]
        actions=list(day_rule["actions"]) + day_relation_actions,  # type: ignore[arg-type]
        evidence=day_evidence,
        basis=day_basis,
        notes=day_notes,
    )

    month_target = month_context.gan_zhi
    month_ten_god = _ten_god_for(day_stem, month_target[0])
    month_rule = _rule(month_ten_god, locale)
    month_relation = _relation_matches(
        target_branch=month_target[1],
        saju_calculation=saju_calculation,
        visible_keys=visible_keys,
    )
    month_relation_text, month_relation_focus, month_relation_actions, month_relation_evidence = _build_relation_text(
        relation_match=month_relation[0] if month_relation else None,
        locale=locale,
        target_branch=month_target[1],
    )
    month_label = _format_month_label(month_context.start, month_context.end, locale)
    localized_month_ten_god = localize_ten_god(month_ten_god, locale)
    localized_month_gan_zhi = localize_ganzhi(month_target, locale)
    localized_year_gan_zhi = localize_ganzhi(month_context.year_gan_zhi, locale)
    month_term_label = _period_term_label(month_context.term_id, locale)
    cycle_label = localize_ganzhi(current_cycle.gan_zhi, locale) if current_cycle else ""
    if locale == "ko":
        month_summary = str(month_rule["summary"])
        if month_relation_text:
            month_summary = f"{month_summary} {month_relation_text}"
        month_basis = "절기 기준 월주·일간 십성·지지 관계와 현재 연운/대운(가능한 경우)을 조합한 로컬 규칙 v1"
        month_evidence = [
            PeriodFlowEvidence(
                label="절기 구간",
                value=month_term_label,
                detail=(
                    f"{_format_local_datetime(month_context.start.datetime_text, locale)}부터 "
                    f"{_format_local_datetime(month_context.end.datetime_text, locale) + ' 직전' if month_context.end else '다음 경계 직전'}까지 "
                    f"{region.tzid} 현지 기준입니다."
                ),
                source=month_context.start.provider,
            ),
            PeriodFlowEvidence(
                label="이번 달 월주",
                value=localized_month_gan_zhi,
                detail=f"현재 절기 구간의 월주이며, 일간 기준 {localized_month_ten_god} 신호를 확인했습니다.",
                source="solar_term_month_pillar_rule",
            ),
            PeriodFlowEvidence(
                label="연운 기준",
                value=localized_year_gan_zhi,
                detail="입춘 경계를 기준으로 해당 절기 구간의 연주를 계산했습니다.",
                source=month_context.year_boundary.provider if month_context.year_boundary else "solar_term_month_pillar_rule",
            ),
        ]
    else:
        month_summary = str(month_rule["summary"])
        if month_relation_text:
            month_summary = f"{month_summary} {month_relation_text}"
        month_basis = "Local v1 rules combining the solar-term month pillar, day-stem Ten-God signal, branch relation, and current year/cycle when available"
        month_evidence = [
            PeriodFlowEvidence(
                label="Solar-term window",
                value=month_term_label,
                detail=(
                    f"Local time from {_format_local_datetime(month_context.start.datetime_text, locale)} until "
                    f"{_format_local_datetime(month_context.end.datetime_text, locale) + ' (exclusive)' if month_context.end else 'the next boundary'}."
                ),
                source=month_context.start.provider,
            ),
            PeriodFlowEvidence(
                label="Month pillar",
                value=localized_month_gan_zhi,
                detail=f"Month pillar for the current solar-term window; {localized_month_ten_god} relative to the natal day stem.",
                source="solar_term_month_pillar_rule",
            ),
            PeriodFlowEvidence(
                label="Annual pillar",
                value=localized_year_gan_zhi,
                detail="Annual pillar selected using the Start of Spring boundary.",
                source=month_context.year_boundary.provider if month_context.year_boundary else "solar_term_month_pillar_rule",
            ),
        ]
    if month_relation_evidence:
        month_evidence.append(month_relation_evidence)
    if current_cycle:
        cycle_period = (
            f"{_format_local_datetime(current_cycle.start_datetime, locale)} ~ "
            f"{_format_local_datetime(current_cycle.change_datetime, locale)}"
            if current_cycle.start_datetime and current_cycle.change_datetime
            else ""
        )
        month_evidence.append(
            PeriodFlowEvidence(
                label="현재 대운" if locale == "ko" else "Current luck cycle",
                value=cycle_label,
                detail=cycle_period or ("출생시간 기반 대운 구간입니다." if locale == "ko" else "Cycle window calculated from the birth time."),
                source="luck_cycle_calculation",
            )
        )
    month_notes = _common_notes(
        locale=locale,
        target_source=month_context.start.provider,
        estimated=payload.is_birth_time_estimated,
    )
    monthly_flow = PeriodFlow(
        kind="month",
        period_start=month_context.start.datetime_text,
        period_end=month_context.end.datetime_text if month_context.end else "",
        period_label=month_label,
        target_gan_zhi=month_target,
        target_element=_element_label(month_target[0], locale),
        primary_signal=localized_month_ten_god,
        headline=str(month_rule["headline"]),
        summary=month_summary,
        focus=list(month_rule["focus"]) + month_relation_focus,  # type: ignore[arg-type]
        actions=list(month_rule["actions"]) + month_relation_actions,  # type: ignore[arg-type]
        evidence=month_evidence,
        basis=month_basis,
        notes=month_notes,
        current_luck_cycle=_cycle_schema(current_cycle),
    )

    return PeriodFlows(
        as_of=as_of_local.isoformat(),
        timezone_id=region.tzid,
        today=daily_flow,
        month=monthly_flow,
    )
