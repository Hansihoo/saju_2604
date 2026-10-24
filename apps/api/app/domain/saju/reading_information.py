"""Compile supplied chart positions and found-only terms without new judgments.

No model, network, score, candidate comparison or event forecast is used here.
Hidden-stem relations reuse the canonical backend question fact adapter.
"""
from datetime import datetime
from functools import lru_cache
import json
from pathlib import Path

from app.domain.saju.localization import localize_branch, localize_stem, localize_ten_god
from app.domain.saju.pydantic_compat import model_to_dict
from app.domain.saju.question_reading import _cycles, _date_label, _ten_god
from app.domain.saju.reading_information_contracts import (
    ReadingInformation, ReadingInformationFact, ReadingInformationItem,
)

POSITIONS = {
    "ko": {"year": "태어난 해", "month": "태어난 달", "day": "태어난 날", "time": "태어난 시간"},
    "en": {"year": "year", "month": "month", "day": "day", "time": "hour"},
}
TEN_GOD_THEMES = {
    "비견": ("내 기준·동료", "self and peers"),
    "겁재": ("다른 사람과 경쟁하는 일·역할과 자원을 나누는 일", "competition with others and sharing roles or resources"),
    "식신": ("만드는 일·결과물", "production and output"), "상관": ("표현·새로운 방식", "expression and new approaches"),
    "정재": ("재산·보상", "assets and compensation"), "편재": ("거래·자원 운용", "trade and resource management"),
    "정관": ("역할·규범·평가", "roles, standards and evaluation"), "편관": ("책임·압박·도전", "responsibility, pressure and challenge"),
    "정인": ("배움·지원", "learning and support"), "편인": ("탐구·전문 지식", "inquiry and specialist knowledge"),
}
STEM_IMAGES = {
    "甲": ("갑목", "큰 나무", "Yang Wood, traditionally pictured as a tree"),
    "乙": ("을목", "풀과 덩굴", "Yin Wood, traditionally pictured as grasses and vines"),
    "丙": ("병화", "햇빛", "Yang Fire, traditionally pictured as sunlight"),
    "丁": ("정화", "작은 불빛", "Yin Fire, traditionally pictured as a small flame"),
    "戊": ("무토", "큰 땅", "Yang Earth, traditionally pictured as broad land"),
    "己": ("기토", "밭과 흙", "Yin Earth, traditionally pictured as cultivated soil"),
    "庚": ("경금", "단단한 금속", "Yang Metal, traditionally pictured as solid metal"),
    "辛": ("신금", "다듬은 금속", "Yin Metal, traditionally pictured as refined metal"),
    "壬": ("임수", "큰 물", "Yang Water, traditionally pictured as a large body of water"),
    "癸": ("계수", "비와 이슬", "Yin Water, traditionally pictured as rain and dew"),
}
MONTH_NAMES = {"寅": ("인목", "봄", "spring"), "卯": ("묘목", "봄", "spring"), "辰": ("진토", "봄", "spring"),
               "巳": ("사화", "여름", "summer"), "午": ("오화", "여름", "summer"), "未": ("미토", "여름", "summer"),
               "申": ("신금", "가을", "autumn"), "酉": ("유금", "가을", "autumn"), "戌": ("술토", "가을", "autumn"),
               "亥": ("해수", "겨울", "winter"), "子": ("자수", "겨울", "winter"), "丑": ("축토", "겨울", "winter")}


@lru_cache(maxsize=1)
def _catalog():
    return json.loads((Path(__file__).parent / "data" / "reading_information_catalog.json").read_text(encoding="utf-8"))


def load_information_catalog():
    """Read the versioned glossary without a calculation or provider call."""
    return _catalog()


def _copula(word):
    return word + ("야" if (ord(word[-1]) - 0xAC00) % 28 == 0 else "이야")


def _valid_matches(star, base):
    if not star.active:
        return []
    matches = []
    visible = set(base.manse.meta.visible_pillar_keys)
    for match in star.matches:
        if match.pillar_key not in visible:
            continue
        pillar = getattr(base.manse.pillars, match.pillar_key)
        if not pillar.enabled or match.gan_zhi != pillar.gan_zhi or match.stem != pillar.stem or match.branch != pillar.branch:
            continue
        expected_value = pillar.branch if match.matched_field == "pair" else getattr(pillar, match.matched_field)
        if match.matched_value != expected_value:
            continue
        if match.counterpart_pillar_key:
            if match.counterpart_pillar_key not in visible:
                continue
            counterpart = getattr(base.manse.pillars, match.counterpart_pillar_key)
            if not counterpart.enabled or match.counterpart_gan_zhi != counterpart.gan_zhi:
                continue
        matches.append(match)
    return matches


def build_reading_information(*, base, locale: str, gender: str, as_of: datetime) -> ReadingInformation:
    if as_of.tzinfo is None:
        raise ValueError("reading information needs an aware as_of")
    ko = locale == "ko"
    provisional = any(flag.severity == "critical" for flag in base.result.uncertainty_summary)
    result = ReadingInformation(interpretation_withheld=provisional)
    labels = POSITIONS[locale]

    def fact(fact_id, value, source_path):
        if not any(item.id == fact_id for item in result.facts):
            result.facts.append(ReadingInformationFact(id=fact_id, value=value, source_path=source_path))
        return fact_id

    def add(item_id, category, title, body, memo, refs, kind="calculation_description", **extra):
        if provisional:
            # A folded item can be read independently of the page-level hold.
            # Keep its selected-chart assumption in both presentation forms.
            title = ("잠정 계산: " if ko else "Provisional calculation: ") + title
            if ko:
                body = body.replace("네 사주를", "선택한 임시 명식을").replace("네 사주", "선택한 임시 명식")
                body = "아래 글자와 위치는 선택한 기준의 임시 계산값이야. 확정된 명식의 정보는 아니야.\n\n" + body
                memo = "선택한 임시 명식 기준의 자료입니다. 일주가 확정된 것으로 읽지 않습니다.\n\n" + memo
            else:
                body = body.replace("Your reference character is", "The provisional chart's reference character is")
                body = body.replace("your chart", "the provisional chart").replace("Matched in your ", "Provisional matches in the ")
                body = "The characters and positions below belong to the provisional chart under the selected convention, not a confirmed chart.\n\n" + body
                memo = "Information under the selected provisional chart; the day pillar is not confirmed.\n\n" + memo
        result.items.append(ReadingInformationItem(id=item_id, category=category, title=title, body=body,
                            memo_body=memo, fact_ids=list(dict.fromkeys(refs)), kind=kind,
                            provisional=provisional, **extra))

    day = base.manse.meta.day_master
    day_ref = fact("information.day_master", day, "manse.meta.day_master")
    relations = []
    for key in base.manse.meta.visible_pillar_keys:
        pillar = getattr(base.manse.pillars, key)
        if not pillar.enabled:
            continue
        ref = fact("information.pillar." + key, model_to_dict(pillar), "manse.pillars." + key)
        # Day stem is the reference itself, not a second personal trait.
        if key != "day" and pillar.stem:
            relations.append({"pillar": key, "layer": "visible", "stem": pillar.stem,
                              "god": _ten_god(day, pillar.stem, "ko")[0], "ref": ref,
                              "reported_god": localize_ten_god(pillar.stem_ten_god or "", "ko")})
        for stem in pillar.hidden_stems:
            relations.append({"pillar": key, "layer": "hidden", "stem": stem,
                              "god": _ten_god(day, stem, "ko")[0], "ref": ref})
    result.derivations.append({"rule": "canonical_visible_and_hidden_stem_relation_v2", "reference": "question_reading._ten_god / LunarUtil.SHI_SHEN",
                               "input_fact_ids": [f.id for f in result.facts], "relations": relations})

    name, image, english_image = STEM_IMAGES[day]
    month = base.manse.pillars.month
    month_ref = "information.pillar.month"
    month_god = _ten_god(day, month.stem, "ko")[0]
    theme = TEN_GOD_THEMES.get(month_god)
    _, season, english_season = MONTH_NAMES[month.branch]
    month_text = (f"태어난 달은 전통적인 계절 구분에서 {season}에 해당해." if ko else
                  f"Your birth month falls in {english_season} in the traditional solar-term calendar.")
    if theme:
        month_text += (f" 태어난 달의 글자를 너와의 관계로 읽으면 ‘{theme[0]}’이라는 주제가 나와." if ko else
                       f" Read in relation to your day stem, the month stem has the traditional theme of {theme[1]}.")
    add("structure.day_month", "core", f"너를 읽는 기준은 {name}" if ko else "Your day stem and birth month",
        (f"네 사주를 읽는 기준 글자는 {_copula(name)}. 전통적으로 {image}에 비유해.\n\n" if ko else
         f"Your reference character is {english_image}.\n\n") + month_text,
        f"일간 {day}; 월주 {month.gan_zhi}; 선택한 일간 기준 월간 십성 {month_god}. 전통적 비유와 계절 분류이며 성격 검사 결과가 아닙니다. 단순 오행 개수로 신강·신약이나 용신을 판단하지 않습니다." if ko else
        f"Day stem {localize_stem(day, locale)}; month pillar {localize_stem(month.stem, locale)} / {localize_branch(month.branch, locale)}; month-stem relation {localize_ten_god(month_god, locale)}. Counts do not establish chart strength or favorable elements.",
        [day_ref, month_ref])
    reported_month_god = localize_ten_god(month.stem_ten_god or "", "ko")
    if reported_month_god != month_god:
        result.items[-1].memo_body += (f"\n원본 월간 분류는 {reported_month_god}입니다. 이 자료의 관계 설명은 원본 분류를 복사하지 않고 선택한 일간 {day}와 월간 {month.stem}을 같은 관계 표로 대조한 {month_god}를 사용합니다. 원본 계산값과 보류는 보존합니다." if ko else
            f"\nThe source reports {localize_ten_god(reported_month_god, locale)}. This description instead compares selected day stem {day} with month stem {month.stem} in the same relation table used for hidden stems: {localize_ten_god(month_god, locale)}. Original calculation fields and holds are preserved.")

    def positions(items, technical=False):
        # Explicit hidden stems are counted once each; no zip with a differently ordered god list.
        groups = []
        for layer in ("visible", "hidden"):
            for god in TEN_GOD_THEMES:
                selected = [r for r in items if r["layer"] == layer and r["god"] == god]
                if not selected:
                    continue
                locs = list(dict.fromkeys(labels[r["pillar"]] for r in selected))
                god_label = f" ({localize_ten_god(god, locale)})" if technical else ""
                groups.append((f"{TEN_GOD_THEMES[god][0]}{god_label}: {'·'.join(locs)}{'의 위쪽 글자' if layer == 'visible' else ' 안에 든 글자'}" if ko else
                               f"{TEN_GOD_THEMES[god][1]}{god_label}: {', '.join(locs)} positions, {'upper characters' if layer == 'visible' else 'characters inside the lower character'}"))
        return "\n".join("- " + group for group in groups)

    money = [r for r in relations if r["god"] in {"정재", "편재"}]
    if money:
        add("structure.wealth", "wealth", "돈과 보상의 글자는 어디에 있을까" if ko else "Where wealth symbols appear",
            ("돈과 보상에 연결해 읽는 글자는 이 자리에 있어. 겉에 보이는 글자와 안쪽에 든 글자를 나눴어.\n\n" if ko else
             "Wealth symbols are traditional names for assets and compensation. Your matching positions are below, separating visible stems from stems inside the branches.\n\n") + positions(money),
            ("정재는 재산·보상, 편재는 거래·자원 운용에 대응하는 전통적 분류입니다. 위치 확인은 수입·부의 크기 판정이 아닙니다.\n" if ko else
             "Direct Wealth concerns assets/compensation; Indirect Wealth concerns trade/resource management in the traditional glossary. Positions do not establish income or wealth.\n") + positions(money, technical=True),
            [day_ref] + [r["ref"] for r in money])

    partner_gods = {"정재", "편재"} if gender == "male" else {"정관", "편관"} if gender == "female" else set()
    partner = [r for r in relations if r["god"] in partner_gods]
    if partner:
        add("structure.partner", "love", "연애를 읽을 때 함께 보는 글자" if ko else "Additional relationship symbols",
            ("전통적인 성별 기준으로 연애·배우자에 연결해 읽는 글자는 이 자리에 있어.\n\n" if ko else
             "In this traditional convention, male charts use wealth symbols and female charts use officer symbols as partner references. For the gender supplied, the matching positions are:\n\n") + positions(partner),
            ("남성 기준은 재성, 여성 기준은 관성을 배우자 상징으로 읽는 전통적 분류입니다. 실제 성적 지향·현재 관계 상태·상대의 존재·만남 시기를 추론하지 않습니다.\n" if ko else
             "This is a traditional gender-based classification. It does not establish orientation, relationship status, a partner's existence or meeting dates.\n") + positions(partner, technical=True),
            [day_ref, fact("information.gender", gender, "input.gender")] + [r["ref"] for r in partner])

    for item_id, gods, title, intro in (
        ("structure.officer", {"정관", "편관"}, "책임과 평가를 읽는 글자" if ko else "Responsibility and evaluation symbols",
         "일의 역할·규칙·평가에 연결해 읽는 글자는 이 자리에 있어." if ko else
         "Officer symbols are traditionally used for roles, standards and evaluation. Your positions are:"),
        ("structure.work", {"식신", "상관", "정인", "편인"}, "만드는 일과 배우는 일, 따로 보여" if ko else "Output and learning symbols",
         "만들고 표현하는 일, 배우고 지원받는 일에 연결해 읽는 글자는 이 자리에 있어." if ko else
         "Output/expression uses the Output symbols; learning/support uses the Resource symbols. Your matching positions are:"),
    ):
        selected = [r for r in relations if r["god"] in gods]
        if selected:
            add(item_id, "career", title, intro + "\n\n" + positions(selected),
                ("각 글자의 분류와 위치를 기술한 것입니다. 적성·취업·승진·능력 수준은 이 목록만으로 판단하지 않습니다.\n" if ko else
                 "These are classifications and positions, not conclusions about aptitude, hiring, promotion or ability.\n") + positions(selected, technical=True),
                [day_ref] + [r["ref"] for r in selected])

    current, following = _cycles(base, as_of)
    for name, cycle in (("current", current), ("next", following)):
        if cycle is None:
            continue
        index = next(i for i, candidate in enumerate(base.manse.luck_cycles) if candidate.index == cycle.index)
        ref = fact("information.cycle." + name, model_to_dict(cycle), f"manse.luck_cycles[{index}]")
        god = _ten_god(day, cycle.gan_zhi[0], "ko")[0]
        start, end = _date_label(cycle.start_datetime, locale), _date_label(cycle.change_datetime, locale)
        title = ("지금 대운" if name == "current" else "다음 대운") if ko else ("Current luck cycle" if name == "current" else "Next luck cycle")
        letters = localize_stem(cycle.gan_zhi[0], locale) + "·" + localize_branch(cycle.gan_zhi[1], locale)
        add("cycle." + name, "luck_flow", title + ": " + TEN_GOD_THEMES[god][0 if ko else 1],
            (f"{start}부터 {end}까지의 계산 구간이야. 전통적인 풀이 주제는 {_copula(TEN_GOD_THEMES[god][0])}." if ko else
             f"This calculated interval runs from {start} to {end}. Its traditional theme is {TEN_GOD_THEMES[god][1]}."),
            f"{letters}; {localize_ten_god(god, locale)}; {cycle.start_datetime} ≤ as_of < {cycle.change_datetime}; {base.region.tzid}. " +
            ("교운 경계이며 유리한 사건 시기를 선정한 결과가 아닙니다." if ko else "Cycle boundaries, not favorable event windows."), [day_ref, ref])

    if not provisional and current is not None and following is not None:
        current_god = _ten_god(day, current.gan_zhi[0], "ko")[0]
        next_god = _ten_god(day, following.gan_zhi[0], "ko")[0]
        now_theme = TEN_GOD_THEMES[current_god][0 if ko else 1]
        next_theme = TEN_GOD_THEMES[next_god][0 if ko else 1]
        if current_god == next_god:
            contrast = (f"**구간이 바뀌어도 ‘{now_theme}’이라는 주제는 이어져.** 기간의 경계가 달라지는 것과 풀이 주제가 달라지는 것은 구별해서 읽어." if ko else
                        f"**The theme of {now_theme} continues across both periods.** A new interval does not necessarily introduce a different theme.")
        elif {current_god, next_god} == {"비견", "겁재"}:
            contrast = (f"**지금의 ‘{now_theme}’에서 다음의 ‘{next_theme}’로 초점이 달라져.** 두 구간 모두 나와 다른 사람의 관계를 읽지만, 내 입장을 세우는 것과 서로의 몫을 나누는 것은 다른 문제야. 같이 일하는 사람과의 관계에서도 ‘내가 어떻게 할 것인가’와 ‘누가 무엇을 맡고 나눌 것인가’를 구별하는 풀이야." if ko else
                        f"**The focus changes from {now_theme} to {next_theme}.** Both concern you and other people. Your own position differs from how roles and resources are divided: choosing your approach and sharing ownership are distinct themes.")
        else:
            contrast = (f"**지금은 ‘{now_theme}’, 다음은 ‘{next_theme}’을 중심으로 읽는 구간이야.** 같은 주제가 그대로 이어지는 구성이 아니라, 두 기간에 붙는 풀이의 초점이 달라져." if ko else
                        f"**The current theme is {now_theme}; the next is {next_theme}.** The two periods carry different interpretive themes rather than repeating the same one.")
        add("cycle.comparison", "luck_flow", "지금과 다음, 무엇이 달라질까" if ko else "What changes between these periods",
            contrast, ("두 대운 천간을 선택한 일간과 같은 관계 표로 대조한 분류의 뜻을 비교했습니다. 원국과 대운 지지·세운·합충을 종합한 판정이 아니며 사건의 증가/감소·유리한 시기·결과를 선정하지 않습니다." if ko else
                       "Compares the existing meanings of two cycle-stem relationships to the same day stem. It does not synthesize natal structure, cycle branches, annual influences or interactions, nor rank favorable periods or predict events."),
            [day_ref, "information.cycle.current", "information.cycle.next"])
        result.derivations.append({"rule": "cycle_theme_comparison_v1", "reference": "TEN_GOD_THEMES / question_reading._ten_god",
            "input_fact_ids": [day_ref, "information.cycle.current", "information.cycle.next"],
            "current_god": current_god, "next_god": next_god, "scope": "existing_classification_meanings_only_not_favorability"})

    for entry in _catalog()["entries"]:
        selected = []
        for index, star in enumerate(base.manse.special_stars):
            if not ((entry.get("key") == star.key) or (entry.get("family") == star.family)):
                continue
            matches = _valid_matches(star, base)
            if matches:
                selected.append((index, star, matches))
        if not selected:
            continue
        found_keys = {match.pillar_key for _, _, matches in selected for match in matches}
        keys = [key for key in base.manse.meta.pillar_order if key in found_keys]
        locations = "·".join(labels[key] for key in keys) if ko else ", ".join(labels[key] for key in keys)
        title = entry[locale]
        pairs = set()
        order = {key: index for index, key in enumerate(base.manse.meta.pillar_order)}
        for _, _, matches in selected:
            for match in matches:
                if match.counterpart_pillar_key:
                    pairs.add(tuple(sorted((match.pillar_key, match.counterpart_pillar_key), key=order.get)))
        if pairs:
            pair_text = "; ".join(labels[left] + " ↔ " + labels[right] for left, right in sorted(pairs, key=lambda p: (order[p[0]], order[p[1]])))
            location_sentence = f"네 사주에서는 {pair_text}의 조합에서 확인돼. " if ko else f"Matched pairs in your chart: {pair_text}. "
        else:
            location_sentence = f"네 사주에서는 {locations} 자리에 확인돼. " if ko else f"Matched in your {locations} pillar positions. "
        body = location_sentence + entry["meaning_" + locale]
        refs, memos = [], []
        for index, star, matches in selected:
            refs.append(fact("information.star." + star.key, model_to_dict(star), f"manse.special_stars[{index}]"))
            refs.extend("information.pillar." + match.pillar_key for match in matches)
            refs.extend("information.pillar." + match.counterpart_pillar_key for match in matches if match.counterpart_pillar_key)
            match_descriptions = []
            for match in matches:
                description = labels[match.pillar_key] + "=" + (match.matched_value if ko else localize_branch(match.branch, locale))
                if match.counterpart_pillar_key:
                    description += " ↔ " + labels[match.counterpart_pillar_key] + "=" + (match.counterpart_branch if ko else localize_branch(match.counterpart_branch, locale))
                match_descriptions.append(description)
            memos.append(f"{star.key}: {star.method_id}; " + (star.basis if ko else star.basis_key) + "; " + ", ".join(dict.fromkeys(match_descriptions)))
        add("star." + entry["id"], entry["category"], title, body, "\n".join(memos), refs,
            kind="traditional_term_definition", star_keys=[s.key for _, s, _ in selected],
            methods=list(dict.fromkeys(s.method_id for _, s, _ in selected)), matched_pillars=keys)
    return result
