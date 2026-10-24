"""Present existing judgments and source-linked chart information by category.

Main prose, found terms and technical memos are assembled on the server.
Existing interpretation/provider validation remains the owner's job. Critical
calculations retain the hold while supplying provisional positions/glossary.
"""

from datetime import datetime, timezone
import re
from typing import Callable, Optional

from app.domain.saju.pydantic_compat import model_to_dict
from app.domain.saju.question_reading import assemble_basic_reading, _wealth
from app.domain.saju.question_schemas import CategoryReading, CategoryReadingSection, SajuCategoryResponse
from app.domain.saju.reading_information import build_reading_information
from app.domain.saju.services.build_chart_characteristics import build_chart_characteristics
from app.domain.saju.reading_publication import publish_chapter, PUBLICATION_VERSION
from app.domain.saju.distinctive_reading import build_distinctive_reading
from app.domain.saju.natal_structure import build_natal_structure, catalog as natal_catalog


CATEGORIES = (
    ("core", "core_analysis", "내 사주의 특징", "Your chart's main features"),
    ("love", "love", "연애·결혼운", "Love and marriage"),
    ("wealth", "wealth", "금전운", "Money"),
    ("career", "career", "직장·직업운", "Work and career"),
    ("luck_flow", "luck_flow", "지금부터 달라질 운", "How your current flow changes"),
)
TECHNICAL_HEADINGS = {"풀이 포인트", "전문가 노트", "분석 노트", "풀이 메모", "reading points", "interpretation points", "expert note", "expert notes", "analysis note", "reading memo"}
OPENING_HEADINGS = {"핵심 결론", "Core conclusion"}


def _wealth_facts_body(base, locale, natal):
    """Reuse the question's factual extraction; do not derive money judgments."""
    facts, details = [], []
    answer, memo, _ = _wealth(base, locale, facts, details)
    # The information block already supplies locations and glossary. Retain
    # the count summary without duplicating positions or the shared notice.
    main = answer
    if natal.status == "available":
        gods = {o["god"] for o in natal.profile["wealth_occurrences"]}
        meaning_key = ("both" if gods == {"정재", "편재"} else "direct" if "정재" in gods else
                       "indirect" if "편재" in gods else "absent")
        main = natal_catalog()["wealth_explanation"][meaning_key][locale]
    # Exact counts/positions still belong to evidence. The main answers what
    # the matched classification means, without turning it into a wealth verdict.
    return main, "\n\n".join([answer] + [f"### {part.title}\n{part.text}" for part in details] + [memo])


def _calculation_notices(base, basic, locale, critical):
    if not critical:
        return basic.basic_reading.notices
    if not base.manse.meta.hour_pillar_enabled:
        return ["태어난 시간을 몰라 태어난 날의 글자도 확정하지 못했어. 사주팔자는 생년월일 기준의 임시 계산값이고, 다섯 분야의 해석은 보류했어. 시주와 대운도 제외했어." if locale == "ko" else
                "Birth time is unknown, so the day pillar is also unconfirmed. The displayed chart is provisional; all five category interpretations are withheld. Hour pillar and luck cycles are excluded."]
    return ["네 출생시간은 날짜를 바꾸는 기준에 따라 태어난 날의 글자가 달라질 수 있어. 아래는 선택한 명식의 잠정 계산 정보와 용어 설명이야. 이 차이 때문에 다섯 분야의 해석은 보류했어." if locale == "ko" else
            "The day pillar can differ between day-change conventions at this birth time. Below are provisional calculated positions and term definitions under the selected chart; all five category interpretations remain withheld."]


def split_reading_body(body: str):
    """Keep prose order and Markdown lists; move only named technical sections."""
    main, memo = [], []
    destination = main
    for line in body.splitlines():
        heading = re.match(r"^\s*#{1,6}\s+(.+?)\s*$", line)
        if heading:
            title = heading.group(1)
            technical = title.casefold() in TECHNICAL_HEADINGS
            destination = memo if technical else main
            if title in OPENING_HEADINGS or technical:
                continue
        destination.append(line)
    return "\n".join(main).strip(), "\n".join(memo).strip()


def _writing_context(report):
    diagnostics = report.diagnostics if report else None
    return {
        "generation_metadata_version": "provider-generation-v1",
        "requested_writing_provider": diagnostics.configured_provider if diagnostics else None,
        "writing_model": report.model if report else None,
        "writing_status": ("not_called" if report is None else
                           "model_generated" if report.provider in {"openai", "codex"} else "fallback"),
        "writing_fallback_reason": diagnostics.fallback_reason if diagnostics else None,
    }


def create_category_reading(*, payload, trace_id: str, service_name: str, calculate: Callable,
                            as_of: Optional[datetime] = None, on_progress=None) -> SajuCategoryResponse:
    current = as_of or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("category reading as_of must have a timezone")
    base = calculate(payload=payload, trace_id=trace_id, service_name=service_name, debug_requested=False,
                     report_mode="initial_reading", as_of=current, on_progress=on_progress)
    basic = assemble_basic_reading(base=base, locale=payload.locale, as_of=current)
    information = build_reading_information(base=base, locale=payload.locale, gender=payload.gender, as_of=current)
    characteristics = build_chart_characteristics(base=base, locale=payload.locale)
    distinctive = build_distinctive_reading(base=base, locale=payload.locale)
    natal = build_natal_structure(base=base, locale=payload.locale)
    # Factual calculation questions remain available through /saju/basic.
    # The initial reading offers deeper questions only for eligible themes.
    basic.question_flow.questions = [q for q in basic.question_flow.questions if q.id.startswith("features.")]
    has_dohwa = any(item.id in {"star.hamji", "star.wangji", "star.mokyok"} for item in information.items)
    if not has_dohwa:
        basic.question_flow.questions = [q for q in basic.question_flow.questions if q.id != "stars.dohwa"]
    report = base.result.interpretation
    from app.domain.saju.publication_writing import WRITING_VERSION
    model_publication = bool(report is not None and report.provider in {"openai", "codex"}
                             and report.publication_writing_version == WRITING_VERSION)
    critical = any(flag.severity == "critical" for flag in base.result.uncertainty_summary)
    if report is None and not critical:
        raise ValueError("initial reading report is missing")
    sections = []
    for category, key, ko_title, en_title in CATEGORIES:
        status = "blocked_calculation" if critical else "existing_interpretation"
        if critical:
            body = ("지금 입력은 계산 기준에 따라 명식이 달라져서 이 분야의 해석을 보류했어. 위에 표시한 사주팔자와 아래 질문의 계산값은 확인할 수 있어." if payload.locale == "ko" else
                    "This input can produce a different chart under other calculation conventions, so this category's interpretation is withheld. You can still check the displayed chart and calculated facts in the questions below.")
            memo = ""
        elif category == "wealth" and not model_publication:
            # Legacy money prose expands counts into personal spending/income and
            # period conclusions without an active catalog rule. Do not promote it.
            status = "needs_rule_review"
            body, memo = _wealth_facts_body(base, payload.locale, natal)
        else:
            body, memo = split_reading_body(getattr(report, key).body)
            if category == "wealth":
                status = "needs_rule_review"
            # Keep the original report/provenance intact. The initial fallback
            # presentation omits canned scenes/tasks, which assume a life state
            # that the user has not supplied. No new reading judgment is added.
            structure = report.reading_sections.get(key)
            if report.provider == "fallback" and structure is not None:
                paragraphs = []
                for block in structure.blocks:
                    if block.role not in {"answer", "tradeoff"}:
                        continue
                    paragraphs.append(block.text)
                    if category == "career" and block.role == "answer":
                        explanation = natal_catalog()["work_explanation"].get(structure.rule_id, {}).get(payload.locale)
                        if explanation:
                            paragraphs.append(explanation)
                body = "\n\n".join(paragraphs)
        category_information = [item for item in information.items if item.category == category]
        if category == "love":
            category_information.sort(key=lambda item: item.kind != "traditional_term_definition")
        information_memo = "\n\n".join(f"### {item.title}\n{item.memo_body}" for item in category_information)
        memo = "\n\n".join(part for part in (memo, information_memo) if part)
        section = CategoryReadingSection(id=category, title=ko_title if payload.locale == "ko" else en_title,
                                              body=body, memo_body=memo,
                                              status=status, information=category_information,
                                              visible=bool(not critical or category_information or any(q.category == category for q in basic.question_flow.questions)))
        comparison_memo = ""
        if category == "core" and characteristics.comparisons:
            comparison_memo = "\n\n".join("### " + comparison.label + "\n" +
                " · ".join(comparison.chart[k] for k in ("year", "month", "day", "time"))
                for comparison in characteristics.comparisons)
        section.publication = publish_chapter(section=section, report=report, locale=payload.locale,
                                              calculation_memo=comparison_memo, distinctive=distinctive, natal=natal)
        if model_publication or (category == "core" and natal.status in {"available", "conditional"}):
            # The compatibility body must agree with the actual published main.
            section.body = "\n\n".join(("### " + b.title + "\n\n" if b.title else "") + b.text
                                        for b in section.publication.blocks)
            section.memo_body = section.publication.memo_body
        if critical and distinctive.status == "conditional":
            section.visible = any(t.category == category for t in distinctive.themes)
        if category == "core" and natal.status in {"available", "conditional"}:
            section.visible = True
        sections.append(section)
    return SajuCategoryResponse(**model_to_dict(basic), category_reading=CategoryReading(
        sections=sections, reading_information=information, characteristics=characteristics, distinctive_reading=distinctive,
        natal_structure=natal,
        provider=report.provider if report else "deterministic", source_context={
            **_writing_context(report),
            "interpretation_rules_changed": False, "critical_hold": critical,
            "expert_review": "not_completed", "event_timing_supported": False,
            "report_prompt_version": report.prompt_version if report else None,
            "report_schema_version": report.schema_version if report else None,
            "wealth_interpretation_withheld": True,
            "information_scope": information.scope,
            "information_is_provisional": information.interpretation_withheld,
            "calculation_provider": "deterministic_manse_engine",
            "writing_provider": report.provider if report else "not_called_critical_hold",
            "published_model_contract": report.publication_writing_version if report else None,
            "fallback_visible_roles": ["answer", "tradeoff"],
            "characteristics_scope": characteristics.scope,
            "characteristics_status": characteristics.status,
            "characteristics_rules_changed": True,
            "publication_version": PUBLICATION_VERSION,
            "publication_is_not_new_judgment": True,
            "natal_structure_rules_changed": True,
            "natal_structure_scope": natal.scope,
            "natal_structure_status": natal.status,
            "natal_conclusion_selection_version": natal.versions.selection,
            "whole_chart_synthesis_supported": natal.whole_chart_synthesis_supported,
            "final_strength_supported": False,
            "useful_element_supported": False,
            "distinctive_scope": distinctive.scope,
            "distinctive_status": distinctive.status,
            "distinctive_rules_changed": True,
            "legacy_report_hold_preserved": critical,
        }, calculation_notices=([natal.assumption or distinctive.assumption,
                                 "날짜 기준에 따라 명식이 달라져 종합 풀이는 보류했어. 아래는 선택한 명식의 구조와 확인된 특징을 조건부로 읽은 내용이야." if payload.locale == "ko" else
                                 "The different day-change conventions keep the full reading on hold. Only the selected chart's structure and confirmed themes below are read conditionally."] if natal.status == "conditional" or distinctive.status == "conditional" else
                               _calculation_notices(base, basic, payload.locale, critical)),
        notices=(["명식의 구조를 읽은 참고 풀이야. 평생의 길흉이나 만남·취업 시기를 확정한 결과는 아니야." if payload.locale == "ko" else
                  "A reference reading of natal structure, not a lifetime verdict or event forecast."] if natal.blocks else
                 ["확인된 전통 보조 표시를 함께 읽은 참고 풀이야. 사주 전체의 큰 길흉이나 사건 시기를 판정한 결과는 아니야." if payload.locale == "ko" else
                  "A reference reading of coexisting traditional supplementary themes, not a whole-chart verdict or event forecast."] if distinctive.themes else
                 ["선택한 기준의 잠정 정보야. 만남·취업·승진 날짜나 수입을 예측한 결과는 아니야." if payload.locale == "ko" else
                  "This is provisional information under the selected convention, without predictions of events or income."] if critical else
                 ["현재 해석 기준을 바탕으로 한 참고 풀이야. 실제 사건이나 수입을 보장하지 않아." if payload.locale == "ko" else
                  "A reference reading using the current interpretation policies, without guarantees of events or income."])))
