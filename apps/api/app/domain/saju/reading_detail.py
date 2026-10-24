"""Explain supplied relations and locations; never evaluate fortune or lift holds."""
import json
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field

from app.domain.saju.services.build_chart_characteristics import KEYS, _relation


VERSIONS = {
    "knowledge": "reading-detail-knowledge-2026-10-24.1",
    "selection": "reading-detail-selection-2026-10-24.2",
    "copy": "reading-detail-copy-2026-10-24.2",
}
RULES = {
    "month_support_meaning": "Explain the already-selected month and root/resource meanings, without final strength or ability.",
    "wealth_meaning_locations": "Join actual wealth categories and positions to existing category definitions; never infer income, source of money or retention.",
    "visible_relation_meanings": "Explain canonical groups actually present in visible non-day stems; not job suitability, ability or outcome.",
    "theme_locations": "Use only a selected theme's eligible matches; positions do not strengthen, cancel or predict a relationship.",
    "day_convention_comparison": "Compare only the independently derived, validated alternate profile; not a preferred convention or a global verdict.",
    "cycle_relation_glossary": "Explain current/next supplied cycle-stem categories against the selected day stem; not favorable periods or events.",
}
GROUPS = {
    "ko": {"peer": "동료와 자기 몫", "output": "표현과 결과물", "wealth": "돈과 보상", "officer": "역할과 평가", "resource": "배움과 지원"},
    "en": {"peer": "peers and one's own share", "output": "expression and output", "wealth": "money and rewards", "officer": "roles and evaluation", "resource": "learning and support"},
}
POSITIONS = {
    "ko": {"year": "태어난 해", "month": "태어난 달", "day": "태어난 날", "time": "태어난 시간"},
    "en": {"year": "year", "month": "month", "day": "day", "time": "hour"},
}


class ReadingDetailBlock(BaseModel):
    id: str
    category: Literal["core", "love", "wealth", "career", "luck_flow"]
    title: str
    text: str
    fact_ids: List[str]
    rule_ids: List[str]
    conditions: Dict[str, Any] = Field(default_factory=dict)
    provisional: bool = False
    scope: Literal["supplied_meanings_not_fortune_verdict"] = "supplied_meanings_not_fortune_verdict"


def _positions(occurrences, locale):
    keys = {o["pillar"] for o in occurrences}
    return " · ".join(POSITIONS[locale][k] for k in KEYS if k in keys)


def build_reading_details(*, natal, distinctive, information, locale):
    """No model prose, raw scores, unknown-time guesses or unvalidated alternates."""
    if natal.status not in {"available", "conditional"} or not natal.profile:
        return []
    from app.domain.saju.natal_structure import catalog
    data = catalog()
    p = natal.profile
    ko = locale == "ko"
    labels = GROUPS[locale]
    all_refs = [f["id"] for f in natal.facts]
    allowed = set(all_refs) | {f["id"] for f in distinctive.facts}
    if information is not None:
        allowed.update(f.id for f in information.facts)
    details = []

    def add(key, category, title, text, refs, rules, conditions=None):
        refs = list(dict.fromkeys(refs))
        if not refs or not set(refs) <= allowed or not set(rules) <= set(RULES):
            raise ValueError("Detailed reading requires supplied facts and explicit explanation rules")
        details.append(ReadingDetailBlock(id="detail." + key, category=category, title=title,
            text=text, fact_ids=refs, rule_ids=rules, conditions=conditions or {},
            provisional=natal.status == "conditional"))

    # The old words 'backing' and 'support' did not explain the distinction.
    resource_places = _positions(p["resource_occurrences"], locale)
    roots = " · ".join(POSITIONS[locale][k] for k in p["root_pillars"])
    if ko:
        support = (f"너와 같은 기운이 안쪽에 자리한 곳은 {roots}이야. " if roots else
                   "선택한 명식의 안쪽 구성에서는 너와 같은 기운이 자리한 곳이 확인되지 않아. ")
        support += (f"반면 배우고 도움을 받는 쪽의 관계는 {resource_places}에서 확인돼. " if resource_places else
                    "배움과 도움에 해당하는 관계도 이번 명식에서는 확인되지 않아. ")
        support += "같은 기운이 안에서 받쳐 주는 것과, 다른 기운이 배움·도움의 관계로 연결되는 것은 서로 다른 조건이야. 도움의 표시를 곧바로 혼자 모든 일을 감당하는 힘으로 읽지 않는 이유가 여기에 있어."
    else:
        support = (f"Same-element roots occur inside the {roots} positions. " if roots else
                   "No same-element root is matched in the selected chart's inner composition. ")
        support += (f"A separate learning/support relationship occurs at {resource_places}. " if resource_places else
                    "No separate learning/support relationship is matched either. ")
        support += "An inner root and another element's learning/support relationship are different conditions. The latter must not be counted as an ability to carry every demand alone."
    add("backing", "core", "받쳐 주는 조건을 더 풀어보면" if ko else "Two different forms of backing", support,
        all_refs, ["month_support_meaning"], {"roots": p["root_pillars"], "resource_present": p["resource_present"]})

    visible = [(g, p["visible_groups"][g]) for g in ("output", "officer", "resource", "wealth", "peer") if p["visible_groups"][g]]
    if visible:
        sentences = []
        for group, occurrences in visible:
            places = _positions(occurrences, locale)
            sentences.append((f"{places}의 겉글자에는 {labels[group]}에 해당하는 관계가 드러나 있어." if ko else
                              f"The visible {places} position carries the {labels[group]} relationship."))
        group_set = {g for g, _ in visible}
        if {"output", "officer"} <= group_set:
            sentences.append(("이 명식에서는 결과물을 내놓는 일과 그 결과를 어떤 기준으로 평가받는 일을 함께 볼 수 있어. 아이디어를 말하거나 무언가를 완성하는 과정과, 맡은 역할의 기준을 충족하는 과정이 구별돼. 그래서 결과를 만들었다는 사실 하나로 평가나 대우까지 좋다고 묶어 읽지 않아." if ko else
                              "Here, presenting a result and meeting a role's evaluation standards are separate themes. Developing or completing work is different from satisfying the terms under which it is assessed. Output alone does not establish favorable recognition or treatment."))
        add("work", "career", "일의 결과와 역할을 나누어 보면" if ko else "What the visible work-related themes mean",
            "\n\n".join(sentences), all_refs, ["visible_relation_meanings"], {"visible_groups": sorted(group_set)})

    wealth = p["wealth_occurrences"]
    gods = {o["god"] for o in wealth}
    meaning = "both" if gods == {"정재", "편재"} else "direct" if "정재" in gods else "indirect" if "편재" in gods else "absent"
    parts = [data["wealth_explanation"][meaning][locale]]
    for god, ko_name, en_name in (("정재", "재산·보상", "assets and compensation"), ("편재", "거래·자원 운용", "trade and resource management")):
        matching = [o for o in wealth if o["god"] == god]
        if not matching:
            continue
        for layer in ("visible", "hidden"):
            entries = [o for o in matching if o["layer"] == layer]
            if entries:
                places = _positions(entries, locale)
                parts.append((f"{ko_name}에 해당하는 관계는 {places}의 {'겉글자' if layer == 'visible' else '안쪽 구성'}에서 확인돼." if ko else
                              f"The {en_name} relationship occurs in the {'visible' if layer == 'visible' else 'inner'} {places} positions."))
    parts.append(data["wealth"][p["wealth_layer"]][locale]["text"])
    add("money", "wealth", "돈의 종류와 놓인 자리를 함께 보면" if ko else "Money categories and their actual positions",
        "\n\n".join(parts), all_refs, ["wealth_meaning_locations"], {"meaning": meaning, "layer": p["wealth_layer"]})

    for theme in distinctive.themes:
        if theme.category != "love":
            continue
        locations = []
        for fact_id, matches in theme.eligible_matches.items():
            occurrences = [{"pillar": m["pillar_key"]} for m in matches]
            places = _positions(occurrences, locale)
            if fact_id.endswith("wangji-dohwa"):
                locations.append((f"관심과 호감의 좋은 뜻을 읽는 도화는 {places} 자리에서 확인돼." if ko else
                                  f"The matched attention/attraction symbol occurs at the {places} position."))
            elif fact_id.endswith("wonjin"):
                locations.append((f"가까운 사이의 엇갈림을 읽는 표시는 {places} 자리를 함께 볼 때 확인돼." if ko else
                                  f"The separate close-relationship friction theme involves the {places} positions together."))
        if locations:
            locations.append(("관심을 받는 장면과 서로의 기대를 맞추며 가까운 관계를 이어 가는 장면은 같지 않아. 이 명식에서 좋은 쪽과 부담스러운 쪽을 따로 설명하는 이유야. 한 표시의 좋은 뜻이 다른 표시의 불편한 뜻을 지운다고 계산한 것은 아니야." if ko else
                              "Being noticed and maintaining a close connection with compatible expectations are different situations. That is why the favorable and less comfortable themes are explained separately here; one is not calculated to cancel the other."))
            add("relationship", "love", "관심과 가까운 관계의 차이" if ko else "Attention and closeness are separate",
                "\n\n".join(locations), theme.fact_ids, ["theme_locations"], {"selected_theme": theme.id})

    # The alternate was validated and independently derived by natal_structure.
    for comparison in natal.comparisons:
        other = comparison["profile"]
        if p["resource_present"] and other["resource_present"]:
            text = (f"두 날짜 기준 모두 배움과 지원에 해당하는 관계가 남아 있어. 선택한 명식의 중심은 ‘{labels[p['month_group']]}’, 다른 명식의 중심은 ‘{labels[other['month_group']]}’인데, 배움·지원이라는 관계가 함께 있다는 점은 같아. 그래서 날짜 기준이 바뀌면 앞의 설명이 전부 사라지는 것이 아니라, 공통으로 남는 내용과 달라지는 내용을 나눌 수 있어." if ko else
                    f"A learning/support relationship remains in both day-convention charts. The selected chart centers on {labels[p['month_group']]} and the alternate on {labels[other['month_group']]}, with learning/support present in each. A changed convention therefore does not discard every finding; shared and differing findings can be separated.")
            add("shared_support", "core", "어느 날짜 기준에서도 남는 내용" if ko else "What remains in both charts",
                text, all_refs, ["day_convention_comparison"], {"resource_present_in_both": True})
        other_gods = {o["god"] for o in other["wealth_occurrences"]}
        if gods and gods == other_gods:
            money_names = ({"정재": "재산·보상", "편재": "거래·자원 운용"} if ko else
                           {"정재": "assets/compensation", "편재": "trade/resource management"})
            common = " · ".join(money_names[g] for g in ("정재", "편재") if g in gods)
            text = (f"두 명식을 대조해도 ‘{common}’이라는 돈의 주제는 공통으로 확인돼. 따라서 이 사례는 날짜 기준에 따라 돈의 표시가 통째로 생기거나 사라지는 경우는 아니야. 어떤 돈의 주제가 있는지는 함께 남고, 그 관계가 겉에 드러나는지 안쪽에 놓이는지와 다른 글자와의 관계가 달라지는 거야." if ko else
                    f"Both charts retain the money categories {common}. This case does not switch from money symbols being present to entirely absent. The categories remain while their visible or inner positions and relationships with other characters can differ.")
            add("shared_money", "wealth", "두 기준에서 공통으로 확인되는 돈의 주제" if ko else "Money categories shared by both charts",
                text, all_refs, ["day_convention_comparison"], {"shared_money_categories": sorted(gods)})
        if p["month_group"] != other["month_group"]:
            text = (f"지금 선택된 명식의 중심은 ‘{labels[p['month_group']]}’, 다른 날짜 기준의 중심은 ‘{labels[other['month_group']]}’으로 달라져. 출생정보가 바뀐 것이 아니라 태어난 날을 나누는 기준이 달라져, 다른 글자와 맺는 관계가 달라지는 거야. 그래서 두 명식을 같은 뜻의 풀이로 뭉쳐 쓸 수 없어." if ko else
                    f"The selected chart centers on {labels[p['month_group']]}; the other day-change convention centers on {labels[other['month_group']]}. The birth details are the same, but a different day stem changes its relationships with the other characters. The two charts therefore cannot be given an identical reading.")
            add("alternate_core", "core", "날짜 기준이 달라지면 무엇이 바뀔까?" if ko else "What changes under the other day convention?",
                text, all_refs, ["day_convention_comparison"], {"selected_month_group": p["month_group"], "alternate_month_group": other["month_group"]})
        if p["wealth_layer"] != other["wealth_layer"]:
            layer_names = ({"visible": "돈에 해당하는 관계가 겉글자에 드러나는 구조", "hidden_only": "돈에 해당하는 관계가 안쪽에만 있는 구조", "absent": "돈에 해당하는 관계가 확인되지 않는 구조"} if ko else
                           {"visible": "a visible money relationship", "hidden_only": "money relationships in the inner composition only", "absent": "no matched money relationship"})
            text = (f"선택한 명식은 {layer_names[p['wealth_layer']]}이고, 다른 날짜 기준은 {layer_names[other['wealth_layer']]}야. 따라서 지금 읽은 돈의 위치를 다른 날짜 기준에도 그대로 옮겨 쓸 수는 없어. 차이가 확인된 것은 표시의 종류와 위치이지 실제 수입의 크기나 저축 결과가 아니야." if ko else
                    f"The selected chart has {layer_names[p['wealth_layer']]}, while the alternate has {layer_names[other['wealth_layer']]}. Its locations cannot simply be carried over to the other chart. The observed difference is in chart categories and positions, not actual income or savings.")
            add("alternate_money", "wealth", "다른 날짜 기준에서 달라지는 돈의 표시" if ko else "Money symbols under the alternate convention",
                text, all_refs, ["day_convention_comparison"], {"selected_layer": p["wealth_layer"], "alternate_layer": other["wealth_layer"]})
        primary_groups = {g for g, entries in p["visible_groups"].items() if entries}
        other_groups = {g for g, entries in other["visible_groups"].items() if entries}
        if primary_groups != other_groups:
            a = " · ".join(labels[g] for g in ("peer", "output", "wealth", "officer", "resource") if g in primary_groups)
            b = " · ".join(labels[g] for g in ("peer", "output", "wealth", "officer", "resource") if g in other_groups)
            text = (f"겉에 드러난 관계를 비교하면, 현재 명식에는 {a} 주제가 보이고 다른 날짜 기준에는 {b} 주제가 보여. 두 명식이 겉으로 드러내는 주제의 구성이 다르므로 한쪽의 설명을 다른 쪽에도 그대로 적용하지 않아. 어느 쪽이 더 좋은 직업운인지는 이 비교로 결정하지 않았어." if ko else
                    f"The visible relationships are {a} in the selected chart and {b} in the alternate. The themes differ, so the same work-related account cannot be applied unchanged to both. This comparison does not choose which chart has better career luck.")
            add("alternate_work", "career", "같은 직업 풀이로 합칠 수 없는 이유" if ko else "Why the work-related accounts differ",
                text, all_refs, ["day_convention_comparison"], {"selected_groups": sorted(primary_groups), "alternate_groups": sorted(other_groups)})

    if information is not None:
        facts = {f.id: f.value for f in information.facts}
        current, next_cycle = facts.get("information.cycle.current"), facts.get("information.cycle.next")
        if current and next_cycle and facts.get("information.day_master") == p["day_stem"]:
            _, current_group = _relation(p["day_stem"], current["gan_zhi"][0])
            _, next_group = _relation(p["day_stem"], next_cycle["gan_zhi"][0])
            parts = [(f"현재 구간의 글자를 선택한 명식과 연결하면 {labels[current_group]}의 뜻으로 읽고, 다음 구간은 {labels[next_group]}의 뜻으로 읽어." if ko else
                      f"Against the selected day stem, the current period's stem carries the {labels[current_group]} meaning and the next carries {labels[next_group]}.")]
            parts.append(data["work_explanation"]["work_money." + current_group][locale])
            if next_group != current_group:
                parts.append(data["work_explanation"]["work_money." + next_group][locale])
            parts.append(("두 구간은 달력상의 시작·끝뿐 아니라 설명하는 주제가 다르다는 점을 비교할 수 있어. 이 차이는 어느 구간에 취업하거나 연인을 만난다는 날짜 판정이 아니야." if ko else
                          "The comparison distinguishes the periods' supplied meanings as well as their calendar boundaries. It does not identify a hiring or relationship event date.") if current_group != next_group else
                         ("두 구간의 중심 주제는 같아. 구간이 바뀐다는 이유만으로 같은 뜻의 관계가 더 좋아지거나 나빠진다고 읽지 않아." if ko else
                          "The central category is the same in both periods. A changed period alone does not make that same category more favorable or adverse."))
            add("cycle_meanings", "luck_flow", "지금과 다음 구간을 구체적으로 비교하면" if ko else "The current and next meanings in detail",
                "\n\n".join(parts), ["information.day_master", "information.cycle.current", "information.cycle.next"],
                ["cycle_relation_glossary"], {"current_group": current_group, "next_group": next_group})
    return details


def detail_memo(blocks):
    return "\n\n".join("### " + b.id + "\n" + json.dumps({"facts": b.fact_ids, "rules": {r: RULES[r] for r in b.rule_ids},
        "conditions": b.conditions, "scope": b.scope, "versions": VERSIONS}, ensure_ascii=False, sort_keys=True) for b in blocks)
