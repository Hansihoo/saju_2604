"""Pure project interpretations of chart structure; no engine, HTTP or model calls.

Emphasis describes editorial prominence, never ability, harm, chart strength,
event probability or a population rank. Facts and interpretation stay separate.
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field
from app.domain.saju.localization import localize_ten_god


GROUPS = ("peer", "output", "wealth", "officer", "resource")
GROUP_LABELS = {
    "ko": {"peer": "자기주도·동료", "output": "표현·결과물", "wealth": "돈·자원", "officer": "책임·기준", "resource": "학습·지원"},
    "en": {"peer": "independence and peers", "output": "expression and output", "wealth": "money and resources", "officer": "responsibility and standards", "resource": "learning and support"},
}
LEVEL_LABELS = {"ko": {"prominent": "두드러짐", "noticeable": "눈에 띔", "supporting": "보조 수준"},
                "en": {"prominent": "Prominent", "noticeable": "Noticeable", "supporting": "Supporting"}}
POSITIONS = {"ko": {"year": "년주", "month": "월주", "day": "일주", "time": "시주"},
             "en": {"year": "year", "month": "month", "day": "day", "time": "hour"}}
CRITERIA_LABELS = {"ko": {"visible_non_day_stem": "일간을 제외한 천간에 나타남", "month_branch_main_stem": "월지 본기의 십성과 일치", "hidden_in_a_different_pillar": "해당 천간과 다른 기둥의 지장간에도 나타남"},
                   "en": {"visible_non_day_stem": "present in a visible non-day stem", "month_branch_main_stem": "matches the month branch's main-stem relation", "hidden_in_a_different_pillar": "also present inside a different pillar"}}


class CharacteristicFact(BaseModel):
    id: str
    value: Any
    source_path: str


class CharacteristicItem(BaseModel):
    id: str
    direction: Literal["advantage", "burden"]
    title: str
    conclusion: str
    reason: str
    condition: str
    emphasis: Literal["prominent", "noticeable", "supporting"]
    emphasis_label: str
    emphasis_reason: str
    emphasis_criteria: List[str]
    focus_group: str
    fact_ids: List[str]
    rule_id: str
    rule_version: int
    source_id: str = "project-characteristics-policy"
    counter_signals: List[str] = Field(default_factory=list)
    memo_body: str


class CharacteristicComparison(BaseModel):
    label: str
    chart: Dict[str, str]
    items: List[CharacteristicItem]
    unchanged: List[str] = Field(default_factory=list)
    changed: List[str] = Field(default_factory=list)
    added: List[str] = Field(default_factory=list)
    removed: List[str] = Field(default_factory=list)


class ChartCharacteristics(BaseModel):
    status: Literal["available", "conditional", "blocked_calculation", "no_matching_rules"]
    scope: Literal["project_conditional_characteristics"] = "project_conditional_characteristics"
    assumption: str = ""
    scale_note: str
    items: List[CharacteristicItem] = Field(default_factory=list)
    comparisons: List[CharacteristicComparison] = Field(default_factory=list)
    facts: List[CharacteristicFact] = Field(default_factory=list)
    derivations: List[Dict[str, Any]] = Field(default_factory=list)
    blocked_reasons: List[str] = Field(default_factory=list)
    expert_review: Literal["not_completed"] = "not_completed"
    empirical_validation: Literal["not_completed"] = "not_completed"
    versions: Dict[str, str] = Field(default_factory=lambda: {
        "facts": "characteristics-facts-2026-10-09.2",
        "knowledge": "characteristics-knowledge-2026-10-09.2",
        "rules": "characteristics-rules-2026-10-09.2",
        "scale": "characteristics-emphasis-2026-10-09.1",
    "copy": "characteristics-copy-2026-10-09.3",
        "format": "chart-characteristics-v1",
    })


@lru_cache(maxsize=1)
def load_characteristic_catalog():
    data = json.loads((Path(__file__).parent / "data" / "chart_characteristics_catalog.json").read_text(encoding="utf-8"))
    ids = set()
    for rule in data["rules"]:
        allowed_fields = {"id", "version", "source_id", "status", "direction", "focus", "requires", "counter_groups", "wording", "minimum_emphasis", "exclude_qualifying", "minimum_visible_focus"}
        if set(rule) - allowed_fields or rule.get("minimum_emphasis") not in {None, "prominent"}:
            raise ValueError("Unregistered characteristic condition")
        if rule["id"] in ids or rule["focus"] not in GROUPS or rule["direction"] not in {"advantage", "burden"}:
            raise ValueError("Invalid characteristic rule identity")
        ids.add(rule["id"])
        if len(set(rule["requires"])) < 2 or not set(rule["requires"]) <= set(GROUPS) or rule["focus"] not in rule["requires"]:
            raise ValueError("Characteristic rule needs two registered groups")
        if rule["source_id"] != "project-characteristics-policy" or rule["status"] != "active_project_policy":
            raise ValueError("Unregistered characteristic source/status")
        if any(not set(rule.get(k, [])) <= set(GROUPS) for k in ("counter_groups", "exclude_qualifying")):
            raise ValueError("Unregistered characteristic group")
        if type(rule.get("minimum_visible_focus", 0)) is not int or rule.get("minimum_visible_focus", 0) not in (0, 2):
            raise ValueError("Unregistered visibility condition")
        for locale in ("ko", "en"):
            if any(not rule["wording"][locale].get(key) for key in ("title", "conclusion", "reason", "condition")):
                raise ValueError("Incomplete characteristic wording")
    return data


def group_support(occurrences, group):
    """Three structural criteria about ONE group. Day stem is not evidence."""
    selected, seen = [], set()
    for o in occurrences:
        identity = (o["pillar"], o["layer"], o["god"], o.get("month_main", False), o["fact_id"])
        if o["group"] == group and identity not in seen:
            seen.add(identity)
            selected.append(o)
    visible = {o["pillar"] for o in selected if o["layer"] == "visible"}
    hidden = {o["pillar"] for o in selected if o["layer"] == "hidden"}
    criteria = []
    if visible:
        criteria.append("visible_non_day_stem")
    if any(o.get("month_main") for o in selected):
        criteria.append("month_branch_main_stem")
    if visible and any(h != v for h in hidden for v in visible):
        criteria.append("hidden_in_a_different_pillar")
    level = "prominent" if len(criteria) == 3 else "noticeable" if len(criteria) == 2 else "supporting"
    # Minor/transition hidden stems alone cannot trigger a personal conclusion.
    return {"qualifies": bool(visible or "month_branch_main_stem" in criteria), "criteria": criteria,
            "level": level, "selected": selected}


def evaluate_characteristics(*, occurrences, locale, catalog=None):
    """Return matched project readings, without merging opposite directions."""
    data = catalog or load_characteristic_catalog()
    supports = {g: group_support(occurrences, g) for g in GROUPS}
    candidates = []
    for rule in data["rules"]:
        if not all(supports[g]["qualifies"] for g in rule["requires"]):
            continue
        focus = supports[rule["focus"]]
        if len({o["pillar"] for o in focus["selected"] if o["layer"] == "visible"}) < rule.get("minimum_visible_focus", 0):
            continue
        if rule.get("minimum_emphasis") == "prominent" and focus["level"] != "prominent":
            continue
        if any(supports[g]["qualifies"] for g in rule.get("exclude_qualifying", [])):
            continue
        refs = list(dict.fromkeys(o["fact_id"] for o in occurrences if o["group"] in rule["requires"]))
        if not refs:
            continue
        copy = rule["wording"][locale]
        counter = [g for g in rule.get("counter_groups", []) if supports[g]["qualifies"]]
        positions = []
        for group in rule["requires"]:
            locs = list(dict.fromkeys(POSITIONS[locale][o["pillar"]] + (" 천간" if o["layer"] == "visible" else " 지장간") + " " + o["god"] if locale == "ko" else
                                     POSITIONS[locale][o["pillar"]] + " " + o["layer"] + " " + localize_ten_god(o["god"], "en") for o in supports[group]["selected"]))
            positions.append(GROUP_LABELS[locale][group] + ": " + ", ".join(locs))
        disclaimer = ("프로젝트의 조건부 해석과 본문 비중 기준입니다. 신강·격국 성립·실제 능력/피해의 크기를 판정하지 않습니다. 전문가 검토·실증 검증 미완료." if locale == "ko" else
                      "Project conditional interpretation and editorial prominence, not chart strength, a classical pattern verdict, measured ability or harm. Expert and empirical validation are incomplete.")
        degree_note = (("풀이 비중의 확인 조건: " if locale == "ko" else "Conditions for reading emphasis: ") +
                       "; ".join(CRITERIA_LABELS[locale][c] for c in focus["criteria"]))
        focus_note = ("비중의 초점: " if locale == "ko" else "Focus of emphasis: ") + GROUP_LABELS[locale][rule["focus"]]
        memo = "\n\n".join(positions + [focus_note, degree_note, disclaimer])
        if locale == "ko":
            where = ("태어난 달의 바탕과 겉글자, 다른 자리의 안쪽 글자에서 함께 이어져" if focus["level"] == "prominent" else
                     "겉글자와 태어난 달의 바탕에 함께 나타나" if "month_branch_main_stem" in focus["criteria"] and "visible_non_day_stem" in focus["criteria"] else
                     "겉글자와 다른 자리의 안쪽 글자에 함께 나타나" if focus["level"] == "noticeable" else
                     "겉글자에 나타나지만 달의 바탕과 다른 자리까지 조건이 모두 겹치지는 않아" if "visible_non_day_stem" in focus["criteria"] else
                     "태어난 달의 바탕에서 확인되지만 겉글자까지 함께 나타나지는 않아")
            emphasis_reason = GROUP_LABELS[locale][rule["focus"]] + "의 흐름이 " + where + ". 이 조건으로 ‘" + LEVEL_LABELS[locale][focus["level"]] + "’으로 표시했어."
        else:
            where = ("appears in the month basis, a visible stem and inside a different pillar" if focus["level"] == "prominent" else
                     "appears in both a visible stem and the month basis" if "month_branch_main_stem" in focus["criteria"] and "visible_non_day_stem" in focus["criteria"] else
                     "appears in a visible stem and inside a different pillar" if focus["level"] == "noticeable" else
                     "appears visibly, but the month-basis and other-pillar conditions do not all overlap" if "visible_non_day_stem" in focus["criteria"] else
                     "appears in the month basis without also appearing visibly")
            emphasis_reason = "The " + GROUP_LABELS[locale][rule["focus"]] + " pattern " + where + ". That is why its reading emphasis is " + LEVEL_LABELS[locale][focus["level"]].lower() + "."
        candidates.append(CharacteristicItem(id=rule["id"], direction=rule["direction"],
            focus_group=rule["focus"], emphasis=focus["level"], emphasis_label=LEVEL_LABELS[locale][focus["level"]],
            emphasis_criteria=focus["criteria"], emphasis_reason=emphasis_reason, fact_ids=refs, rule_id=rule["id"], rule_version=rule["version"],
            counter_signals=counter, memo_body=memo, **copy))
    ranks = {"prominent": 0, "noticeable": 1, "supporting": 2}
    candidates.sort(key=lambda item: ranks[item.emphasis])
    result, seen = [], set()
    for item in candidates:
        # Same focus/direction is one evidence family, not additional proof.
        family = (item.direction, item.focus_group)
        if family in seen or sum(i.direction == item.direction for i in result) >= 2:
            continue
        seen.add(family)
        result.append(item)
    return result
