"""Facts-first question readings, isolated from legacy topic and LLM policies.

These answers identify chart facts and explain vocabulary. They do not support
meeting/employment windows, event probabilities, fortune ranks or luck scores.
The calculation adapter is injected into the service boundary; wording never
recalculates the birth chart and callers cannot supply trusted facts.
"""

from collections import OrderedDict
from datetime import datetime, timezone
from hashlib import sha256
import json
from threading import RLock
from time import monotonic
from typing import Callable, Dict, List, Optional, Tuple

from lunar_python.util import LunarUtil

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python 3.8
    from backports.zoneinfo import ZoneInfo

from app.config import settings
from app.domain.saju.interpretation import ReadingBasisExplanation
from app.domain.saju.localization import (
    STEM_LABELS,
    localize_branch, localize_ganzhi, localize_pillar_label, localize_special_star_label,
    localize_stem, localize_ten_god,
)
from app.domain.saju.pydantic_compat import model_copy_compat, model_to_dict
from app.domain.saju.question_schemas import (
    QuestionFact, QuestionFlow, QuestionOption, QuestionSection, QuestionVersions,
    SajuBasicResponse, SajuQuestionRequest, SajuQuestionResponse,
)
from app.domain.saju.schemas import SajuPreviewRequest, SajuPreviewResponse
from app.domain.saju.question_followups import ANSWER_MEANINGS, VERSION as FOLLOWUP_VERSION, select_followups
from app.domain.saju.services.canonical_year_month import year_ganzhi_for_saju_year
from app.domain.saju.services.region_catalog import find_region_by_id
from app.domain.saju.services.solar_term_boundaries import find_jie_boundary_by_term


# Independent versions above cover facts, scope/guards, editorial copy and shape.
# These are source-code project policies; no expert-reviewed prediction is claimed.
QUESTION_CATALOG = (
    ("chart.pillars", "내 사주팔자 글자는 무슨 뜻이야?", "태어난 해·달·날·시간의 네 자리를 나눠볼게.",
     "What do my four pillars represent?", "Read the year, month, day and hour positions separately."),
    ("luck.current_next", "다음 운의 구간은 언제 시작돼?", "지금과 다음 구간의 날짜와 의미를 확인해봐.",
     "When does my current luck cycle change?", "Compare the dates and characters of your current and next cycles."),
    ("stars.dohwa", "내 사주에 도화가 있어?", "도화의 종류와 실제 잡힌 위치를 볼 수 있어.",
     "Does my chart have Peach Blossom?", "See the distinct methods and matching positions."),
    ("wealth.locations", "돈과 관련된 표시는 어디에 있어?", "겉에 보이는 글자와 안쪽에 든 글자를 확인해봐.",
     "Where are the wealth stars in my chart?", "Check the visible stems and hidden stems separately."),
    ("period.this_year", "올해는 어떤 주제가 들어와?", "올해의 글자가 내 사주에서 뜻하는 내용을 확인해봐.",
     "Which annual characters enter my chart?", "Check the solar-term year and its relation to your day stem."),
)
CATEGORY_BY_QUESTION = {"chart.pillars": "core", "stars.dohwa": "love", "wealth.locations": "wealth",
                        "period.this_year": "career", "luck.current_next": "luck_flow"}
TEN_GOD_MEANINGS = {
    "비견": ("나와 같은 오행·같은 음양", "the same element and polarity as the day stem"),
    "겁재": ("나와 같은 오행·다른 음양", "the same element with opposite polarity"),
    "식신": ("내가 생하는 오행·같은 음양", "the element produced by the day stem, with the same polarity"),
    "상관": ("내가 생하는 오행·다른 음양", "the element produced by the day stem, with opposite polarity"),
    "편재": ("내가 극하는 오행·같은 음양", "the element controlled by the day stem, with the same polarity"),
    "정재": ("내가 극하는 오행·다른 음양", "the element controlled by the day stem, with opposite polarity"),
    "편관": ("나를 극하는 오행·같은 음양", "the element controlling the day stem, with the same polarity"),
    "정관": ("나를 극하는 오행·다른 음양", "the element controlling the day stem, with opposite polarity"),
    "편인": ("나를 생하는 오행·같은 음양", "the element producing the day stem, with the same polarity"),
    "정인": ("나를 생하는 오행·다른 음양", "the element producing the day stem, with opposite polarity"),
}
CACHE_TTL_SECONDS = 120
CACHE_MAX_ITEMS = 48
_CALCULATIONS: OrderedDict = OrderedDict()
_ANSWERS: OrderedDict = OrderedDict()
_CACHE_LOCK = RLock()


class QuestionUnavailable(ValueError):
    """No supported answer is available under the supplied calculation policy."""


def _digest(value) -> str:
    return sha256(json.dumps(value, ensure_ascii=True, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def _cache_get(cache, key):
    with _CACHE_LOCK:
        entry = cache.get(key)
        if entry is None:
            return None
        created, value = entry
        if monotonic() - created >= CACHE_TTL_SECONDS:
            del cache[key]
            return None
        cache.move_to_end(key)
        return model_copy_compat(value, deep=True)


def _cache_put(cache, key, value):
    with _CACHE_LOCK:
        now = monotonic()
        expired = [cached_key for cached_key, (created, _) in cache.items() if now - created >= CACHE_TTL_SECONDS]
        for cached_key in expired:
            del cache[cached_key]
        cache[key] = (now, model_copy_compat(value, deep=True))
        cache.move_to_end(key)
        while len(cache) > CACHE_MAX_ITEMS:
            cache.popitem(last=False)


def clear_question_caches() -> None:
    with _CACHE_LOCK:
        _CALCULATIONS.clear()
        _ANSWERS.clear()


def _now(as_of: Optional[datetime]) -> datetime:
    current = as_of or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("question as_of must have a timezone")
    return current


def _calculation_key(payload: SajuPreviewRequest, as_of: datetime) -> str:
    # The instant is not trusted from HTTP. The adapter receives a server clock.
    # Existing period facts use a region-local date; UTC date is an additional key.
    tzid = find_region_by_id(payload.region_id).tzid
    return _digest({
        "input": model_to_dict(payload), "as_of_day": as_of.astimezone(timezone.utc).date().isoformat(),
        "local_day": as_of.astimezone(ZoneInfo(tzid)).date().isoformat(), "timezone_id": tzid,
        "versions": model_to_dict(QuestionVersions()),
        "canonical": settings.use_canonical_year_month_pillars,
    })


def _prepare(payload, trace_id, service_name, as_of, calculate) -> SajuPreviewResponse:
    key = _calculation_key(payload, as_of)
    response = _cache_get(_CALCULATIONS, key)
    if response is not None:
        local_now = as_of.astimezone(ZoneInfo(response.region.tzid))
        month_start = _parse_cycle_time(response.period_flows.month.period_start, response.region.tzid)
        month_end = _parse_cycle_time(response.period_flows.month.period_end, response.region.tzid)
        if month_start is None or month_end is None or not month_start <= local_now < month_end:
            response = None
    if response is None:
        response = calculate(payload=payload, trace_id=trace_id, debug_requested=False,
                             service_name=service_name, report_mode="none", as_of=as_of)
        _cache_put(_CALCULATIONS, key, response)
    response.trace_id = trace_id
    return response


def _critical(response) -> bool:
    return any(flag.severity == "critical" for flag in response.result.uncertainty_summary)


def _notices(response, locale, question_id=None) -> List[str]:
    ko = locale == "ko"
    notices = []
    if any(flag.code == "midnight_rule_changes_day_pillar" for flag in response.result.uncertainty_summary):
        notices.append("날짜를 바꾸는 기준에 따라 태어난 날의 글자가 달라져. 아래는 지금 선택한 기준에서 표시한 사주의 결과야." if ko else
                       "The birth-day characters differ between day-change conventions. These results use the chart displayed under the selected convention.")
    elif _critical(response) and response.manse.meta.hour_pillar_enabled:
        notices.append("출생 시각의 경계와 날짜 구분 방식에 따라 명식이 달라질 수 있어. 아래는 현재 선택된 계산 기준의 사실이야." if ko else
                       "Time boundaries or day-change conventions can alter this chart. The facts below use the currently selected calculation policy.")
    if not response.manse.meta.hour_pillar_enabled:
        notices.append("태어난 시간을 몰라 태어난 날의 글자도 확정하지 못했어. 지금은 선택한 날짜로 임시 표시한 사주를 읽었어. 시주와 대운은 제외했어." if ko else
                       "Birth time is unknown, so the birth-day characters are also unconfirmed. This reads a provisional chart under the selected date. Hour pillar and luck cycles are excluded.")
    if question_id in {None, "luck.current_next"} and not _critical(response) and any(
        flag.code == "luck_cycle_start_age_changed" for flag in response.result.uncertainty_summary
    ):
        notices.append("대운 시점은 계산 기준에 따라 달라질 수 있어. 표시한 날짜는 현재 선택한 기준으로 계산했어." if ko else
                       "Luck-cycle timing can differ between calculation policies. These dates use the currently selected policy.")
    return notices


def _parse_cycle_time(value: Optional[str], tzid: str) -> Optional[datetime]:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=ZoneInfo(tzid))


def _cycles(response, as_of) -> Tuple[object, object]:
    if not response.manse.luck_cycles_enabled or not response.manse.meta.hour_pillar_enabled:
        return None, None
    cycles = response.manse.luck_cycles
    for index, cycle in enumerate(cycles):
        start = _parse_cycle_time(cycle.start_datetime, response.region.tzid)
        end = _parse_cycle_time(cycle.change_datetime, response.region.tzid)
        if start is not None and end is not None and start <= as_of < end:
            following = cycles[index + 1] if index + 1 < len(cycles) else None
            if following is not None and following.start_datetime and following.change_datetime:
                return cycle, following
    return None, None


def supported_questions(response, locale: str, as_of: datetime) -> List[QuestionOption]:
    items = []
    current, following = _cycles(response, as_of)
    for question_id, ko_title, ko_description, en_title, en_description in QUESTION_CATALOG:
        if question_id == "luck.current_next" and (current is None or following is None):
            continue
        items.append(QuestionOption(id=question_id, category=CATEGORY_BY_QUESTION[question_id], title=ko_title if locale == "ko" else en_title,
                                    description=ko_description if locale == "ko" else en_description))
    from app.domain.saju.distinctive_reading import build_distinctive_reading, distinctive_questions
    reading = build_distinctive_reading(base=response, locale=locale)
    items.extend(QuestionOption(**q) for q in distinctive_questions(reading, locale))
    return items


def create_basic_reading(*, payload: SajuPreviewRequest, trace_id: str, service_name: str,
                         calculate: Callable, as_of: Optional[datetime] = None) -> SajuBasicResponse:
    current = _now(as_of)
    base = _prepare(payload, trace_id, service_name, current, calculate)
    return assemble_basic_reading(base=base, locale=payload.locale, as_of=current)


def assemble_basic_reading(*, base: SajuPreviewResponse, locale: str, as_of: datetime) -> SajuBasicResponse:
    # Import at the composition boundary: the overview reuses the domain fact
    # helpers below without making question generation depend on overview copy.
    from app.domain.saju.basic_reading import build_basic_overview

    return SajuBasicResponse(**model_to_dict(base), basic_reading=build_basic_overview(
        base=base, locale=locale, as_of=as_of), question_flow=QuestionFlow(
        as_of=as_of.isoformat(), questions=supported_questions(base, locale, as_of),
        notices=_notices(base, locale)))


def _pillars(base, locale, facts, sections):
    ko = locale == "ko"
    lines = []
    for key in base.manse.meta.pillar_order:
        pillar = getattr(base.manse.pillars, key)
        if not pillar.enabled:
            continue
        label = localize_pillar_label(key, locale)
        lines.append(f"{label} {_ganzhi(pillar.gan_zhi, locale)}")
        _fact(facts, "chart." + key, label, pillar.gan_zhi, "manse.pillars." + key + ".gan_zhi")
    answer = " · ".join(lines)
    memo = ("년주는 태어난 해, 월주는 절기에 따른 달, 일주는 태어난 날, 시주는 태어난 시각의 자리입니다. 각 자리는 천간과 지지 두 글자로 구성됩니다. 일간은 일주의 첫 글자입니다." if ko else
            "The year, solar-term month, day and hour pillars each contain a stem and a branch. The day stem is the first character of the day pillar.")
    return answer, memo, {"_memo_facts": [" · ".join(lines[index:index + 2]) for index in range(0, len(lines), 2)], "scope": "calculated_pillars"}


def _fact(facts, fact_id, label, value, path):
    facts.append(QuestionFact(id=fact_id, label=label, value=value, source_path=path))


def _section(sections, section_id, ko_title, en_title, text, ko):
    sections.append(QuestionSection(id=section_id, title=ko_title if ko else en_title, text=text))


def _ganzhi(value, locale):
    return f"{localize_ganzhi(value, locale)}({value})"


def _canonical_stem(target_stem):
    for hanja, labels in STEM_LABELS.items():
        if target_stem in labels.values():
            return hanja
    return target_stem


def _ten_god(day_stem, target_stem, locale):
    target_stem = _canonical_stem(target_stem)
    raw = LunarUtil.SHI_SHEN.get(day_stem + target_stem)
    if raw is None:
        raise QuestionUnavailable("Ten-god relation is unavailable")
    canonical = localize_ten_god(raw, "ko")
    if canonical not in TEN_GOD_MEANINGS:
        raise QuestionUnavailable("Ten-god relation is not registered")
    return canonical, localize_ten_god(raw, locale)


def _date_label(value, locale):
    parsed = datetime.fromisoformat(value)
    return f"{parsed.year}년 {parsed.month}월 {parsed.day}일" if locale == "ko" else parsed.strftime("%b %d, %Y")


def _positions(count, modifier=""):
    return f"{count} {modifier + ' ' if modifier else ''}{'position' if count == 1 else 'positions'}"


def _branch_label(value, locale):
    return f"{localize_branch(value, locale)}({value})"


def _wealth(base, locale, facts, sections):
    ko = locale == "ko"
    visible, hidden = [], []
    derived_relations = []
    visible_relations = []
    for key in base.manse.meta.visible_pillar_keys:
        pillar = getattr(base.manse.pillars, key)
        label = localize_pillar_label(key, locale)
        _fact(facts, "wealth." + key + ".stem", label, pillar.stem, "manse.pillars." + key + ".stem")
        _fact(facts, "wealth." + key + ".branch", label, pillar.branch, "manse.pillars." + key + ".branch")
        _fact(facts, "wealth." + key + ".stem_ten_god", label, pillar.stem_ten_god, "manse.pillars." + key + ".stem_ten_god")
        _fact(facts, "wealth." + key + ".hidden_stems", label, pillar.hidden_stems, "manse.pillars." + key + ".hidden_stems")
        canonical_visible, visible_relation = _ten_god(base.manse.meta.day_master, pillar.stem, locale)
        visible_relations.append({"pillar_key": key, "stem": pillar.stem, "ten_god": canonical_visible,
                                  "reported_ten_god": pillar.stem_ten_god})
        if canonical_visible in {"정재", "편재"}:
            visible.append(f"{label} {pillar.stem} · {visible_relation}")
        # Public hidden_stems uses the project's explicit stem table. Its order
        # is not the lunar_python branch_ten_gods order and some lengths differ.
        for stem in pillar.hidden_stems:
            canonical, relation = _ten_god(base.manse.meta.day_master, stem, locale)
            derived_relations.append({"pillar_key": key, "stem": stem, "ten_god": canonical})
            if canonical in {"정재", "편재"}:
                display_stem = localize_stem(_canonical_stem(stem), locale)
                hidden.append(f"{label} {pillar.branch} 속 {display_stem} · {relation}" if ko else
                              f"{label}, {display_stem} inside {pillar.branch} · {relation}")
    if ko:
        answer = f"돈과 보상에 연결해 보는 글자는 겉에 {len(visible)}곳, 안쪽에 {len(hidden)}곳 있어."
        if not visible and hidden:
            answer += " 겉에는 없어도 안쪽에는 있어."
        if not base.manse.meta.hour_pillar_enabled:
            answer = "확인한 연주·월주·일주에서, " + answer
        visible_text = " / ".join(visible) if visible else "겉에 적힌 천간에서는 정재·편재에 해당하는 글자가 잡히지 않아."
        hidden_text = " / ".join(hidden) if hidden else (
            "확인한 연주·월주·일주의 지장간에서는 정재·편재에 해당하는 글자가 잡히지 않아."
            if not base.manse.meta.hour_pillar_enabled else "지장간에서도 정재·편재에 해당하는 글자는 잡히지 않아.")
        meaning = "재성은 일간이 극하는 오행을 부르는 이름이야. 같은 음양이면 편재, 다른 음양이면 정재로 구분해. 지장간은 이 만세력의 표시 기준으로 확인했어. 개수는 기둥 수가 아니라 글자 자리 수야. 같은 기둥의 서로 다른 재성 글자나 서로 다른 기둥의 같은 글자는 각 자리로 기록해."
        memo = "겉글자와 표시된 지장간을 모두 선택한 일간과 같은 십성 표로 개별 대조하여 정재·편재를 추출했습니다. 원본 천간 분류는 사실 자료에 보존하고 관계 설명에는 재대조한 분류를 사용합니다. 천간 위치와 지장간 위치를 별도 집계했으며, 이 개수는 재물 강약·실제 소득의 산식이 아닙니다."
    else:
        answer = f"Money-related characters appear in {_positions(len(visible), 'visible stem')} and {_positions(len(hidden), 'hidden stem')}."
        if not visible and hidden:
            answer += " Absent on the surface, present inside."
        if not base.manse.meta.hour_pillar_enabled:
            answer = "I checked the year, month and day pillars: " + answer[0].lower() + answer[1:]
        visible_text = " / ".join(visible) if visible else "No Direct or Indirect Wealth star appears in the visible stems."
        hidden_text = " / ".join(hidden) if hidden else (
            "No Direct or Indirect Wealth stem is found in the checked year, month and day pillars' hidden stems."
            if not base.manse.meta.hour_pillar_enabled else "No Direct or Indirect Wealth stem is found in the hidden stems.")
        meaning = "A wealth star is the element controlled by the day stem: same polarity gives Indirect Wealth, opposite polarity gives Direct Wealth. Hidden stems use this chart's display convention. The unit is a stem position, not a pillar: different wealth stems within one pillar, or repeated stems across pillars, each occupy separate positions."
        memo = "Visible and hidden stems were compared with the selected day stem using the same ten-god table. Original reported labels remain in the facts; these descriptions use the derived relations. Position counts are separated; they are not a measure of wealth strength or actual income."
    _section(sections, "visible", "겉에 있는 재성", "Visible wealth stems", visible_text, ko)
    _section(sections, "hidden", "지장간에 있는 재성", "Hidden wealth stems", hidden_text, ko)
    _section(sections, "meaning", "어떤 글자를 센 거야?", "What was counted?", meaning, ko)
    _fact(facts, "wealth.hidden_relations", "지장간 십성" if ko else "Hidden stem relations", derived_relations, "source_context.wealth_relations")
    _fact(facts, "wealth.visible_relations", "천간 십성 대조" if ko else "Derived visible stem relations", visible_relations, "source_context.visible_wealth_relations")
    return answer, memo, {"wealth_relations": derived_relations, "visible_wealth_relations": visible_relations, "_memo_facts": [
        (f"일간: {base.manse.meta.day_master}" if ko else f"Day stem: {base.manse.meta.day_master}"),
        (f"천간 재성 위치: {len(visible)}곳" if ko else f"Visible wealth positions: {len(visible)}"),
        (f"지장간 재성 위치: {len(hidden)}곳" if ko else f"Hidden wealth positions: {len(hidden)}")]}


def _dohwa(base, locale, facts, sections):
    ko = locale == "ko"
    groups = {"hamji": set(), "wangji": set(), "mokyok": set()}
    visible = set(base.manse.meta.visible_pillar_keys)
    method_lines = []
    method_entries = []
    for index, star in enumerate(base.manse.special_stars):
        group = "hamji" if star.key in {"dohwa-year-branch", "dohwa-day-branch"} else {"wangji-dohwa": "wangji", "mokyok-dohwa": "mokyok"}.get(star.key)
        if group is None:
            continue
        positions = {match.pillar_key for match in star.matches if match.pillar_key in visible}
        groups[group].update(positions)
        label = ("함지도화" if ko else "Hamji Peach Blossom") if group == "hamji" else localize_special_star_label(star.key, star.label, locale)
        anchor = ("연지 기준" if star.key == "dohwa-year-branch" else "일지 기준") if ko else ("year-branch anchor" if star.key == "dohwa-year-branch" else "day-branch anchor")
        locations = ", ".join(localize_pillar_label(key, locale) for key in base.manse.meta.pillar_order if key in positions)
        targets = "·".join(_branch_label(value, locale) for value in star.target_values)
        if group == "hamji":
            method_lines.append(f"{anchor}: {_branch_label(star.anchor_value, locale)}에서 찾는 글자는 {targets}. {locations or '명식에 없음'}." if ko else
                                f"{anchor}: {_branch_label(star.anchor_value, locale)} looks for {targets}; {locations or 'not present' }.")
        _fact(facts, "stars." + star.key + ".matches", label, [model_to_dict(match) for match in star.matches], f"manse.special_stars[{index}].matches")
        _fact(facts, "stars." + star.key + ".method", label, star.method_id, f"manse.special_stars[{index}].method_id")
        _fact(facts, "stars." + star.key + ".targets", label, star.target_values, f"manse.special_stars[{index}].target_values")
        _fact(facts, "stars." + star.key + ".anchor", label, star.anchor_value, f"manse.special_stars[{index}].anchor_value")
        _fact(facts, "stars." + star.key + ".active", label, star.active, f"manse.special_stars[{index}].active")
        _fact(facts, "stars." + star.key + ".source_count", label, star.count, f"manse.special_stars[{index}].count")
        method_entries.append({"key": star.key, "method_id": star.method_id, "positions": sorted(positions)})
    def positions_text(name):
        positions = groups[name]
        labels = "·".join(localize_pillar_label(key, locale) for key in base.manse.meta.pillar_order if key in positions)
        return (f"{len(positions)}곳" + (f" — {labels}" if labels else "")) if ko else _positions(len(positions)) + (f" — {labels}" if labels else "")
    if ko:
        intro = "기준에 따라 다르게 잡혀." if groups["hamji"] != groups["wangji"] else "도화는 보는 기준이 나뉘어."
        answer = f"{intro} 좁은 기준: {positions_text('hamji')}. 넓은 기준: {positions_text('wangji')}. 별도 기준: {positions_text('mokyok')}."
        hamji = " ".join(method_lines) + " 연지·일지 기준이 같은 위치를 잡으면 그 위치는 한 번만 세었어."
        extended = f"왕지도화: {positions_text('wangji')}. 자·오·묘·유가 있는지 보는 넓은 기준이야. 목욕도화: {positions_text('mokyok')}. 일간의 12운성 목욕지를 확인하는 별도 기준이고."
        memo = "연지·일지 기준 함지도화의 일치 위치를 합집합으로 집계했습니다. 왕지 및 목욕 기준은 별도로 기록하고 위치 분류 태그는 추가 개수로 합산하지 않았습니다."
    else:
        intro = "The methods find different positions." if groups["hamji"] != groups["wangji"] else "Peach Blossom uses separate methods."
        answer = f"{intro} Narrower method: {positions_text('hamji')}. Broader method: {positions_text('wangji')}. Separate method: {positions_text('mokyok')}."
        hamji = " ".join(method_lines) + " If both anchor methods match the same pillar, that position is counted once."
        extended = f"Wangji: {positions_text('wangji')}, using the branches 子·午·卯·酉. Bath Peach Blossom: {positions_text('mokyok')}, using the day stem's Bath position in the twelve-stage cycle."
        memo = "Hamji positions are the union of the year- and day-anchor matches. Wangji and Bath are recorded separately; location-category tags are not counted as extra stars."
    _section(sections, "hamji", "함지도화부터 보면", "Start with Hamji", hamji, ko)
    _section(sections, "extended", "함께 보이는 다른 기준", "Other separate methods", extended, ko)
    return answer, memo, {"dohwa_methods": method_entries, "_memo_facts": [
        ("함지도화: " if ko else "Hamji: ") + positions_text("hamji"),
        ("왕지도화: " if ko else "Wangji: ") + positions_text("wangji"),
        ("목욕도화: " if ko else "Bath: ") + positions_text("mokyok")]}


def _luck(base, locale, facts, sections, as_of):
    ko = locale == "ko"
    current, following = _cycles(base, as_of)
    if current is None or following is None:
        raise QuestionUnavailable("Current and next precise luck cycles are unavailable")
    day = base.manse.meta.day_master
    current_relation, current_label = _ten_god(day, current.gan_zhi[0], locale)
    next_relation, next_label = _ten_god(day, following.gan_zhi[0], locale)
    date_label = _date_label(current.change_datetime, locale)
    for prefix, cycle in (("current", current), ("next", following)):
        position = next(index for index, item in enumerate(base.manse.luck_cycles) if item.index == cycle.index)
        for field in ("gan_zhi", "start_datetime", "change_datetime"):
            _fact(facts, "luck." + prefix + "." + field, prefix, getattr(cycle, field), f"manse.luck_cycles[{position}].{field}")
    _fact(facts, "luck.current_stem_ten_god", "current", current_relation, "source_context.current_stem_ten_god")
    _fact(facts, "luck.next_stem_ten_god", "next", next_relation, "source_context.next_stem_ten_god")
    if ko:
        answer = f"현재 {_ganzhi(current.gan_zhi, locale)} 대운은 {date_label}에 다음 {_ganzhi(following.gan_zhi, locale)} 대운으로 바뀌어."
        current_text = f"지금 구간은 {_date_label(current.start_datetime, locale)}부터 {_date_label(current.change_datetime, locale)} 교체 시각 전까지야. 일간 {day} 기준으로 본 대운 천간 {current.gan_zhi[0]}의 십성은 {current_label}에 해당해. 둘은 {TEN_GOD_MEANINGS[current_relation][0]} 관계야."
        next_text = f"다음 구간은 {_date_label(following.start_datetime, locale)}부터 {_date_label(following.change_datetime, locale)} 교체 시각 전까지야. 천간이 {current.gan_zhi[0]}에서 {following.gan_zhi[0]} 글자로, 지지가 {current.gan_zhi[1]}에서 {following.gan_zhi[1]} 글자로 바뀌어. 다음 천간의 십성은 {next_label}에 해당해."
        memo = f"대운의 정밀 시작·교체 시각으로 현재 구간을 선택했습니다. 일간 대비 대운 천간의 십성 관계를 비교했습니다. 표시 날짜는 출생지 시간대({base.region.tzid}) 기준이며 교체 시각 전까지를 현재 구간으로 봅니다."
    else:
        answer = f"Your current {_ganzhi(current.gan_zhi, locale)} cycle changes to {_ganzhi(following.gan_zhi, locale)} on {date_label}."
        current_text = f"The interval runs from {_date_label(current.start_datetime, locale)} until the change time on {_date_label(current.change_datetime, locale)}. Its stem {current.gan_zhi[0]} is {current_label} relative to day stem {day}: {TEN_GOD_MEANINGS[current_relation][1]}."
        next_text = f"The next interval runs from {_date_label(following.start_datetime, locale)} until the change time on {_date_label(following.change_datetime, locale)}. The stem changes from {current.gan_zhi[0]} to {following.gan_zhi[0]} and the branch from {current.gan_zhi[1]} to {following.gan_zhi[1]}. Its stem relation is {next_label}."
        memo = f"The active cycle was selected by precise start/change datetimes. Stem ten-god relations were compared. Dates use the birth location's timezone ({base.region.tzid}); the current interval excludes its exact change time."
    _section(sections, "current", "지금 구간", "Current interval", current_text, ko)
    _section(sections, "next", "다음 구간", "Next interval", next_text, ko)
    return answer, memo, {"current_cycle_index": current.index, "next_cycle_index": following.index,
        "current_stem_ten_god": current_relation, "next_stem_ten_god": next_relation, "_memo_facts": [
        ("현재 대운: " if ko else "Current cycle: ") + _ganzhi(current.gan_zhi, locale),
        ("교체 시각: " if ko else "Change datetime: ") + current.change_datetime,
        ("다음 대운: " if ko else "Next cycle: ") + _ganzhi(following.gan_zhi, locale)]}


def _annual(base, locale, facts, sections, as_of):
    ko = locale == "ko"
    local = as_of.astimezone(ZoneInfo(base.region.tzid))
    boundary = find_jie_boundary_by_term(local.year, "ipchun", timezone_id=base.region.tzid)
    if boundary is None:
        raise QuestionUnavailable("Solar-term year boundary is unavailable")
    year_start = datetime.fromisoformat(boundary.datetime_text).replace(tzinfo=ZoneInfo(base.region.tzid))
    saju_year = local.year if local >= year_start else local.year - 1
    actual_start = boundary if saju_year == local.year else find_jie_boundary_by_term(saju_year, "ipchun", timezone_id=base.region.tzid)
    actual_end = find_jie_boundary_by_term(saju_year + 1, "ipchun", timezone_id=base.region.tzid)
    if actual_start is None or actual_end is None:
        raise QuestionUnavailable("Solar-term year interval is unavailable")
    gan_zhi = year_ganzhi_for_saju_year(saju_year)
    canonical, signal = _ten_god(base.manse.meta.day_master, gan_zhi[0], locale)
    annual = {"gan_zhi": gan_zhi, "saju_year": saju_year, "start_datetime": actual_start.datetime_text,
              "change_datetime": actual_end.datetime_text, "stem_ten_god": canonical,
              "boundary_provider": actual_start.provider}
    for field, value in annual.items():
        _fact(facts, "annual." + field, field, value, "source_context.annual." + field)
    if ko:
        answer = f"올해 들어온 글자는 {localize_ganzhi(gan_zhi, locale)}야. 네 사주와 비교할 때 붙는 관계 이름은 ‘{signal}’이야."
        interval = f"올해 사주년은 {_date_label(actual_start.datetime_text, locale)} 입춘부터 {_date_label(actual_end.datetime_text, locale)} 다음 입춘 전까지야. 양력 1월 1일에 글자가 바뀌는 방식이 아니라 입춘을 경계로 했어."
        relation = f"네 일간은 {base.manse.meta.day_master}, 올해 천간은 {gan_zhi[0]}이야. 둘의 관계는 {TEN_GOD_MEANINGS[canonical][0]}이고, 십성은 {signal}에 해당해. 일간이 다른 사람은 같은 해도 다른 십성으로 읽을 수 있어."
        memo = f"절입 자료의 입춘 시각을 기준으로 사주년을 선택했습니다. 원국 일간과 연간의 십성 관계를 표시했습니다. 정밀 시각은 출생지 시간대({base.region.tzid}) 기준입니다."
    else:
        answer = f"This year's characters are {localize_ganzhi(gan_zhi, locale)}. The comparison name relative to your chart is {signal}."
        interval = f"The interval starts at Ipchun on {_date_label(actual_start.datetime_text, locale)} and ends at the next Ipchun on {_date_label(actual_end.datetime_text, locale)}. The year changes at Ipchun, rather than January 1."
        relation = f"Your day stem is {base.manse.meta.day_master}; this year's stem is {gan_zhi[0]}. Their relationship is {TEN_GOD_MEANINGS[canonical][1]}, classified as {signal}. A different day stem can give a different relation for the same year."
        memo = f"The annual pillar was selected using Ipchun boundaries from the solar-term data. The annual-stem/day-stem relation is shown. Exact times use the birth location's timezone ({base.region.tzid})."
    _section(sections, "interval", "올해는 어디서부터야?", "Year boundary", interval, ko)
    _section(sections, "relation", "같은 해도 다르게 읽는 이유", "Why the same year differs", relation, ko)
    return answer, memo, {"annual": annual, "_memo_facts": [
        ("입춘 기준 해: " if ko else "Solar-term year: ") + _ganzhi(gan_zhi, locale),
        ("올해 구간: " if ko else "Year interval: ") + actual_start.datetime_text + " ~ " + actual_end.datetime_text,
        ("일간 대비 연간 십성: " if ko else "Annual stem relation: ") + signal]}


def create_question_reading(*, payload: SajuQuestionRequest, trace_id: str, service_name: str,
                            calculate: Callable, as_of: Optional[datetime] = None) -> SajuQuestionResponse:
    current = _now(as_of)
    base = _prepare(payload.input, trace_id, service_name, current, calculate)
    options = {option.id: option for option in supported_questions(base, payload.input.locale, current)}
    if payload.question_id not in options:
        raise QuestionUnavailable("This question is unavailable for the supplied birth information")
    facts = []
    sections = []
    _fact(facts, "natal.day_master", "일간" if payload.input.locale == "ko" else "Day stem",
          base.manse.meta.day_master, "manse.meta.day_master")
    if payload.question_id.startswith("features."):
        from app.domain.saju.distinctive_reading import build_distinctive_reading, answer_distinctive_question
        reading = build_distinctive_reading(base=base, locale=payload.input.locale)
        data, feature_facts, memo = answer_distinctive_question(reading, payload.question_id, payload.input.locale)
        facts.extend(QuestionFact(id=f["id"], label=f["id"], value=f["value"], source_path=f["source_path"]) for f in feature_facts)
        answer = data["answer"]
        sections.append(QuestionSection(id="personal_meaning", title=data["detail_title"], text=data["detail"], kind="reading"))
        sections.append(QuestionSection(id="matched_evidence", title="적용한 자료와 관법" if payload.input.locale == "ko" else "Matched facts and methods", text=memo))
        memo = ("확인된 보조 표시의 뜻과 공존하는 주제를 읽었습니다. 아래 자료에는 실제 적용 위치와 출처가 포함됩니다." if payload.input.locale == "ko" else
                "This reads matched supplementary themes. The notes below retain eligible positions and sources.")
        if reading.comparisons:
            memo += (" 다른 날짜 기준의 결과도 함께 제공합니다." if payload.input.locale == "ko" else
                     " They also include the alternate day-convention comparison.")
        context = {"feature_versions": model_to_dict(reading.versions), "feature_scope": reading.scope,
                   "feature_status": reading.status, "feature_assumption": reading.assumption,
                   "feature_comparisons": reading.comparisons,
                   "_memo_facts": [" · ".join(getattr(base.manse.pillars, k).gan_zhi for k in ("year", "month", "day", "time"))]}
    elif payload.question_id == "chart.pillars":
        answer, memo, context = _pillars(base, payload.input.locale, facts, sections)
    elif payload.question_id == "luck.current_next":
        answer, memo, context = _luck(base, payload.input.locale, facts, sections, current)
    elif payload.question_id == "period.this_year":
        answer, memo, context = _annual(base, payload.input.locale, facts, sections, current)
    elif payload.question_id == "stars.dohwa":
        answer, memo, context = _dohwa(base, payload.input.locale, facts, sections)
    else:
        answer, memo, context = _wealth(base, payload.input.locale, facts, sections)
    memo_facts = context.pop("_memo_facts")
    context["calculation_policy"] = model_to_dict(base.result.calculation_basis)
    context["timezone_id"] = base.region.tzid
    context["critical_uncertainty"] = _critical(base)
    context["uncertainty_codes"] = [flag.code for flag in base.result.uncertainty_summary]
    context["answer_meaning_ids"] = sorted(ANSWER_MEANINGS[payload.question_id])
    context["question_recommendation_version"] = FOLLOWUP_VERSION
    followups = select_followups(list(options.values()), payload.question_id)
    cache_key = _digest({"input": model_to_dict(payload), "facts": [model_to_dict(fact) for fact in facts],
                         "context": context, "day": current.astimezone(ZoneInfo(base.region.tzid)).date().isoformat(),
                         "versions": model_to_dict(QuestionVersions()), "provider": "deterministic"})
    cached = _cache_get(_ANSWERS, cache_key)
    if cached is not None:
        cached.trace_id = trace_id
        cached.as_of = current.isoformat()
        cached.cached = True
        return cached
    option = options[payload.question_id]
    scope_notices = {
        "chart.pillars": ("네 자리의 글자를 설명한 답이야. 이 글자만으로 사건이나 성격을 단정한 건 아니야.", "This explains the four positions; it does not infer events or personality from the characters alone."),
        "luck.current_next": ("대운 교체일은 계산 구간의 경계야. 만남·취업이 일어날 날짜를 뜻하진 않아.", "A cycle change is a calculated interval boundary, not a relationship or job-entry date."),
        "stars.dohwa": ("도화 위치는 만남 확률이나 다른 사람과의 매력 순위가 아니야.", "Peach Blossom positions are not meeting probabilities or attractiveness rankings."),
        "wealth.locations": ("재성 위치의 개수는 돈복의 크기나 실제 수입을 뜻하진 않아.", "Wealth position counts do not measure money luck or actual income."),
        "period.this_year": ("올해 천간의 십성 하나로 길흉이나 만남·승진 시기를 정한 건 아니야.", "One annual stem relation does not determine fortune or relationship/promotion timing."),
    }
    notices = _notices(base, payload.input.locale, payload.question_id)
    if payload.question_id.startswith("features."):
        if context["feature_assumption"]:
            notices = [context["feature_assumption"]]
        notices.append("확인된 전통 보조 표시의 뜻을 함께 읽은 풀이야. 사주 전체의 길흉이나 사건 시기를 판정한 것은 아니야." if payload.input.locale == "ko" else
                       "A reading of coexisting traditional supplementary themes, not a whole-chart fortune verdict or event forecast.")
    else:
        notices += [scope_notices[payload.question_id][0 if payload.input.locale == "ko" else 1]]
    response = SajuQuestionResponse(
        trace_id=trace_id, as_of=current.isoformat(), question_id=payload.question_id,
        question=option.title, title=option.title, answer=answer, sections=sections,
        memo=ReadingBasisExplanation(facts=memo_facts, reading=memo),
        notices=notices, facts=facts, source_context=context, followups=followups)
    _cache_put(_ANSWERS, cache_key, response)
    return response
