"""Explicit natal relationships before optional symbol hooks.

This module never consumes heuristic scores, LLM prose or star counts. It does
not implement final strength, special formation, useful-element or period rules.
"""
import json
from functools import lru_cache
from pathlib import Path

from app.domain.saju.natal_structure_contracts import NatalConclusion, NatalStructureBlock, NatalStructureReading
from app.domain.saju.pydantic_compat import model_to_dict
from app.domain.saju.services.build_chart_characteristics import (
    KEYS, MAIN_STEMS, _known_midnight_alternate, _occurrences, _relation, _stem,
)
from app.domain.saju.services.build_manse import HIDDEN_STEMS_BY_BRANCH


STEM_ELEMENT = dict(zip("甲乙丙丁戊己庚辛壬癸", ("wood", "wood", "fire", "fire", "earth", "earth", "metal", "metal", "water", "water")))


@lru_cache(maxsize=1)
def catalog():
    return json.loads(Path(__file__).with_name("data").joinpath("natal_structure_catalog.json").read_text(encoding="utf-8"))


def derive_profile(chart, hidden, refs):
    """Exact structural occurrences, not weighted strength or population ranks."""
    occurrences = _occurrences(chart, hidden, refs)
    day = chart["day"][0]
    roots = [key for key in KEYS if any(STEM_ELEMENT[_stem(s)] == STEM_ELEMENT[day] for s in hidden[key])]
    month_main = MAIN_STEMS[chart["month"][1]]
    visible = {g: [o for o in occurrences if o["layer"] == "visible" and o["group"] == g]
               for g in ("peer", "output", "wealth", "officer", "resource")}
    resources = [o for o in occurrences if o["group"] == "resource"]
    wealth = [o for o in occurrences if o["group"] == "wealth"]
    return {"chart": dict(chart), "day_stem": day, "day_element": STEM_ELEMENT[day],
            "month_main_stem": month_main, "month_group": _relation(day, month_main)[1],
            "root_pillars": roots, "resource_present": bool(resources), "resource_occurrences": resources,
            "visible_groups": visible, "wealth_occurrences": wealth,
            "wealth_layer": "visible" if visible["wealth"] else "hidden_only" if wealth else "absent",
            "occurrences": occurrences,
            "winter_metal": STEM_ELEMENT[day] == "metal" and chart["month"][1] in "亥子丑",
            "fire_present": any(STEM_ELEMENT[v[0]] == "fire" or any(STEM_ELEMENT[_stem(s)] == "fire" for s in hidden[k]) for k, v in chart.items()),
            "degree_scope": "positions_and_relationships_only_not_final_strength"}


def render_structure(profile, refs, locale):
    """Select bounded rules with their complete input and counterevidence."""
    data = catalog()
    all_refs = list(dict.fromkeys(refs[k] for k in KEYS))
    blocks = []

    def add(block_id, copy, rule_ids):
        blocks.append(NatalStructureBlock(id=block_id, title=copy["title"], text=copy["text"],
                                         rule_ids=rule_ids, fact_ids=all_refs))

    focus = dict(data["month"][profile["month_group"]][locale])
    if profile["month_group"] == "output" and profile["visible_groups"]["resource"]:
        focus["text"] += "\n\n" + data["combinations"]["output_resource"][locale]
        add("month_context", focus, ["month_context", "output_resource"])
    else:
        add("month_context", focus, ["month_context"])
    support_key = ("root" if profile["root_pillars"] else "no_root") + ("_resource" if profile["resource_present"] else "_no_resource")
    add("roots_and_support", data["support"][support_key][locale], ["roots_and_support"])
    add("wealth_layer", data["wealth"][profile["wealth_layer"]][locale], ["wealth_layer"])
    if profile["visible_groups"]["output"] and profile["visible_groups"]["officer"]:
        add("output_officer", data["combinations"]["output_officer"][locale], ["output_officer"])
    return blocks


def select_conclusions(profile, blocks, locale):
    """Connect applied month/support findings before publishing; no new fortune rule.

    Analysis blocks remain complete evidence, including wealth locations. A
    location-only finding is not a personal conclusion in the core chapter.
    """
    found = {b.id: b for b in blocks}
    month, support = found["month_context"], found["roots_and_support"]
    subjects = {
        "ko": {"output": "만들고 표현하는 일", "resource": "배움과 준비", "wealth": "돈과 보상을 다루는 일",
               "officer": "맡은 역할과 책임", "peer": "자신의 입장과 동료·경쟁 관계"},
        "en": {"output": "Making and expressing", "resource": "Learning and preparation", "wealth": "Money and rewards",
               "officer": "Roles and responsibilities", "peer": "Your position alongside peers"},
    }
    subject = subjects[locale][profile["month_group"]]
    # These paragraphs include the meaning and its countercondition. Selecting
    # only the opening sentence turned a bounded reading into a bare label.
    paragraphs = [month.text]
    particle = "과" if (ord(subject[-1]) - 0xAC00) % 28 else "와"
    link = (subject + particle + " 함께 볼 조건도 있어. " if locale == "ko" else
            "Alongside " + subject[0].lower() + subject[1:] + ", consider the chart's backing. ")
    paragraphs.append(link + support.text)
    sources = [month, support]
    result = [NatalConclusion(id="primary_with_support", title=month.title, text="\n\n".join(paragraphs),
        one_line=catalog()["one_line"][profile["month_group"]][locale],
        source_block_ids=[b.id for b in sources], rule_ids=list(dict.fromkeys(r for b in sources for r in b.rule_ids)),
        fact_ids=list(dict.fromkeys(f for b in sources for f in b.fact_ids)),
        conditions={"month_group": profile["month_group"], "root_pillars": profile["root_pillars"],
                    "resource_present": profile["resource_present"]})]
    if "output_officer" in found:
        b = found["output_officer"]
        result.append(NatalConclusion(id=b.id, title=b.title, text=b.text, source_block_ids=[b.id],
            rule_ids=b.rule_ids, fact_ids=b.fact_ids,
            conditions={"visible_output": profile["visible_groups"]["output"],
                        "visible_officer": profile["visible_groups"]["officer"]}))
    return result


def structure_memo(profile, blocks, locale):
    ko = locale == "ko"
    group_names = {"peer": "비겁", "output": "식상", "wealth": "재성", "officer": "관성", "resource": "인성"} if ko else {
        "peer": "peer", "output": "output", "wealth": "wealth", "officer": "officer", "resource": "resource"}
    positions = {"year": "년", "month": "월", "day": "일", "time": "시"} if ko else {k: k for k in KEYS}
    chart = " · ".join(profile["chart"][k] for k in KEYS)
    roots = ", ".join(positions[k] for k in profile["root_pillars"]) or ("없음" if ko else "none")
    text = (f"### 명식 구조\n{chart}\n일간 {profile['day_stem']} / 월지 본기 {profile['month_main_stem']} / 월의 관계 {group_names[profile['month_group']]}\n같은 오행의 지장간 뿌리 위치: {roots}. 인성 존재: {'있음' if profile['resource_present'] else '없음'}." if ko else
            f"### Natal structure\n{chart}\nDay stem {profile['day_stem']} / month's main stem {profile['month_main_stem']} / relationship {group_names[profile['month_group']]}\nSame-element hidden root positions: {roots}. Resource relationship present: {profile['resource_present']}.")
    entries = []
    for o in profile["occurrences"]:
        label = ("천간" if o["layer"] == "visible" else "지장간") if ko else o["layer"]
        entry = f"{positions[o['pillar']]} {label}: {o['god'] if ko else group_names[o['group']]}"
        if o["month_main"]:
            entry += " (월지 본기)" if ko else " (month main)"
        entries.append(entry)
    text += "\n\n" + "\n".join(entries)
    if profile["winter_metal"]:
        text += ("\n\n### 계절의 반대 단서\n겨울 금의 한랭을 읽는 조후 관점이 있다. " + ("화가 실제 존재한다." if profile["fire_present"] else "화는 실제 명식에서 잡히지 않는다.") + " 화는 금을 제어하는 관성이기도 하다. 온기라는 관점만으로 화를 최종 용신이나 좋은 운으로 확정하지 않는다." if ko else
                 "\n\n### Seasonal counterconsideration\nWinter metal has a traditional cold/warm consideration. Fire present: " + str(profile["fire_present"]) + ". Fire also controls metal in the officer relationship. This does not select fire as a final useful element or favorable period.")
    rule_ids = list(dict.fromkeys(r for b in blocks for r in b.rule_ids))
    if profile["winter_metal"]:
        rule_ids.append("winter_metal_note")
    source_ids = set(s for r in rule_ids for s in catalog()["rules"][r]["sources"])
    text += "\n\n" + ("### 적용 규칙과 출처\n" if ko else "### Applied rules and sources\n") + ", ".join(rule_ids)
    for source in catalog()["sources"]:
        if source["id"] in source_ids:
            text += "\n" + source.get("url", source.get("reference", ""))
    text += ("\n\n월의 중심·뿌리·인성·재성 위치의 제한된 프로젝트 풀이다. 합충의 성립/제화/종격은 판정하지 않았다. 신강·신약·격국·최종 용신, 능력/재산/사건 시기/인구 대비 희소성은 판정하지 않았다. 뿌리 개수나 오행 단순 비율을 강약 점수로 바꾸지 않았다. 전문가 검토와 예측 정확성 검증은 미완료다." if ko else
             "\n\nBounded project reading of month context, roots, support and wealth positions. Combinations, transformations and special formations are not evaluated. Final strength, formation, useful element, ability, wealth, event timing and population rarity are not judged. Root counts and raw element ratios are not strength scores. Expert review and predictive validation are incomplete.")
    return text


def build_natal_structure(*, base, locale):
    result = NatalStructureReading()
    if not base.manse.meta.hour_pillar_enabled or set(base.manse.meta.visible_pillar_keys) != set(KEYS):
        result.blocked_reasons = ["incomplete_birth_time_or_pillars"]
        return result
    chart, hidden, refs = {}, {}, {}
    for key in KEYS:
        p = getattr(base.manse.pillars, key)
        if not p.enabled or p.gan_zhi != (p.stem or "") + (p.branch or ""):
            result.blocked_reasons = ["inconsistent_chart"]
            return result
        chart[key], hidden[key], refs[key] = p.gan_zhi, p.hidden_stems, "natal.pillar." + key
        result.facts.append({"id": refs[key], "source_path": "manse.pillars." + key, "value": model_to_dict(p)})
    if base.manse.meta.day_master != chart["day"][0]:
        result.blocked_reasons = ["inconsistent_day_master"]
        return result
    critical = [f for f in base.result.uncertainty_summary if f.severity == "critical"]
    alternate = _known_midnight_alternate(base, chart) if critical else None
    if critical and alternate is None:
        result.blocked_reasons = [f.code for f in critical]
        return result
    try:
        profile = derive_profile(chart, hidden, refs)
        blocks = render_structure(profile, refs, locale)
        conclusions = select_conclusions(profile, blocks, locale)
        memo = structure_memo(profile, blocks, locale)
        memo += "\n\n" + ("### 본문 결론의 선정\n" if locale == "ko" else "### Main conclusion selection\n")
        memo += "\n".join(c.id + ": " + ", ".join(c.source_block_ids) + "; " +
                          json.dumps(c.conditions, ensure_ascii=False, sort_keys=True) for c in conclusions)
        memo += "\n\n" + "\n\n".join(b.title + "\n" + b.text for b in blocks)
        if alternate:
            other_chart, candidate, path, convention = alternate
            other_refs = {k: "natal.alternate" for k in KEYS}
            other_hidden = {k: HIDDEN_STEMS_BY_BRANCH[v[1]] for k, v in other_chart.items()}
            other_profile = derive_profile(other_chart, other_hidden, other_refs)
            other_blocks = render_structure(other_profile, other_refs, locale)
            other_conclusions = select_conclusions(other_profile, other_blocks, locale)
            result.facts.append({"id": "natal.alternate", "source_path": path, "value": candidate})
            result.comparisons.append({"convention": convention, "input_fact_id": "natal.alternate",
                                       "profile": other_profile, "blocks": [model_to_dict(b) for b in other_blocks],
                                       "conclusions": [model_to_dict(c) for c in other_conclusions]})
            memo += "\n\n" + ("### 다른 날짜 기준으로 읽으면\n" if locale == "ko" else "### Under the other day-change convention\n")
            memo += structure_memo(other_profile, other_blocks, locale)
            memo += "\n\n" + "\n\n".join(b.title + "\n" + b.text for b in other_blocks)
            result.assumption = ("현재 계산 기준의 명식을 가정한 풀이야. 날짜를 바꾸는 기준에 따라 특징이 달라질 수 있어." if locale == "ko" else
                                 "This reading assumes the selected calculation convention. Another day-change convention can change these features.")
    except (ValueError, KeyError, TypeError):
        result.blocked_reasons = ["missing_or_inconsistent_structural_facts"]
        return result
    result.profile, result.blocks, result.conclusions, result.memo_body = profile, blocks, conclusions, memo
    result.status = "conditional" if alternate else "available"
    return result
