"""Supply already selected server conclusions to the initial-reading writer.

This is an expression contract, not another calculation or judgment engine.
Legacy preview/detail generation and critical holds keep their own contracts.
"""
import re

from app.domain.saju.natal_structure import build_natal_structure, catalog as natal_catalog
from app.domain.saju.distinctive_reading import build_distinctive_reading, catalog as theme_catalog
from app.domain.saju.pydantic_compat import model_to_dict
from app.domain.saju.reading_detail import build_reading_details, VERSIONS as DETAIL_VERSIONS


WRITING_VERSION = "published-reading-writing-2026-10-24.2"
MIN_MAIN_CHARS = 4412
SECTION_KEYS = ("core_analysis", "love", "wealth", "career", "luck_flow")


def visible_main_chars(body, locale="ko"):
    from app.domain.saju.reading_publication import model_main_parts
    main = re.split(r"(?m)^### (?:풀이 포인트|전문가 노트|Interpretation points|Expert note)\s*$", body, maxsplit=1)[0]
    main = re.sub(r"(?m)^#{1,6} .*$", "", main)
    main = "\n\n".join(model_main_parts(main, locale)[0])
    return len(re.sub(r"[\s*#`]", "", main))


def build_publication_writing(*, base, payload):
    if any(flag.severity == "critical" for flag in base.result.uncertainty_summary):
        return None
    locale = payload.profile.locale
    natal = build_natal_structure(base=base, locale=locale)
    if natal.status != "available":
        return None
    distinctive = build_distinctive_reading(base=base, locale=locale)
    chapters = {key: {"basis": [], "fact_ids": [], "scope": "bounded_supplied_judgments"}
                for key in SECTION_KEYS}

    def add(key, text, fact_ids, rule_ids):
        if text:
            chapters[key]["basis"].append({"text": text, "fact_ids": fact_ids, "rule_ids": rule_ids})
            chapters[key]["fact_ids"] = list(dict.fromkeys(chapters[key]["fact_ids"] + fact_ids))

    for conclusion in natal.conclusions:
        add("core_analysis", conclusion.text, conclusion.fact_ids, conclusion.rule_ids)
    for theme in distinctive.themes:
        if theme.category == "love":
            add("love", theme.body, theme.fact_ids, [theme.rule_id])
        elif theme.category == "core" and theme.question_ids:
            rule = next(r for r in theme_catalog()["rules"] if r["id"] == theme.rule_id)
            add("core_analysis", rule.get("reading_context", {}).get(locale), theme.fact_ids, [theme.rule_id])

    for key in ("love", "career", "luck_flow"):
        # A selected relationship theme replaces the unrelated legacy inference.
        if key == "love" and chapters[key]["basis"]:
            continue
        plan_key = "work_money" if key == "career" else key
        structure = payload.reading_plan.sections.get(plan_key) if payload.reading_plan else None
        if structure is None:
            continue
        for block in structure.blocks:
            if block.role in {"answer", "tradeoff"}:
                add(key, block.text, block.fact_ids, [structure.rule_id])
        if key == "career":
            add(key, natal_catalog()["work_explanation"].get(structure.rule_id, {}).get(locale),
                [f.id for f in structure.facts], [structure.rule_id])

    gods = {o["god"] for o in natal.profile["wealth_occurrences"]}
    meaning = ("both" if gods == {"정재", "편재"} else "direct" if "정재" in gods else
               "indirect" if "편재" in gods else "absent")
    add("wealth", natal_catalog()["wealth_explanation"][meaning][locale],
        [f["id"] for f in natal.facts], ["wealth_layer"])
    chapters["wealth"]["scope"] = "calculated_money_symbols_and_meaning_no_wealth_verdict"
    if payload.reading_information:
        for item in payload.reading_information.items:
            if item.id in {"cycle.current", "cycle.next", "cycle.comparison"}:
                add("luck_flow", item.body, item.fact_ids, ["supplied_cycle_theme_comparison"])

    details = build_reading_details(natal=natal, distinctive=distinctive, information=payload.reading_information, locale=locale)
    category_keys = {"core": "core_analysis", "love": "love", "wealth": "wealth", "career": "career", "luck_flow": "luck_flow"}
    for block in details:
        add(category_keys[block.category], block.text, block.fact_ids, block.rule_ids)

    if any(not chapter["basis"] or not chapter["fact_ids"] for chapter in chapters.values()):
        return None

    return {
        "version": WRITING_VERSION,
        "minimum_visible_main_chars": MIN_MAIN_CHARS,
        "length_metric": "main_only_no_whitespace_markdown_headings_memos_or_notices",
        "critical_hold": False,
        "whole_chart_synthesis_supported": False,
        "event_timing_supported": False,
        "expert_review": "not_completed",
        "chapters": chapters,
        "facts": natal.facts + distinctive.facts + ([model_to_dict(f) for f in payload.reading_information.facts] if payload.reading_information else []),
        "source_versions": {"natal": model_to_dict(natal.versions),
                            "distinctive": model_to_dict(distinctive.versions), "detail": DETAIL_VERSIONS},
    }
