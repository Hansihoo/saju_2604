"""Always-visible, personal chart overview without model or event prediction.

Question helpers supply the existing calculated facts. Catalog themes are used
only to explain vocabulary, never to apply an interpretation rule (including
when a chart has critical calculation uncertainty).
"""

from datetime import datetime

from app.domain.saju.interpretation import ReadingBasisExplanation
from app.domain.saju.localization import localize_pillar_label, localize_ten_god
from app.domain.saju.pydantic_compat import model_to_dict
from app.domain.saju.question_reading import (
    QuestionUnavailable, _annual, _branch_label, _canonical_stem, _critical,
    _cycles, _date_label, _dohwa, _ganzhi, _notices, _positions, _wealth, _luck,
)
from app.domain.saju.question_schemas import BasicReading, BasicReadingSection, QuestionFact
from app.domain.saju.services.build_reading_plan import load_reading_knowledge
from app.domain.saju.localization import localize_stem


# Plain-language labels for existing catalog groups, not new reading rules.
# Keep this independently versioned by BasicReadingVersions.knowledge/copy.
THEMES = {
    "peer": ("비겁", "내 기준과 함께 맡은 몫", "Peer/Rival", "personal standards and shared ownership"),
    "output": ("식상", "표현과 실제 결과물", "Output", "expression and usable output"),
    "wealth": ("재성", "자원과 보상의 조건", "Wealth", "resources and reward terms"),
    "officer": ("관성", "책임·역할·평가 기준", "Officer", "responsibility, roles and evaluation criteria"),
    "resource": ("인성", "배움과 회복을 위한 여유", "Resource", "learning and room to recover"),
}

# Everyday translations of the same catalog vocabulary. These describe what
# a reading discusses, not what will happen to this person.
PLAIN_TOPICS = {
    "비겁": ("내 몫과 함께하는 일", "내 몫, 함께 일하는 사람과의 역할, 서로의 기준을 살펴보는 주제야.",
             "shared roles and personal boundaries", "This topic covers shared roles, personal boundaries and each person's share."),
    "식상": ("표현과 결과물", "생각을 말이나 결과물로 꺼내는 일, 무엇을 만들어 보여주는지를 살펴보는 주제야.",
             "expression and what you make", "This topic covers turning ideas into words or work that others can see."),
    "재성": ("돈과 보상", "돈과 자원, 일을 하고 받는 보상, 주고받는 조건을 살펴보는 주제야.",
             "money and rewards", "This topic covers money, resources and the terms of what you give and receive."),
    "관성": ("일·책임·평가", "어떤 역할을 맡는지, 책임은 어디까지인지, 어떤 기준으로 평가받는지를 살펴보는 주제야.",
             "work, responsibility and evaluation", "This topic covers the role you take, its responsibilities and how it is evaluated."),
    "인성": ("배움과 재정비", "배우고 준비하는 일, 도움을 받는 조건, 쉬면서 다시 정리하는 이야기를 함께 봐.",
             "learning and regrouping", "This topic covers preparation, support and room to rest and regroup."),
}


def _plain_topic(canonical, locale, bundle, references):
    group = _theme(canonical, bundle, references)[0]
    topic = PLAIN_TOPICS[group]
    return topic[:2] if locale == "ko" else topic[2:]


def _month_label(value, locale):
    date = datetime.fromisoformat(value)
    return f"{date.year}년 {date.month}월" if locale == "ko" else date.strftime("%B %Y")


def _time_label(value, locale):
    date = datetime.fromisoformat(value)
    return _date_label(value, locale) + " " + date.strftime("%H:%M:%S")


def _plain_section(section_id, base, locale, as_of, context, luck_context, bundle, references):
    ko = locale == "ko"
    if section_id == "luck":
        current, following = _cycles(base, as_of)
        first, detail = _plain_topic(context["current_stem_ten_god"], locale, bundle, references)
        second, next_detail = _plain_topic(context["next_stem_ten_god"], locale, bundle, references)
        change = _month_label(current.change_datetime, locale)
        if first == second:
            text = (f"사주는 여러 해씩 묶어서도 읽어. 네가 지금 지나고 있는 계산 구간은 {change}까지야.\n\n"
                    f"지금과 다음 구간은 풀이 주제가 같아. 둘 다 ‘{first}’ 쪽이야. {detail}") if ko else (
                    f"Saju also groups years into long reading intervals. Your current calculated interval ends in {change}. The current and next intervals use the topic of {first}.\n\n"
                    f"{detail} The cycle changes, while this broad reading topic stays the same.")
        else:
            text = (f"사주는 여러 해씩 묶어서도 읽어. 네가 지금 지나고 있는 계산 구간은 {change}까지야. 그다음 구간에서는 풀이 주제도 달라져.\n\n"
                    f"지금 구간: {detail}\n다음 구간: {next_detail}") if ko else (
                    f"Saju also groups years into long reading intervals. Your current calculated interval ends in {change}. Its reading topic is {first}; the next interval uses {second}.\n\n"
                    f"Current cycle: {detail}\nNext cycle: {next_detail}")
        return ("지금부터 다음 흐름까지" if ko else "From this cycle to the next"), text
    if section_id == "annual":
        topic, detail = _plain_topic(context["annual"]["stem_ten_god"], locale, bundle, references)
        if luck_context:
            current_topic, _ = _plain_topic(luck_context["current_stem_ten_god"], locale, bundle, references)
            if topic == current_topic:
                lead = f"올해와 여러 해를 묶은 구간은 풀이 주제가 같아. 둘 다 ‘{topic}’ 쪽이야." if ko else (
                    f"This year also brings {topic} into the reading. It is a shared topic across your long cycle and this year.")
            else:
                lead = f"여러 해를 묶은 구간은 ‘{current_topic}’ 쪽이고, 올해는 ‘{topic}’ 쪽이야. 올해 풀이에는 다른 이야기가 더해진 셈이지." if ko else (
                    f"Your long cycle is read around {current_topic}; this year adds {topic}. These are two different topics to consider together.")
        else:
            lead = f"올해 네 사주와 연결해 읽는 이야기는 ‘{topic}’ 쪽이야." if ko else f"This year's reading topic for your chart is {topic}."
        if luck_context and topic == current_topic:
            detail = ("서로 다른 기간에서 같은 이야기가 나온다는 뜻이야. 같은 분류가 두 번 나왔다고 운이 두 배로 좋거나 나쁜 것은 아니야." if ko else
                      "Two different reading intervals share a topic. A repeated category does not make your luck twice as good or bad.")
        if not base.manse.meta.hour_pillar_enabled:
            lead = ("임시로 표시한 태어난 날의 글자를 기준으로 보면, " + lead) if ko else (
                "Using the provisionally displayed birth-day characters, " + lead[0].lower() + lead[1:])
        return ("올해, 함께 읽을 이야기" if ko else "What this year adds"), lead + "\n\n" + detail
    if section_id == "wealth":
        visible = sum(localize_ten_god(getattr(base.manse.pillars, key).stem_ten_god or "", "ko") in {"정재", "편재"}
                      for key in base.manse.meta.visible_pillar_keys)
        hidden = sum(item["ten_god"] in {"정재", "편재"} for item in context["wealth_relations"])
        places = {"year": "태어난 해", "month": "태어난 달", "day": "태어난 날", "time": "태어난 시간"} if ko else {
            "year": "birth year", "month": "birth month", "day": "birth day", "time": "birth hour"}
        visible_places = [key for key in base.manse.meta.visible_pillar_keys if localize_ten_god(
            getattr(base.manse.pillars, key).stem_ten_god or "", "ko") in {"정재", "편재"}]
        surface_locations = ", ".join(places[key] for key in visible_places)
        hidden_places = list(dict.fromkeys(item["pillar_key"] for item in context["wealth_relations"] if item["ten_god"] in {"정재", "편재"}))
        locations = "·".join(places[key] for key in hidden_places) if ko else ", ".join(places[key] for key in hidden_places)
        scope = ("생년월일로 임시 표시한 사주에서는, " if ko else "Within the provisionally displayed birth-year, month and day chart, ") if not base.manse.meta.hour_pillar_enabled else ""
        if not visible and hidden:
            title = "돈에 관한 단서, 겉보다 안쪽에 있어" if ko else "Money clues lie inside the chart"
            text = (f"{scope}위에 보이는 글자만 보면 돈과 보상에 관한 표시가 없어. 사주에는 겉에 보이는 글자 외에, 안쪽에 따로 표시하는 글자도 있어.\n\n"
                    f"그렇게 보면 {locations}에 해당하는 부분에서 총 {hidden}곳이 확인돼. ‘돈에 관한 표시가 없는 사주’라고 끝내면 네 정보를 놓치는 거야.") if ko else (
                    f"{scope}the visible chart has no money or reward marker. Its inner details do, in the {locations} part.\n\n"
                    "Reading only the visible chart would miss those markers.")
        elif visible and hidden:
            title = "돈에 관한 단서가 겉과 안에 있어" if ko else "Money clues appear on both layers"
            text = (f"{scope}돈과 보상에 관한 표시는 위에 보이는 글자에서 {visible}곳 확인돼. 사주에는 겉에 보이는 글자 외에, 안쪽에 따로 표시하는 글자도 있어.\n\n"
                    f"그 안쪽에서는 {locations}에 해당하는 부분에 총 {hidden}곳이 더 있어. 네 사주는 두 부분을 함께 봐야 설명이 빠지지 않아.") if ko else (
                    f"{scope}money and reward markers appear in the visible {surface_locations} part and the inner details of the {locations} part.\n\n"
                    "Reading only the visible chart or only its inner details would miss a marker.")
        elif visible:
            title = "돈에 관한 단서가 겉에 드러나 있어" if ko else "Money clues are on the surface"
            text = (f"{scope}돈과 보상에 관한 표시는 위에 보이는 글자에서 {visible}곳 확인돼. 사주의 글자를 안쪽까지 더 나눠 봤지만, 추가 표시는 없었어.\n\n"
                    "이번 결과는 겉에 나온 글자를 중심으로 살펴본 거야. 개수가 실제 수입의 크기를 뜻하는 건 아니야.") if ko else (
                    f"{scope}money and reward markers appear in the visible {surface_locations} part. No extra marker was found in the inner details.\n\n"
                    "These are markers in the chart, not a measure of actual income.")
        else:
            title = "돈에 관한 글자가 안 보인다고, 돈을 못 버는 건 아니야" if ko else "No wealth characters does not mean no income"
            text = (f"{scope}돈과 보상에 연결해 보는 글자는 이번에 잡히지 않았어.\n\n"
                    "이건 확인한 글자의 결과야. ‘돈을 못 번다’거나 ‘돈복이 없다’는 결론으로 바꾸면 안 돼.") if ko else (
                    f"{scope}no character associated with money and rewards was found.\n\n"
                    "That is a result about chart characters, not a conclusion that you cannot earn money.")
        return title, text if ko or scope else text[0].upper() + text[1:]
    methods = context["dohwa_methods"]
    hamji, wangji, mokyok = set(), set(), set()
    for method in methods:
        if method["key"] in {"dohwa-year-branch", "dohwa-day-branch"}:
            hamji.update(method["positions"])
        elif method["key"] == "wangji-dohwa":
            wangji.update(method["positions"])
        elif method["key"] == "mokyok-dohwa":
            mokyok.update(method["positions"])
    if not hamji and (wangji or mokyok):
        title = "도화는 ‘있다·없다’ 한마디로 못 끝내" if ko else "Peach Blossom is not a simple yes or no"
        text = ("좁은 기준에서는 도화가 잡히지 않았지만, 다른 기준에서는 잡혔어. 네 사주는 기준에 따라 결과가 달라지는 경우야.\n\n"
                "그래서 ‘없다’고 딱 잘라 말하기보다, 어느 기준에서 확인됐는지 나눠 읽어야 해.") if ko else (
                "The narrower method found no Peach Blossom, while another method did. Your result changes with the method.\n\n"
                "A single yes or no would hide that difference. The methods need to be read separately.")
    elif hamji:
        title = "네 사주에서 도화가 확인됐어" if ko else "Peach Blossom was found in your chart"
        text = (f"좁은 기준에서 도화가 {len(hamji)}자리에 잡혔어. 서로 다른 기준이 같은 자리를 가리키면 중복으로 세지 않았어.\n\n"
                "이건 사주 안의 표시를 확인한 결과야. 도화 하나로 인기나 연애 결과까지 정하는 건 아니야.") if ko else (
                f"The narrower method found Peach Blossom in {_positions(len(hamji))}. Repeated matches at the same position count once.\n\n"
                "These are chart markers, not a measure of popularity or a relationship outcome.")
    else:
        title = "도화가 없다고, 인연까지 없는 건 아니야" if ko else "No Peach Blossom does not mean no relationship"
        text = ("확인한 기준에서는 도화가 잡히지 않았어.\n\n도화가 없다는 말과 연애할 기회가 없다는 말은 달라. 이번 결과로 인연의 가능성까지 닫는 풀이를 하지 않아.") if ko else (
                "None of the checked methods found Peach Blossom.\n\nThat does not mean there are no chances for a relationship. This marker cannot decide that.")
    explanation = ("도화는 연애 풀이에서 참고하는 사주 속 표시야. " if ko else
                   "Peach Blossom is a chart marker consulted in relationship readings. ")
    if not base.manse.meta.hour_pillar_enabled:
        explanation = ("임시로 표시한 생년월일 부분만 살펴봤어. " if ko else
                       "Only the provisionally displayed birth-year, month and day parts were examined. ") + explanation
    return title, explanation + text


def _stem_label(stem, locale):
    canonical = _canonical_stem(stem)
    return f"{localize_stem(canonical, locale)}({canonical})"


def _theme(canonical, bundle, references):
    # This is a vocabulary reference. Rule conditions/exclusions are not
    # evaluated or bypassed, and no ReadingPlan/verified marker is produced.
    rule = next((rule for rule in bundle.rules if rule.topic == "luck_flow"
                 and rule.status == "active_project_policy" and canonical in rule.any_of), None)
    if rule is None:
        raise QuestionUnavailable("Catalog vocabulary theme is unavailable")
    group = rule.id.rsplit(".", 1)[-1]
    if group not in THEMES:
        raise QuestionUnavailable("Catalog vocabulary group is unavailable")
    source = next(source for source in bundle.sources if source.id == rule.source_id)
    references[rule.id] = {
        "rule_id": rule.id, "rule_version": rule.version,
        "source_id": source.id, "source_reference": source.reference,
        "source_kind": source.kind, "expert_review": source.expert_review,
        "kind": "vocabulary_theme", "interpretation_rule_applied": False,
    }
    return THEMES[group]


def _theme_text(canonical, locale, bundle, references):
    label = localize_ten_god(canonical, locale)
    ko_group, ko_meaning, en_group, en_meaning = _theme(canonical, bundle, references)
    return (f"{label} 이름은 {ko_meaning} 같은 주제를 설명할 때 쓰는 {ko_group} 용어야."
            if locale == "ko" else
            f"{label} belongs to the {en_group} group, vocabulary used when discussing {en_meaning}.")


def _theme_pair(first, second, first_period, second_period, locale, bundle, references, headline=False):
    """Connect two supplied labels, explaining a common theme only once."""
    first_label, second_label = localize_ten_god(first, locale), localize_ten_god(second, locale)
    first_theme = _theme(first, bundle, references)
    second_theme = _theme(second, bundle, references)
    if locale == "ko":
        if first_theme[0] == second_theme[0]:
            text = (f"{first_period}의 {first_label} 이름과 {second_period}의 {second_label} 이름은 "
                    f"같은 ‘{first_theme[1]}’ 주제로 묶여.")
            if not headline:
                text += (f" 명리에서 이 큰 분류를 {first_theme[0]}이라고 불러. "
                         "세부 십성 이름은 달라도 용어의 큰 분류는 같은 거야." if first != second else
                         f" 명리에서 이 큰 분류를 {first_theme[0]}이라고 불러. 두 항목의 세부 이름도 같아.")
            return text
        text = (f"{first_period}의 {first_label} 이름은 ‘{first_theme[1]}’ 쪽, "
                f"{second_period}의 {second_label} 이름은 ‘{second_theme[1]}’ 쪽 용어야.")
        if not headline:
            text += f" 앞쪽은 {first_theme[0]}, 뒤쪽은 {second_theme[0]}으로 큰 분류도 달라."
        return text
    if first_theme[2] == second_theme[2]:
        text = (f"The {first_label} label in {first_period} and the {second_label} label in {second_period} "
                f"share the topic of {first_theme[3]}.")
        if not headline:
            text += (f" Both belong to the {first_theme[2]} group. Their specific names differ, while the broader "
                     "vocabulary group is the same." if first != second else
                     f" Both belong to the {first_theme[2]} group, with the same specific name too.")
        return text
    text = (f"{first_label} in {first_period} is vocabulary for {first_theme[3]}; "
            f"{second_label} in {second_period} is vocabulary for {second_theme[3]}.")
    if not headline:
        text += f" Their broader groups also differ: {first_theme[2]} and {second_theme[2]}."
    return text


def _luck_body(base, locale, as_of, context, bundle, references):
    current, following = _cycles(base, as_of)
    current_name = _ganzhi(current.gan_zhi, locale)
    next_name = _ganzhi(following.gan_zhi, locale)
    current_label = localize_ten_god(context["current_stem_ten_god"], locale)
    next_label = localize_ten_god(context["next_stem_ten_god"], locale)
    if locale == "ko":
        periods = (f"지금은 {current_name} 대운 구간이야. {_time_label(current.start_datetime, locale)}에 시작했고, "
                   f"{_time_label(current.change_datetime, locale)} 교체 시각 전까지 이어져. 그다음은 {next_name} 대운으로, "
                   f"{_time_label(following.change_datetime, locale)} 교체 시각 전까지야.")
        relations = (f"네 일간 {_stem_label(base.manse.meta.day_master, locale)} 기준으로 현재 대운 천간 "
                     f"{_stem_label(current.gan_zhi[0], locale)}의 십성은 {current_label}, 다음 천간 "
                     f"{_stem_label(following.gan_zhi[0], locale)}의 십성은 {next_label}에 해당해. ")
        relations += ("두 구간의 천간에 붙는 십성 이름이 서로 다르게 잡힌 거야." if current_label != next_label else
                      "두 구간의 천간에 붙는 십성은 같은 이름으로 분류돼.")
    else:
        periods = (f"You are in the {current_name} long cycle, which began on {_time_label(current.start_datetime, locale)} "
                   f"and runs until its change time on {_time_label(current.change_datetime, locale)}. The following {next_name} "
                   f"cycle runs until its change time on {_time_label(following.change_datetime, locale)}.")
        relations = (f"Relative to your day stem {_stem_label(base.manse.meta.day_master, locale)}, the current stem "
                     f"{_stem_label(current.gan_zhi[0], locale)} is {current_label}; the next stem "
                     f"{_stem_label(following.gan_zhi[0], locale)} is {next_label}. Both the cycle characters and their named "
                     "relationships to the day stem can be compared.")
    meanings = _theme_pair(context["current_stem_ten_god"], context["next_stem_ten_god"],
        "현재 대운" if locale == "ko" else "the current long cycle", "다음 대운" if locale == "ko" else "the next long cycle",
        locale, bundle, references)
    return "\n\n".join((periods, relations, meanings))


def _annual_body(base, locale, context, luck_context, bundle, references):
    annual = context["annual"]
    label = localize_ten_god(annual["stem_ten_god"], locale)
    if locale == "ko":
        personal = (f"올해 들어온 글자를 보면 {_ganzhi(annual['gan_zhi'], locale)}년이야. 그중 천간 "
                    f"{_stem_label(annual['gan_zhi'][0], locale)}의 십성은 네 일간 {_stem_label(base.manse.meta.day_master, locale)} "
                    f"기준으로 보면 {label}에 해당해. 같은 해를 살아도 일간이 다르면 이 관계 이름은 달라져.")
        period = (f"올해 구간은 {_date_label(annual['start_datetime'], locale)} 입춘부터 "
                  f"{_date_label(annual['change_datetime'], locale)} 다음 입춘 전까지야. "
                  "세운은 이 한 해의 글자이고, 대운은 그보다 긴 구간의 글자라 따로 놓고 보는 자료야.")
    else:
        personal = (f"This year's characters are {_ganzhi(annual['gan_zhi'], locale)}. Its stem "
                    f"{_stem_label(annual['gan_zhi'][0], locale)} is {label} relative to your day stem "
                    f"{_stem_label(base.manse.meta.day_master, locale)}. Different day stems can give different relationships "
                    "within the same calendar year.")
        period = (f"This annual interval begins at Ipchun on {_date_label(annual['start_datetime'], locale)} "
                  f"and ends at the next Ipchun on {_date_label(annual['change_datetime'], locale)}. "
                  "The annual pillar covers this year; the long-cycle pillar describes a longer calculated interval.")
    if luck_context:
        meaning = _theme_pair(luck_context["current_stem_ten_god"], annual["stem_ten_god"],
            "현재 대운" if locale == "ko" else "the current long cycle", "올해" if locale == "ko" else "this year",
            locale, bundle, references)
        meaning += " 긴 구간과 올해 구간의 용어를 나란히 비교한 것이야." if locale == "ko" else " This compares vocabulary across the two time layers."
    else:
        meaning = _theme_text(annual["stem_ten_god"], locale, bundle, references)
    return "\n\n".join((personal, period, meaning))


def _wealth_body(base, locale, context, bundle, references):
    visible = []
    visible_entries = []
    for key in base.manse.meta.visible_pillar_keys:
        pillar = getattr(base.manse.pillars, key)
        canonical = localize_ten_god(pillar.stem_ten_god or "", "ko")
        if canonical in {"정재", "편재"}:
            visible_entries.append({"pillar_key": key, "stem": _canonical_stem(pillar.stem)})
            visible.append(f"{localize_pillar_label(key, locale)} {_stem_label(pillar.stem, locale)} "
                           f"· {localize_ten_god(canonical, locale)}")
    hidden = []
    hidden_entries = []
    for item in context["wealth_relations"]:
        if item["ten_god"] not in {"정재", "편재"}:
            continue
        key = item["pillar_key"]
        hidden_entries.append({"pillar_key": key, "stem": _canonical_stem(item["stem"])})
        branch = _branch_label(getattr(base.manse.pillars, key).branch, locale)
        hidden.append((f"{localize_pillar_label(key, locale)} {branch} 속 {_stem_label(item['stem'], locale)} "
                       f"· {localize_ten_god(item['ten_god'], locale)}") if locale == "ko" else
                      (f"{localize_pillar_label(key, locale)}, {_stem_label(item['stem'], locale)} inside {branch} "
                       f"· {localize_ten_god(item['ten_god'], locale)}"))
    scope = ("임시로 표시한 연주·월주·일주에서 " if locale == "ko" else "Within the provisionally displayed year, month and day pillars, ") if not base.manse.meta.hour_pillar_enabled else ""
    if locale == "ko":
        surface = scope + ("겉 천간의 재성은 " + " / ".join(visible) + "에 있어." if visible else
                           "겉에 적힌 천간에서는 정재·편재에 해당하는 글자가 잡히지 않아.")
        inside = ("지장간은 지지 글자 안에 나누어 표시하는 천간이야. 재성은 " + " / ".join(hidden) + "에서 확인돼." if hidden else
                  "확인한 기둥의 지장간에서는 정재·편재에 해당하는 글자가 잡히지 않아.")
        counts = (f"겉 {len(visible)}곳과 지장간 {len(hidden)}곳을 나누어 센 거야. 개수는 글자 자리 수라 "
                  "같은 글자가 서로 다른 기둥에 있어도 각각 기록해.")
        meaning = "명리에서 재성은 자원과 보상의 조건을 설명할 때 쓰는 이름이야. 정재·편재는 일간과 재성 글자의 음양 관계로 나눈 분류고."
    else:
        surface = scope + ("the visible wealth stems are " + " / ".join(visible) + "." if visible else
                           "no Direct or Indirect Wealth character appears in the visible stems.")
        if not scope:
            surface = surface[0].upper() + surface[1:]
        inside = ("Hidden stems are stem characters displayed within a branch. Wealth characters appear at " + " / ".join(hidden) + "." if hidden else
                  "No Direct or Indirect Wealth character appears in the hidden stems of the checked pillars.")
        counts = (f"Visible stems occupy {_positions(len(visible))}; hidden wealth stems occupy {_positions(len(hidden))}. "
                  "The unit is a character position: repeated characters in different pillars count as separate positions.")
        meaning = "Wealth is vocabulary for resources and reward terms. Direct and Indirect Wealth are distinguished by their polarity relationship to the day stem."
    _theme("정재", bundle, references)
    shared_stems = list(dict.fromkeys(item["stem"] for item in visible_entries
                                     if any(hidden_item["stem"] == item["stem"] for hidden_item in hidden_entries)))
    connection = []
    for stem in shared_stems:
        surface_locations = "·".join(localize_pillar_label(item["pillar_key"], locale) for item in visible_entries if item["stem"] == stem)
        hidden_locations = "·".join(localize_pillar_label(item["pillar_key"], locale) for item in hidden_entries if item["stem"] == stem)
        connection.append(f"같은 {_stem_label(stem, locale)} 글자가 {surface_locations}의 겉 천간과 {hidden_locations}의 지장간에 각각 있어." if locale == "ko" else
                          f"The same {_stem_label(stem, locale)} character appears as a visible stem in {surface_locations} and as a hidden stem in {hidden_locations}.")
    if visible and hidden and not shared_stems:
        connection.append("겉 천간과 지장간 양쪽에 재성이 있지만, 확인된 재성 글자는 서로 달라." if locale == "ko" else
                          "Wealth stems appear on both the surface and within the branches, but the wealth characters differ between those two layers.")
    elif not visible and hidden:
        connection.append("이 명식에서 재성이 확인된 쪽은 겉 천간이 아니라 지장간이야." if locale == "ko" else
                          "The wealth characters in this chart were found within the branches rather than on the surface.")
    elif visible and not hidden:
        connection.append("확인한 기둥에서 재성이 잡힌 쪽은 겉 천간이야. 지장간에서는 추가 재성 글자가 잡히지 않았어." if locale == "ko" else
                          "Within the checked pillars, wealth characters were found on the surface; no additional wealth stem was found inside the branches.")
    elif not visible and not hidden:
        connection.append("확인한 겉 천간과 지장간 양쪽에서 재성 글자가 잡히지 않았어." if locale == "ko" else
                          "No wealth character was found in either the checked visible stems or hidden stems.")
    for stem in dict.fromkeys(item["stem"] for item in hidden_entries):
        locations = list(dict.fromkeys(item["pillar_key"] for item in hidden_entries if item["stem"] == stem))
        if len(locations) > 1:
            labels = "·".join(localize_pillar_label(key, locale) for key in locations)
            connection.append(f"지장간의 {_stem_label(stem, locale)} 글자는 {labels}에 각각 있어서, 같은 글자도 서로 다른 자리로 기록돼." if locale == "ko" else
                              f"Within the hidden stems, {_stem_label(stem, locale)} appears separately in {labels}, so the repeated character occupies distinct positions.")
    counts += " " + " ".join(connection)
    return "\n\n".join((surface + " " + inside, counts, meaning))


def _dohwa_body(base, locale, context):
    methods = context["dohwa_methods"]
    groups = {"hamji": set(), "wangji": set(), "mokyok": set()}
    for method in methods:
        name = "hamji" if method["key"] in {"dohwa-year-branch", "dohwa-day-branch"} else {
            "wangji-dohwa": "wangji", "mokyok-dohwa": "mokyok"}.get(method["key"])
        if name:
            groups[name].update(method["positions"])
    def positions(name):
        labels = []
        for key in base.manse.meta.pillar_order:
            if key in groups[name]:
                branch = _branch_label(getattr(base.manse.pillars, key).branch, locale)
                labels.append(f"{localize_pillar_label(key, locale)} {branch}")
        count = f"{len(groups[name])}곳" if locale == "ko" else _positions(len(groups[name]))
        return count + (" — " + " / ".join(labels) if labels else "")
    if locale == "ko":
        personal = f"네 명식에서 확인한 위치를 나누면 이래. 함지도화: {positions('hamji')}. 왕지도화: {positions('wangji')}."
        methods_text = ("함지도화는 연지와 일지의 삼합 기준으로 특정 지지를 찾고, 왕지도화는 자·오·묘·유라는 "
                        "네 지지가 있는지 보는 넓은 기준이야. 그래서 같은 명식이어도 기준별 위치가 다를 수 있어.")
        separate = (f"일간의 12운성에서 목욕지를 찾는 목욕도화: {positions('mokyok')}. "
                    "이 세 방법은 각각 확인한 결과야. 연지·일지 기준이 같은 기둥을 가리키면 함지 위치는 한 번만 기록해.")
    else:
        personal = f"Your chart has Hamji Peach Blossom at {positions('hamji')} and Wangji at {positions('wangji')}."
        methods_text = ("Hamji uses the year- and day-branch triad methods to seek a specific branch. Wangji is a broader "
                        "check for the four branches Ja(子), O(午), Myo(卯) and Yu(酉). These methods can identify different "
                        "positions in the same chart.")
        separate = (f"Bath Peach Blossom, which seeks the day stem's Bath branch in the twelve-stage cycle, has "
                    f"{positions('mokyok')}. Each method is recorded separately. A pillar matched by both Hamji anchor "
                    "methods is counted once in Hamji.")
    if not base.manse.meta.hour_pillar_enabled:
        personal = ("임시로 표시한 연주·월주·일주만 확인했어. " if locale == "ko" else "Only the provisionally displayed year, month and day pillars were checked. ") + personal
    return "\n\n".join((personal, methods_text, separate))


def build_basic_overview(*, base, locale: str, as_of: datetime) -> BasicReading:
    """Compose an overview from one already-calculated response; no calls/IO provider."""
    ko = locale == "ko"
    bundle = load_reading_knowledge()
    references = {}
    facts = [QuestionFact(id="natal.day_master", label="일간" if ko else "Day stem",
                          value=base.manse.meta.day_master, source_path="manse.meta.day_master"),
             QuestionFact(id="natal.visible_elements", label="겉글자 오행 개수" if ko else "Visible element counts",
                          value=model_to_dict(base.manse.elements), source_path="manse.elements")]
    sections = []
    memo_sections = []
    context = {
        "calculation_policy": model_to_dict(base.result.calculation_basis),
        "timezone_id": base.region.tzid, "critical_uncertainty": _critical(base),
        "catalog_knowledge_version": bundle.knowledge_version,
        "vocabulary_only": True, "interpretation_rules_applied": False,
    }
    notices = []
    if not base.manse.meta.hour_pillar_enabled:
        notices.append("태어난 시간을 몰라 태어난 날의 글자도 확정하지 못했어. 아래는 생년월일로 임시 표시한 사주의 설명이야. 시간이 필요한 여러 해의 구간 설명은 제외했어." if ko else
                       "Birth time is unknown, so the birth-day characters are also unconfirmed. This reading uses a provisional date-based chart. Time-dependent long intervals are excluded.")
    elif any(flag.code == "midnight_rule_changes_day_pillar" for flag in base.result.uncertainty_summary):
        notices.append("네 출생시간은 날짜를 바꾸는 기준에 따라 태어난 날의 글자가 달라지는 구간이야. 아래는 지금 선택한 기준에서 표시한 사주를 읽었어." if ko else
                       "Your birth-day characters differ between day-change conventions at this birth time. This reading uses the chart displayed under the selected convention.")
    elif _critical(base):
        notices.append("출생시간이나 날짜를 나누는 기준에 따라 사주가 달라질 수 있어. 지금 선택한 기준으로 읽은 결과야." if ko else
                       "Birth-time and day-change conventions can change this chart. This reading uses the currently selected convention.")
    if not notices:
        notices = _notices(base, locale)
    current, following = _cycles(base, as_of)
    builders = []
    if current is not None and following is not None:
        builders.append(("luck", "지금과 다음의 큰 구간", "Your current and next long cycles", _luck))
    builders.extend((("annual", "올해 들어온 글자", "This year's characters", _annual),
                     ("wealth", "돈과 연결해 보는 글자의 자리", "Where the wealth characters appear", _wealth),
                     ("dohwa", "도화는 기준을 나누어 보면", "Peach Blossom, by method", _dohwa)))
    for section_id, title_ko, title_en, helper in builders:
        local_facts, helper_sections = [], []
        section_references = {}
        try:
            if section_id in {"luck", "annual"}:
                _, _, derived = helper(base, locale, local_facts, helper_sections, as_of)
            else:
                _, _, derived = helper(base, locale, local_facts, helper_sections)
            derived.pop("_memo_facts", None)
            if section_id == "luck":
                text = _luck_body(base, locale, as_of, derived, bundle, section_references)
            elif section_id == "annual":
                text = _annual_body(base, locale, derived, context.get("luck"), bundle, section_references)
                if context.get("luck"):
                    local_facts.append(next(fact for fact in facts if fact.id == "luck.current_stem_ten_god"))
            elif section_id == "wealth":
                text = _wealth_body(base, locale, derived, bundle, section_references)
            else:
                text = _dohwa_body(base, locale, derived)
                # Position text also names the actual matched branch, so expose
                # those original branches independently from the star matches.
                keys = {key for method in derived["dohwa_methods"] for key in method["positions"]}
                for key in sorted(keys):
                    local_facts.append(QuestionFact(id="dohwa." + key + ".branch", label=localize_pillar_label(key, locale),
                        value=getattr(base.manse.pillars, key).branch, source_path="manse.pillars." + key + ".branch"))
        except QuestionUnavailable:
            notices.append((title_ko + "은 필요한 계산 자료가 없어 이번 본문에서 제외했어.") if ko else
                           (title_en + " is omitted because its calculation data is unavailable."))
            continue
        memo_text = text
        if not base.manse.meta.hour_pillar_enabled:
            memo_text = ("시간 미상으로 일주·일간은 확정되지 않았습니다. 아래는 선택한 날짜 기준의 잠정 명식에 대한 설명입니다.\n\n" if ko else
                         "Birth time is unknown, so the day pillar/day stem are unconfirmed. This describes the provisional chart under the selected date convention.\n\n") + memo_text
        plain_title, text = _plain_section(section_id, base, locale, as_of, derived, context.get("luck"), bundle, section_references)
        context[section_id] = derived
        references.update(section_references)
        ids = ["natal.day_master"]
        for fact in local_facts:
            if fact.source_path.startswith("source_context."):
                fact = QuestionFact(**dict(model_to_dict(fact), source_path="basic_reading.source_context." + section_id + "." + fact.source_path[len("source_context."):]))
            if fact.id not in {known.id for known in facts}:
                facts.append(fact)
            ids.append(fact.id)
        fact_ids = list(dict.fromkeys(ids))
        sections.append(BasicReadingSection(id=section_id, title=plain_title, text=text, fact_ids=fact_ids))
        memo_sections.append(BasicReadingSection(id=section_id, title=title_ko if ko else title_en,
                                                text=memo_text, fact_ids=fact_ids))
    context["vocabulary_sources"] = list(references.values())
    limitations = ["만남·취업 시기나 실제 수입을 예측한 결과는 아니야." if ko else
                   "This reading does not predict relationship/job dates or actual income."]
    scope = "연주·월주·일주·시주" if base.manse.meta.hour_pillar_enabled else "연주·월주·일주"
    if context.get("luck") and context.get("annual"):
        current_topic, _ = _plain_topic(context["luck"]["current_stem_ten_god"], locale, bundle, references)
        annual_topic, _ = _plain_topic(context["annual"]["annual"]["stem_ten_god"], locale, bundle, references)
        if current_topic == annual_topic:
            headline = f"지금과 올해는 ‘{current_topic}’ 이야기가 겹쳐 보여." if ko else f"Your long cycle and this year share a topic: {current_topic}."
        else:
            headline = f"지금 구간은 ‘{current_topic}’ 쪽, 올해는 ‘{annual_topic}’ 쪽으로 읽혀." if ko else f"Your current interval and this year use different reading topics: {current_topic}, and {annual_topic}."
    elif context.get("annual"):
        annual = context["annual"]["annual"]
        topic, _ = _plain_topic(annual["stem_ten_god"], locale, bundle, references)
        headline = f"올해는 ‘{topic}’ 쪽으로 읽혀." if ko else f"This year's reading focuses on {topic}."
    elif context.get("luck"):
        topic, _ = _plain_topic(context["luck"]["current_stem_ten_god"], locale, bundle, references)
        headline = f"지금 구간은 ‘{topic}’ 쪽으로 읽혀." if ko else f"This cycle's reading focuses on {topic}."
    else:
        headline = "네 사주에서 확인된 부분부터 읽어볼게." if ko else "Let's read the parts your chart can support."
    if not base.manse.meta.hour_pillar_enabled:
        headline = ("임시로 표시한 사주로 보면, " + headline) if ko else "For the provisional chart: " + headline
    used_sections = {section.id for section in sections}
    data_labels = {"luck": ("정밀 대운 구간", "precise cycle intervals"), "annual": ("입춘 세운", "Ipchun annual intervals"),
                   "wealth": ("표시된 천간·지장간", "visible/hidden stems"), "dohwa": ("방법별 신살 위치", "star-method positions")}
    used_data = [data_labels[section.id][0 if ko else 1] for section in sections]
    if used_data:
        memo_reading = ("이번 본문에는 " + ", ".join(used_data) + " 자료를 사용했습니다.") if ko else (
            "This overview used " + ", ".join(used_data) + ".")
    else:
        memo_reading = "이번 본문에는 확인된 일간 자료만 사용했습니다." if ko else "This overview used only the supplied day stem."
    if {"luck", "annual"}.intersection(used_sections):
        memo_reading += (f" 날짜는 출생지 시간대({base.region.tzid}) 기준이며 교체 시각은 해당 구간에 포함하지 않습니다." if ko else
                         f" Timezone: {base.region.tzid}; change instants start the next interval.")
    memo_reading += (" 생활 주제는 프로젝트 지식 카탈로그의 일반 용어 배경으로만 설명했습니다. 해석 규칙을 적용하거나 사건 시기·강도·결과를 판정하지 않았습니다." if ko else
                     " Catalog themes only; no interpretation rules or event predictions applied.")
    memo_reading += (" 오행 개수는 지장간을 제외한 단순 집계로, 강약·부족·길흉 판정이 아닙니다." if ko else
                     " Element counts omit hidden stems and do not measure strength.")
    elements = model_to_dict(base.manse.elements)
    element_labels = {"wood": "목", "fire": "화", "earth": "토", "metal": "금", "water": "수"} if ko else {
        "wood": "Wood", "fire": "Fire", "earth": "Earth", "metal": "Metal", "water": "Water"}
    element_counts = " · ".join(f"{label} {elements[key]}" + ("개" if ko else "") for key, label in element_labels.items())
    return BasicReading(as_of=as_of.isoformat(), title="네 사주부터 읽어볼게" if ko else "Start with your chart",
        headline=headline,
        sections=sections, memo_sections=memo_sections, limitations=limitations,
        facts=facts, source_context=context, notices=list(dict.fromkeys(notices)),
        memo=ReadingBasisExplanation(facts=[(("표시 범위(일주는 잠정): " if not base.manse.meta.hour_pillar_enabled else "확인 범위: ") + scope) if ko else
            ("Checked: year, month, day and hour pillars" if base.manse.meta.hour_pillar_enabled else "Displayed: year, month and provisional day pillars"),
            (("일간(잠정): " if not base.manse.meta.hour_pillar_enabled else "일간: ") if ko else
             ("Provisional day stem: " if not base.manse.meta.hour_pillar_enabled else "Day stem: ")) + _stem_label(base.manse.meta.day_master, locale),
            ("겉글자 기준 오행 개수: " if ko else "Visible element counts: ") + element_counts],
            reading=memo_reading))
