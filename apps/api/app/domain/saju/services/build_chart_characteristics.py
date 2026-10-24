"""Project structural readings from immutable public chart facts.

Only the known midnight-convention difference may receive a separate, assumed
primary reading. All legacy guards remain intact. Alternate interpretations are
rebuilt from their own day stem, not copied from the selected primary.
"""
from lunar_python.util import LunarUtil

from app.domain.saju.chart_characteristics import (
    CharacteristicComparison, CharacteristicFact, ChartCharacteristics, evaluate_characteristics,
)
from app.domain.saju.localization import STEM_LABELS, localize_ten_god
from app.domain.saju.pydantic_compat import model_to_dict
from app.domain.saju.services.build_manse import HIDDEN_STEMS_BY_BRANCH


KEYS = ("year", "month", "day", "time")
MAIN_STEMS = dict(zip("子丑寅卯辰巳午未申酉戌亥", "癸己甲乙戊丙丁己庚辛戊壬"))
GOD_GROUPS = {"비견": "peer", "겁재": "peer", "식신": "output", "상관": "output",
              "정재": "wealth", "편재": "wealth", "정관": "officer", "편관": "officer",
              "정인": "resource", "편인": "resource"}


def _stem(value):
    if value in STEM_LABELS:
        return value
    for hanja, names in STEM_LABELS.items():
        if value in names.values():
            return hanja
    raise ValueError("Unknown stem")


def _relation(day, target):
    raw = LunarUtil.SHI_SHEN.get(day + _stem(target))
    god = localize_ten_god(raw or "", "ko")
    if god not in GOD_GROUPS:
        raise ValueError("Unknown canonical ten-god relation")
    return god, GOD_GROUPS[god]


def _validate_chart(chart):
    if set(chart) != set(KEYS):
        raise ValueError("Incomplete chart")
    for letters in chart.values():
        if not isinstance(letters, str) or len(letters) != 2 or letters[0] not in STEM_LABELS or letters[1] not in MAIN_STEMS:
            raise ValueError("Invalid chart characters")
        if letters not in LunarUtil.JIA_ZI:
            raise ValueError("Invalid stem-branch pair")


def _occurrences(chart, hidden, refs):
    _validate_chart(chart)
    day = chart["day"][0]
    result = []
    for key in KEYS:
        branch = chart[key][1]
        expected = {_stem(s) for s in HIDDEN_STEMS_BY_BRANCH[branch]}
        actual = {_stem(s) for s in hidden[key]}
        if expected != actual:
            raise ValueError("Missing or inconsistent explicit hidden stems")
        if key != "day":
            god, group = _relation(day, chart[key][0])
            result.append({"pillar": key, "layer": "visible", "god": god, "group": group,
                           "fact_id": refs[key], "month_main": False})
        # Validate the supplied set first, then use the shared table's stable
        # order; a presentation reorder must not change a reading or its memo.
        for target in (_stem(s) for s in HIDDEN_STEMS_BY_BRANCH[branch]):
            god, group = _relation(day, target)
            result.append({"pillar": key, "layer": "hidden", "god": god, "group": group,
                           "fact_id": refs[key], "month_main": key == "month" and target == MAIN_STEMS[branch]})
    return result


def _known_midnight_alternate(base, primary):
    """Fail closed unless ALL critical differences are explained by this pair."""
    critical = [f for f in base.result.uncertainty_summary if f.severity == "critical"]
    if not critical or any(f.code not in {"midnight_rule_changes_day_pillar", "primary_differs_from_candidate"} for f in critical):
        return None
    midnight = next(((i, f) for i, f in enumerate(base.result.uncertainty_summary)
                     if f.code == "midnight_rule_changes_day_pillar" and f.severity == "critical"), None)
    if midnight is None:
        return None
    index, flag = midnight
    candidates = [flag.evidence.get(k) for k in ("sect1_23_changes_day", "sect2_00_changes_day")]
    if any(not isinstance(c, dict) for c in candidates):
        return None
    charts = [{key: c.get(key + "_pillar" if key != "time" else "hour_pillar") for key in KEYS} for c in candidates]
    try:
        for chart in charts:
            _validate_chart(chart)
    except ValueError:
        return None
    if charts[0]["year"] != charts[1]["year"] or charts[0]["month"] != charts[1]["month"] or charts[0]["day"] == charts[1]["day"]:
        return None
    if primary not in charts:
        return None
    for c, rule in zip(candidates, ("sect1_23_changes_day", "sect2_00_changes_day")):
        if c.get("midnight_rule") != rule or c.get("day_pillar_rule") != rule:
            return None
    actual_fields = {"hour_pillar" if k == "time" else k + "_pillar" for k in KEYS if charts[0][k] != charts[1][k]}
    if set(midnight[1].evidence.get("changed_fields", [])) != actual_fields:
        return None
    for flag in critical:
        if not set(flag.affected_fields) <= {"day_pillar", "hour_pillar"}:
            return None
        if flag.code == "primary_differs_from_candidate":
            if set(flag.evidence.get("changed_fields", [])) != actual_fields:
                return None
            if flag.evidence.get("primary") is None:
                return None
            if any(flag.evidence["primary"].get(k + "_pillar" if k != "time" else "hour_pillar") != primary[k] for k in KEYS):
                return None
            compared = flag.evidence.get("candidates", [])
            if not compared:
                return None
            for candidate in compared:
                candidate_chart = {k: candidate.get(k + "_pillar" if k != "time" else "hour_pillar") for k in KEYS}
                if candidate_chart not in charts or candidate.get("midnight_rule") not in {"sect1_23_changes_day", "sect2_00_changes_day"} or candidate.get("day_pillar_rule") != candidate.get("midnight_rule"):
                    return None
    alternate_index = 1 if primary == charts[0] else 0
    rule = ("sect1_23_changes_day", "sect2_00_changes_day")[alternate_index]
    return charts[alternate_index], candidates[alternate_index], f"result.uncertainty_summary[{index}].evidence.{rule}", rule


def build_chart_characteristics(*, base, locale):
    ko = locale == "ko"
    result = ChartCharacteristics(status="blocked_calculation", scale_note=(
        "표시한 정도는 이 프로젝트 풀이에서의 비중이야. 실제 능력이나 피해의 크기를 재는 등급은 아니야." if ko else
        "Emphasis means prominence in this project's reading, not a measured level of ability or harm."))
    if not base.manse.meta.hour_pillar_enabled or set(base.manse.meta.visible_pillar_keys) != set(KEYS):
        result.blocked_reasons = ["incomplete_birth_time_or_pillars"]
        return result
    primary, hidden, refs = {}, {}, {}
    for key in KEYS:
        pillar = getattr(base.manse.pillars, key)
        if not pillar.enabled or pillar.gan_zhi != (pillar.stem or "") + (pillar.branch or ""):
            result.blocked_reasons = ["inconsistent_chart"]
            return result
        primary[key], hidden[key], refs[key] = pillar.gan_zhi, pillar.hidden_stems, "characteristics.pillar." + key
        result.facts.append(CharacteristicFact(id=refs[key], value=model_to_dict(pillar), source_path="manse.pillars." + key))
    if base.manse.meta.day_master != primary["day"][0]:
        result.blocked_reasons = ["inconsistent_day_master"]
        return result
    critical = [f for f in base.result.uncertainty_summary if f.severity == "critical"]
    alternate = _known_midnight_alternate(base, primary) if critical else None
    if critical and alternate is None:
        result.blocked_reasons = [f.code for f in critical]
        return result
    try:
        occurrences = _occurrences(primary, hidden, refs)
    except ValueError:
        result.blocked_reasons = ["missing_or_inconsistent_structural_facts"]
        return result
    result.items = evaluate_characteristics(occurrences=occurrences, locale=locale)
    for item in result.items:
        item.fact_ids = list(dict.fromkeys([refs["day"]] + item.fact_ids))
    result.derivations.append({"id": "selected_chart", "day_stem": primary["day"][0], "chart": primary,
        "occurrences": occurrences, "main_stem_table": MAIN_STEMS, "hidden_stem_policy": "build_manse.HIDDEN_STEMS_BY_BRANCH",
        "rule_source": "project-characteristics-policy", "emphasis_scope": "editorial_prominence_only"})
    if alternate is not None:
        chart, candidate, source_path, rule = alternate
        ref = "characteristics.alternate"
        result.facts.append(CharacteristicFact(id=ref, value=candidate, source_path=source_path))
        other_hidden = {key: HIDDEN_STEMS_BY_BRANCH[letters[1]] for key, letters in chart.items()}
        try:
            other_occurrences = _occurrences(chart, other_hidden, {key: ref for key in KEYS})
            other = evaluate_characteristics(occurrences=other_occurrences, locale=locale)
        except ValueError:
            result.items = []
            result.blocked_reasons = ["invalid_alternate_derivation"]
            return result
        selected_by_id, other_by_id = {i.id: i for i in result.items}, {i.id: i for i in other}
        common = set(selected_by_id) & set(other_by_id)
        unchanged = sorted(i for i in common if selected_by_id[i].emphasis == other_by_id[i].emphasis)
        changed = sorted(common - set(unchanged))
        label = ("0시 날짜 변경 기준" if rule == "sect2_00_changes_day" else "23시 날짜 변경 기준") if ko else (
            "Midnight day-change convention" if rule == "sect2_00_changes_day" else "11 pm day-change convention")
        result.comparisons.append(CharacteristicComparison(label=label, chart=chart, items=other, unchanged=unchanged,
            changed=changed, added=sorted(set(other_by_id) - set(selected_by_id)), removed=sorted(set(selected_by_id) - set(other_by_id))))
        result.derivations.append({"id": "alternate_chart", "input_fact_id": ref, "day_stem": chart["day"][0],
            "occurrences": other_occurrences, "hidden_stem_policy": "build_manse.HIDDEN_STEMS_BY_BRANCH", "rule": rule})
        result.assumption = ("현재 계산 기준의 명식을 가정한 풀이야. 날짜를 바꾸는 기준에 따라 특징이 달라질 수 있어." if ko else
                             "This reading assumes the selected calculation convention. Another day-change convention can change these features.")
        result.status = "conditional" if result.items else "no_matching_rules"
    else:
        result.status = "available" if result.items else "no_matching_rules"
    return result
