"""Select bounded personal themes only from valid, independently matched facts.

No population comparison, whole-chart strength, event timing or star-count score.
The only conditional branch allowed is the already-validated day-convention pair.
"""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path

from lunar_python.util import LunarUtil

from app.domain.saju.distinctive_contracts import DistinctiveReading, DistinctiveTheme, DistinctiveVersions
from app.domain.saju.pydantic_compat import model_to_dict
from app.domain.saju.reading_information import _valid_matches
from app.domain.saju.services.build_chart_characteristics import KEYS, _known_midnight_alternate, _validate_chart, _stem
from app.domain.saju.services.build_manse import HIDDEN_STEMS_BY_BRANCH
from app.domain.saju.services.calculate_special_stars import build_special_stars
from app.domain.saju.schemas import MansePillar


@lru_cache(maxsize=1)
def catalog():
    return json.loads((Path(__file__).parent / "data/distinctive_reading_catalog.json").read_text(encoding="utf-8"))


CLASH = dict(zip("子丑寅卯辰巳午未申酉戌亥", "午未申酉戌亥子丑寅卯辰巳"))


def _versions():
    data = catalog()
    return DistinctiveVersions(knowledge=data["knowledge_version"], rules=data["rules_version"], copy=data["copy_version"])


def _unique_matches(matches):
    return list({json.dumps(model_to_dict(m), sort_keys=True, ensure_ascii=False): m for m in matches}.values())


def _supported_matches(base):
    result = {}
    for index, star in enumerate(base.manse.special_stars):
        matches = _valid_matches(star, base)
        if matches:
            result[star.key] = (index, star, _unique_matches(matches))
    return result


def _clear_position(base, match):
    # Conservative selection for the favorable theme: no claimed relief from
    # a clash/void. These conditions do not establish strength or a major blessing.
    void = getattr(base.manse.pillars.day, "xun_kong", "") or ""
    branches = [getattr(base.manse.pillars, k).branch for k in KEYS]
    return match.branch not in void and CLASH[match.branch] not in branches


def _select(base, locale, result):
    found = _supported_matches(base)
    chosen = []
    wen = found.get("munchang-gwiin")
    cover_methods = {"hwagae-year-branch": "triad-hwagae-year-branch", "hwagae-day-branch": "triad-hwagae-day-branch"}
    covers = [v for k, v in found.items() if k in cover_methods and v[1].method_id == cover_methods[k]]
    if wen and wen[1].method_id == "day-stem-fixed-table":
        wen_matches = [m for m in wen[2] if _clear_position(base, m)]
        cover_matches = [(v, m) for v in covers for m in v[2] if m.pillar_key == "day" and _clear_position(base, m)]
        if wen_matches and cover_matches:
            chosen.append(("study_with_solitude", [(wen[0], wen[1], wen_matches)] +
                [(v[0], v[1], [m for item, m in cover_matches if item[1].key == v[1].key]) for v, _ in cover_matches]))
    attention, friction = found.get("wangji-dohwa"), found.get("wonjin")
    if (attention and attention[1].method_id == "visible-wangji-branch-common-kr" and
            friction and friction[1].method_id == "visible-branch-pair-common-kr" and
            any(m.pillar_key == "day" or m.counterpart_pillar_key == "day" for m in friction[2])):
        chosen.append(("attention_with_friction", [attention, (friction[0], friction[1],
            [m for m in friction[2] if m.pillar_key == "day" or m.counterpart_pillar_key == "day"])]))
    rules = {r["id"]: r for r in catalog()["rules"]}
    for rule_id, evidence in chosen:
        rule = rules[rule_id]
        refs, notes, eligible = ["distinctive.chart"], [], {}
        seen = set()
        for index, star, matches in evidence:
            if star.key in seen:
                continue
            seen.add(star.key)
            ref = "distinctive.star." + star.key
            refs.append(ref)
            eligible[ref] = [model_to_dict(m) for m in _unique_matches(matches)]
            result.facts.append({"id": ref, "value": model_to_dict(star, exclude_none=True), "source_path": f"manse.special_stars[{index}]"})
            # Only actual enabled matches, each pair once, never a duplicated score.
            positions = sorted({tuple(sorted((m.pillar_key, m.counterpart_pillar_key))) if m.counterpart_pillar_key else (m.pillar_key,) for m in matches})
            notes.append(f"{star.label}: {star.method_id}; " + "; ".join(" ↔ ".join(p + "=" + getattr(base.manse.pillars, p).gan_zhi for p in pair) for pair in positions))
        question_ids = list(rule["questions"])
        if "features.taegeuk" in question_ids:
            tae = found.get("taegeuk-gwiin")
            if tae is None or tae[1].method_id != "day-stem-fixed-table":
                question_ids.remove("features.taegeuk")
            else:
                index, star, _ = tae
                ref = "distinctive.star." + star.key
                refs.append(ref)
                eligible[ref] = [model_to_dict(m) for m in tae[2]]
                result.facts.append({"id": ref, "value": model_to_dict(star, exclude_none=True), "source_path": f"manse.special_stars[{index}]"})
                notes.append(f"{star.label}: {star.method_id}; " + ", ".join(m.pillar_key + "=" + m.gan_zhi for m in tae[2]))
        sources = [catalog()["sources"][s] for s in rule["sources"]]
        if "features.taegeuk" in question_ids:
            sources.append(catalog()["sources"]["sanming-taegeuk"])
        notes.extend(s["title"] + ": " + s.get("url", s.get("path", "")) + "\n" + s["scope"] for s in sources)
        if locale == "ko":
            notes.append("서로 다른 전통 보조 주제의 동시 존재를 설명하는 프로젝트 규칙입니다. 두 표시가 서로 강화·취소한다고 판정하지 않습니다. 출현/개수로 큰 길흉이나 실제 사건을 판정하지 않으며 전문가/실증 검증은 미완료입니다.")
        else:
            notes.append("Project interpretation of coexisting supplementary themes, not amplification/cancellation, measured fortune magnitude, event prediction or expert approval.")
        # Introduce a detected feature and its bounded meaning before offering
        # its follow-up. Never publish an optional feature from static copy alone.
        introductions = [item[locale] for item in rule.get("introductions", [])
                         if item["question_id"] in question_ids and eligible.get(item["fact_id"])]
        paragraphs = rule[locale]["body"].split("\n\n")
        body = "\n\n".join(paragraphs[:1] + introductions + paragraphs[1:])
        result.themes.append(DistinctiveTheme(id=rule_id, category=rule["category"], title=rule[locale]["title"],
            body=body, memo_body="\n\n".join(notes), fact_ids=list(dict.fromkeys(refs)),
            rule_id=rule_id, question_ids=question_ids, eligible_matches=eligible))
    result.facts = list({f["id"]: f for f in result.facts}.values())


def build_distinctive_reading(*, base, locale):
    result = DistinctiveReading(status="blocked_calculation", versions=_versions())
    if not base.manse.meta.hour_pillar_enabled or set(base.manse.meta.visible_pillar_keys) != set(KEYS):
        result.blocked_reasons = ["incomplete_birth_time_or_pillars"]
        return result
    primary = {k: getattr(base.manse.pillars, k).gan_zhi for k in KEYS}
    try:
        _validate_chart(primary)
        if base.manse.meta.day_master != primary["day"][0]:
            raise ValueError("inconsistent_day_master")
        for k in KEYS:
            p = getattr(base.manse.pillars, k)
            if not p.enabled or p.gan_zhi != p.stem + p.branch:
                raise ValueError("inconsistent_chart")
            if {_stem(s) for s in p.hidden_stems} != {_stem(s) for s in HIDDEN_STEMS_BY_BRANCH[p.branch]}:
                raise ValueError("inconsistent_hidden_stems")
    except (ValueError, KeyError):
        result.blocked_reasons = ["inconsistent_chart_facts"]
        return result
    critical = [f for f in base.result.uncertainty_summary if f.severity == "critical"]
    alternate = _known_midnight_alternate(base, primary) if critical else None
    if critical and alternate is None:
        result.blocked_reasons = [f.code for f in critical]
        return result
    result.facts = [{"id": "distinctive.chart", "value": model_to_dict(base.manse.pillars, exclude_none=True), "source_path": "manse.pillars"}]
    _select(base, locale, result)
    result.status = "available" if result.themes else "no_matching_rules"
    if alternate:
        chart, candidate, source_path, rule = alternate
        other = deepcopy(base)
        other.manse.meta.day_master = chart["day"][0]
        for k in KEYS:
            original = getattr(base.manse.pillars, k)
            # Rebuild only fields used by these rules. Never retain the primary
            # day-stem-dependent relations, elements or fortunes on an alternate.
            p = MansePillar(key=k, label=original.label, enabled=True, gan_zhi=chart[k], stem=chart[k][0], branch=chart[k][1],
                hidden_stems=HIDDEN_STEMS_BY_BRANCH[chart[k][1]],
                xun_kong=LunarUtil.XUN_KONG[LunarUtil.JIA_ZI.index(chart[k]) // 10])
            setattr(other.manse.pillars, k, p)
        other.manse.special_stars = build_special_stars(pillars={k: getattr(other.manse.pillars, k) for k in KEYS}, visible_pillar_keys=KEYS)
        alternate_pillars = {k: model_to_dict(getattr(other.manse.pillars, k), include={
            "key", "label", "enabled", "gan_zhi", "stem", "branch", "hidden_stems", "xun_kong"}) for k in KEYS}
        alternate_reading = DistinctiveReading(status="available", versions=_versions(), facts=[
            {"id": "distinctive.chart", "value": alternate_pillars, "source_path": "manse.pillars"}])
        _select(other, locale, alternate_reading)
        result.comparisons = [{"chart": chart, "rule": rule, "source_path": source_path,
            "derived_fields_scope": "Only reconstructed chart characters, hidden stems, void and special stars; no alternate ten-god/element/fortune claim.",
            "derived_source": {"manse": {"pillars": alternate_pillars,
                "special_stars": [model_to_dict(s, exclude_none=True) for s in other.manse.special_stars]}},
            "fact_source_scope": "comparison.derived_source",
            "themes": [model_to_dict(t) for t in alternate_reading.themes], "facts": alternate_reading.facts,
            "retained_theme_ids": sorted({t.id for t in result.themes} & {t.id for t in alternate_reading.themes}),
            "removed_theme_ids": sorted({t.id for t in result.themes} - {t.id for t in alternate_reading.themes})}]
        result.assumption = ("밤 11시부터 다음 날로 보는 현재 명식을 가정한 풀이야. 날짜 기준이 달라지면 아래 특징도 달라질 수 있어." if locale == "ko" else
                             "These themes assume the displayed chart. A different day-change convention can change them.")
        # The assumption must reflect the actual selected policy, not a fixed birthday.
        if primary == chart:
            raise ValueError("alternate must differ")
        primary_policy = base.result.calculation_basis.primary_midnight_rule
        if primary_policy == "sect2_00_changes_day" and locale == "ko":
            result.assumption = "밤 12시에 날짜를 바꾸는 현재 명식을 가정한 풀이야. 날짜 기준이 달라지면 아래 특징도 달라질 수 있어."
        elif primary_policy != "sect1_23_changes_day":
            result.assumption = ("화면에 표시한 명식을 가정한 풀이야. 날짜 기준이 달라지면 아래 특징도 달라질 수 있어." if locale == "ko" else result.assumption)
        result.status = "conditional" if result.themes else "no_matching_rules"
    return result


def distinctive_questions(reading, locale):
    ids = list(dict.fromkeys(q for t in reading.themes for q in t.question_ids))
    # Two questions per category at most, selected from actually supported themes.
    return [{"id": q, "category": catalog()["questions"][q]["category"],
             "title": catalog()["questions"][q][locale]["title"],
             "description": catalog()["questions"][q][locale]["description"]} for q in ids]


def answer_distinctive_question(reading, question_id, locale):
    themes = [t for t in reading.themes if question_id in t.question_ids]
    if not themes:
        raise ValueError("feature question has no eligible theme")
    data = catalog()["questions"][question_id][locale]
    ids = list(dict.fromkeys(f for t in themes for f in t.fact_ids))
    facts = [f for f in reading.facts if f["id"] in ids]
    # A chosen chart and the validated alternative are essential assumption facts.
    memo = "\n\n".join(t.memo_body for t in themes)
    if reading.comparisons:
        memo += "\n\n" + comparison_memo(reading, locale, theme_ids={t.id for t in themes})
    return data, facts, memo


def comparison_memo(reading, locale, theme_ids=None):
    lines = []
    titles = {r["id"]: r[locale]["title"] for r in catalog()["rules"]}
    def labels(ids):
        return ", ".join(titles[i] for i in ids if theme_ids is None or i in theme_ids) or ("없음" if locale == "ko" else "None")
    for c in reading.comparisons:
        lines.append(("다른 날짜 기준의 명식: " if locale == "ko" else "Alternate chart: ") + " · ".join(c["chart"][k] for k in KEYS))
        lines.append(("위 조합 풀이 중 다른 기준에서도 성립하는 것: " if locale == "ko" else "Selected combined readings retained under this convention: ") + labels(c["retained_theme_ids"]))
        lines.append(("위 조합 풀이 중 다른 기준에서는 성립하지 않는 것: " if locale == "ko" else "Selected combined readings no longer eligible: ") + labels(c["removed_theme_ids"]))
        lines.append("선택한 조합 풀이끼리의 비교입니다. 개별 보조 표시가 모두 없어졌거나 부담이 해소됐다는 뜻은 아닙니다." if locale == "ko" else
                     "This compares selected combined readings only. Individual symbols can remain; no burden has been calculated to disappear.")
        if any("features.taegeuk" in t.question_ids and (theme_ids is None or t.id in theme_ids) for t in reading.themes):
            tae = next((s for s in c["derived_source"]["manse"]["special_stars"] if s["key"] == "taegeuk-gwiin" and s["active"]), None)
            if tae:
                positions = sorted({m["pillar_key"] + "=" + m["gan_zhi"] for m in tae["matches"]})
                lines.append(("다른 기준에도 태극귀인 표시는 남습니다: " if locale == "ko" else "Taiji Noble remains in the alternate chart: ") + ", ".join(positions))
        for t in c["themes"]:
            if theme_ids is None or t["id"] in theme_ids:
                lines.append(t["title"] + "\n" + t["body"] + "\n" + t["memo_body"])
    return "\n\n".join(lines)
