"""LLM provider boundary and fallback interpretation generation."""

from __future__ import annotations

import json
import re
import time
from copy import deepcopy
from json import JSONDecodeError
from typing import Any, Dict, List, Sequence, Tuple

from pydantic import ValidationError

from app.config import PLACEHOLDER_OPENAI_API_KEY, settings
from app.diagnostics import log_stage
from app.domain.saju.interpretation import (
    InterpretationAttemptDiagnostic,
    InterpretationDiagnostics,
    InterpretationLLMOutput,
    InterpretationNarrativeSection,
    InterpretationReport,
    InterpretationSummaryBlock,
)
from app.domain.saju.llm_payload import InterpretationLuckCycle, InterpretationPayload
from app.domain.saju.localization import contains_hangul, contains_hanja

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - import guard for local test envs
    OpenAI = None


PROMPT_VERSION = "saju-report-v7"
MIN_SUMMARY_LENGTH = 90
MIN_SECTION_LENGTH = 260
OUTPUT_EXCERPT_LIMIT = 280
ERROR_MESSAGE_LIMIT = 280
SCHEMA_NOISE_KEYS = {
    "default",
    "examples",
    "minLength",
    "maxLength",
    "pattern",
    "format",
    "minimum",
    "maximum",
    "multipleOf",
    "minItems",
    "maxItems",
}
BANNED_PHRASES = [
    "무조건",
    "절대",
    "100%",
    "천생연분",
    "운명의 상대",
    "반드시 헤어진다",
    "대박 난다",
    "꽃길만 걷는다",
]
ELEMENT_LABELS = {
    "ko": {"wood": "목", "fire": "화", "earth": "토", "metal": "금", "water": "수"},
    "en": {
        "wood": "Wood",
        "fire": "Fire",
        "earth": "Earth",
        "metal": "Metal",
        "water": "Water",
    },
}

DEVELOPER_PROMPT = """
You are a modern Korean saju interpretation writer.

Rules:
- The payload already contains computed manse and saju facts. Never recalculate them.
- Use only the provided payload. Do not invent pillars, gods, timing, marriage outcomes, reunion, cheating, or destiny.
- Follow profile.locale strictly.
- If locale is ko, write in Hangul only. Do not output Hanja.
- If locale is en, write in English only. Do not output Korean or Hanja.
- Keep the tone professional, readable, and grounded.
- Every major section must be long-form prose with markdown subheadings and bullet points.
- Keep the established long-form reading style instead of turning the output into score commentary.
- Core analysis must include standout traits, comparison, strengths, cautions, and direction.
- Love must include relationship style, marriage traits, good match, difficult match, advice, and one short current-period subsection.
- Career must include work style, suitable environment, risks, strategy, and one short current-period subsection.
- Wealth must include flow type, relative tendency, cautions, money management direction, and one short current-period subsection.
- Luck flow must focus on current and next cycle only.
- Do not use literal labels such as evidence or explanation.
- Do not expose numeric scores, score labels, or point-based phrasing in user-facing text.
- Avoid exaggerated certainty and banned phrases.
- Return valid JSON that matches the schema.
""".strip()

REPAIR_PROMPT = """
You repair JSON output for a modern Korean saju interpretation service.

Rules:
- Use the provided payload as the only source of truth.
- Repair the draft JSON so it exactly matches the schema.
- Keep the existing long-form style when possible.
- Do not invent new facts.
- Follow the locale rules strictly.
- Return valid JSON only.
""".strip()


def _locale(payload: InterpretationPayload) -> str:
    return payload.profile.locale


def _local_elements(payload: InterpretationPayload, values: Sequence[str]) -> str:
    if not values:
        return "없음" if _locale(payload) == "ko" else "none"
    labels = ELEMENT_LABELS[_locale(payload)]
    return ", ".join(labels.get(value, value) for value in values)


def _metric_text(payload: InterpretationPayload, metrics: Sequence[Any]) -> str:
    if not metrics:
        return "없음" if _locale(payload) == "ko" else "none"
    return ", ".join(f"{metric.label} {metric.count}" for metric in metrics)


def _star_text(payload: InterpretationPayload, labels: Sequence[str]) -> str:
    if not labels:
        return "뚜렷한 보조 신호는 많지 않습니다." if _locale(payload) == "ko" else "There are no strong auxiliary star signals."
    joined = ", ".join(labels)
    if _locale(payload) == "ko":
        return f"현재 보이는 보조 신호는 {joined}입니다."
    return f"Visible auxiliary signals include {joined}."


def _cycle_label(payload: InterpretationPayload, cycle: InterpretationLuckCycle | None) -> str:
    if cycle is None:
        return "확인 대기" if _locale(payload) == "ko" else "Not available"
    if _locale(payload) == "ko":
        return f"{cycle.start_age}세부터 {cycle.end_age}세까지 {cycle.display_gan_zhi}"
    return f"{cycle.start_age}-{cycle.end_age} with {cycle.display_gan_zhi}"


def _dominant_domain(payload: InterpretationPayload) -> Tuple[str, int]:
    domain_scores = {
        "love": payload.signals.charm_score,
        "career": payload.signals.career_score,
        "wealth": payload.signals.wealth_score,
        "leadership": payload.signals.leadership_score,
    }
    return max(domain_scores.items(), key=lambda item: item[1])


def _summary_headline(payload: InterpretationPayload) -> str:
    dominant_key, _ = _dominant_domain(payload)
    if _locale(payload) == "ko":
        mapping = {
            "love": "관계의 결이 분명한 사주",
            "career": "일의 방향성이 또렷한 사주",
            "wealth": "돈의 흐름 관리가 중요한 사주",
            "leadership": "주도권의 쓰임이 중요한 사주",
        }
        return mapping[dominant_key]
    mapping = {
        "love": "A chart with a clear relationship pattern",
        "career": "A chart with a clear work direction",
        "wealth": "A chart where money management matters",
        "leadership": "A chart where initiative matters",
    }
    return mapping[dominant_key]


def _summary_overview(payload: InterpretationPayload) -> str:
    pillars = ", ".join(item.display_gan_zhi for item in payload.visible_pillars)
    dominant = _local_elements(payload, payload.signals.dominant_elements)
    missing = _local_elements(payload, payload.signals.missing_elements)
    active_cycle = _cycle_label(payload, payload.current_flow.active_luck_cycle)
    if _locale(payload) == "ko":
        text = (
            f"현재 보이는 사주 구조는 {pillars} 흐름으로 읽고 있습니다. "
            f"강하게 드러나는 기운은 {dominant}, 약하게 보이는 기운은 {missing}이며, "
            f"현재 기준 흐름은 {active_cycle}입니다. "
            f"이 흐름을 함께 반영해 연애운, 직장운, 금전운을 해석합니다."
        )
        if payload.profile.is_birth_time_estimated:
            text += " 출생시간이 미상이므로 시주 기반 해석은 보수적으로 제한했습니다."
        return text
    text = (
        f"The current reading uses the visible structure {pillars}. "
        f"The stronger elements are {dominant}, and the weaker side is {missing}. "
        f"The current timing is {_cycle_label(payload, payload.current_flow.active_luck_cycle)}, and that flow is reflected in love, career, and wealth."
    )
    if payload.profile.is_birth_time_estimated:
        text += " Because the birth time is estimated, hour-pillar-based interpretation stays conservative."
    return text


def _section(title: str, body: str, evidence_ids: Sequence[str]) -> InterpretationNarrativeSection:
    return InterpretationNarrativeSection(title=title, body=body.strip(), evidence_ids=list(evidence_ids)[:6] or ["elements"])


def build_fallback_interpretation_report(payload: InterpretationPayload) -> InterpretationReport:
    locale = _locale(payload)
    dominant = _local_elements(payload, payload.signals.dominant_elements)
    missing = _local_elements(payload, payload.signals.missing_elements)
    top_domain, _ = _dominant_domain(payload)
    top_domain_label = {
        "ko": {"love": "연애", "career": "직장", "wealth": "금전", "leadership": "주도성"},
        "en": {"love": "love", "career": "career", "wealth": "wealth", "leadership": "initiative"},
    }[locale][top_domain]
    active_cycle = _cycle_label(payload, payload.current_flow.active_luck_cycle)
    next_cycle = _cycle_label(payload, payload.current_flow.next_luck_cycle)
    love_star_text = _star_text(payload, payload.love_facts.active_star_labels)
    career_star_text = _star_text(payload, payload.career_facts.active_star_labels)
    wealth_star_text = _star_text(payload, payload.wealth_facts.active_star_labels)
    if locale == "ko":
        core_body = f"""
현재 사주는 {payload.day_master} 일간을 중심으로 {dominant} 기운이 먼저 드러나고, {missing} 기운은 보완 과제로 남기기 쉬운 구조입니다. 그래서 평균적인 사주보다 강점과 약점의 대비가 더 뚜렷하게 느껴질 가능성이 큽니다.

### 1. 내 사주의 핵심 구조
- 현재 보이는 기둥은 {", ".join(item.display_gan_zhi for item in payload.visible_pillars)}입니다.
- 강한 쪽이 빨리 힘을 쓰는 대신, 비어 있는 쪽을 늦게 보완하면 판단이 한 방향으로 기울 수 있습니다.
- 그래서 이 사주는 무난하게 퍼지는 타입보다, 맞는 환경에서 장점이 빠르게 살아나는 타입에 가깝습니다.

### 2. 평균과 다른 점
- 평균적인 사주보다 기운의 분포가 더 분명해서, 잘 맞는 자리와 맞지 않는 자리가 비교적 선명하게 갈릴 수 있습니다.
- 현재는 {top_domain_label} 쪽 이슈가 먼저 체감되기 쉬워 삶의 초점이 자연스럽게 그쪽으로 모이기 쉽습니다.
- 좋은 환경에서는 강점이 빠르게 붙고, 맞지 않는 환경에서는 단점도 함께 커질 가능성이 있습니다.

### 3. 장점과 주의점
- 장점은 스스로 잘 쓰는 기운이 분명하다는 점입니다. 그래서 방향만 맞으면 성과가 생각보다 빠르게 눈에 띌 수 있습니다.
- 주의점은 {missing} 보완이 늦어질수록 피로, 우유부단함, 과한 몰입 중 하나가 커질 수 있다는 점입니다.
- 따라서 내 사주를 좋게 쓰려면 강한 기운만 밀기보다, 약한 기운을 보완하는 생활 리듬과 사람 선택을 함께 가져가는 편이 좋습니다.
"""

        love_body = f"""
현재 연애운은 {payload.love_facts.partner_star_label}의 분포와 {payload.love_facts.spouse_house_label} 흐름을 함께 보고 읽고 있습니다. {love_star_text}

### 1. 연애 스타일
- 관계를 가볍게 넓히기보다, 마음이 움직일 만한 기준이 생겨야 깊게 들어가는 편일 가능성이 큽니다.
- {payload.love_facts.spouse_house_ten_god or "배우자궁 신호"}이 보이는 만큼, 감정만이 아니라 관계의 안정감과 역할 균형도 함께 따질 가능성이 있습니다.
- 쉽게 열리기보다 선택적으로 가까워지는 스타일로 읽는 편이 더 자연스럽습니다.

### 2. 결혼운
- 결혼운은 속도보다 안정감을 더 중시할수록 좋아지는 구조에 가깝습니다.
- 잘 맞는 배우자는 감정 기복을 자극하기보다 생활 리듬과 책임감을 함께 맞춰 줄 수 있는 사람입니다.
- 잘 맞지 않는 사람은 관계의 속도만 빠르고 기준이 자주 바뀌는 사람, 혹은 감정 소모를 계속 만드는 사람일 가능성이 큽니다.

### 3. 현재 기준으로 보면
- 현재 흐름은 {active_cycle}입니다. 지금은 관계를 급하게 결론내리기보다, 오래 갈 수 있는 방식인지 확인하는 태도가 더 중요합니다.
- 다음 흐름은 {next_cycle}입니다. 그래서 지금의 선택 기준이 다음 시기의 안정감으로 이어질 가능성이 큽니다.
- 조언으로는 매력만 확인하기보다 생활 감각, 책임감, 대화 리듬을 같이 보는 편이 좋습니다.
"""

        career_body = f"""
현재 직장운은 {payload.career_facts.month_pillar_label} {payload.career_facts.month_pillar_gan_zhi}, 월간 십성, 그리고 직업 관련 보조 신호를 함께 보고 읽고 있습니다. 핵심 직업 신호는 {_metric_text(payload, payload.career_facts.key_ten_gods)}이고, {career_star_text}

### 1. 일하는 방식의 특징
- 일의 흐름이 분명하고 역할이 보일수록 실력이 살아나는 편일 가능성이 큽니다.
- 반대로 우선순위가 자주 흔들리거나 기준이 모호한 환경에서는 성과보다 피로가 먼저 올라올 수 있습니다.
- 그래서 단순히 직업명보다, 어떤 방식으로 일하느냐가 더 중요한 사주로 읽는 편이 맞습니다.

### 2. 잘 맞는 환경
- 역할이 분명하고, 쌓아 온 기준을 꾸준히 써먹을 수 있는 조직이나 팀이 잘 맞을 가능성이 큽니다.
- 동시에 완전히 막힌 구조보다는, 스스로 판단하고 조정할 여지가 있는 자리가 더 낫습니다.
- 즉 안정감과 자율성의 균형이 맞는 환경이 핵심입니다.

### 3. 현재 기준으로 보면
- 현재 흐름은 {active_cycle}이고, 지금은 실력을 넓게 흩뿌리기보다 핵심 분야를 선명하게 만드는 편이 유리합니다.
- 다음 흐름은 {next_cycle}이어서, 지금 잡은 전문성의 방향이 이후 자리 잡는 방식에 영향을 줄 가능성이 큽니다.
- 조언으로는 잘하는 일을 늘리는 것과 동시에, 피로를 키우는 구조를 빨리 알아채고 정리하는 기준을 만드는 편이 좋습니다.
"""

        wealth_body = f"""
현재 금전운은 재성, 식상, 비겁의 흐름과 부족한 오행을 함께 보고 읽고 있습니다. 핵심 재물 신호는 {_metric_text(payload, payload.wealth_facts.key_ten_gods)}입니다. 약한 오행은 {_local_elements(payload, payload.wealth_facts.missing_elements)}이고, {wealth_star_text}

### 1. 돈의 흐름 특징
- 이 사주는 돈을 얼마나 크게 버느냐보다, 어떤 기준으로 모으고 지키느냐가 더 중요하게 작동할 가능성이 큽니다.
- 재물 흐름이 안정적이라도 관리 기준이 흐리면 체감 이익이 줄 수 있고, 반대로 기준이 분명하면 안정감을 만들 수 있습니다.
- 그래서 금전운은 공격성보다 관리력과 지속성이 더 중요합니다.

### 2. 좋은 점과 주의점
- 좋은 점은 흐름을 잘 읽으면 불필요한 손실을 줄이고, 필요한 곳에 자원을 모으는 힘이 생긴다는 점입니다.
- 주의점은 약한 기운이 보완되지 않으면 소비 판단이 흔들리거나, 사람 문제와 돈 문제가 섞일 수 있다는 점입니다.
- 특히 급하게 키우는 수익보다 오래 유지되는 구조를 먼저 만드는 쪽이 더 유리합니다.

### 3. 현재 기준으로 보면
- 현재 흐름은 {active_cycle}입니다. 지금은 규모를 키우는 것보다 새는 지점을 줄이고 기준을 세우는 시기로 읽는 편이 좋습니다.
- 다음 흐름은 {next_cycle}이므로, 지금 만든 습관이 이후의 안정감이나 확장성으로 이어질 가능성이 큽니다.
- 조언으로는 고정 지출 관리, 충동 소비 점검, 장기 기준 세우기를 먼저 가져가는 편이 좋습니다.
"""

        luck_flow_body = f"""
현재와 다음 대운만 중심으로 보면, 지금은 {active_cycle} 흐름 위에서 전체 운세를 읽고 있고 다음은 {next_cycle}으로 넘어갈 가능성이 큽니다.

### 1. 현재 흐름
- 현재 시기에는 이미 가진 강점을 정리하고, 약한 부분을 어떻게 보완할지 기준을 세우는 일이 중요합니다.
- 연애에서는 관계의 속도보다 안정감을, 직장에서는 역할의 선명함을, 금전에서는 관리 기준을 먼저 보는 편이 좋습니다.
- 즉 빠르게 밀어붙이기보다 구조를 정리하는 태도가 성과를 남기기 쉽습니다.

### 2. 다음 흐름
- 다음 시기에는 지금 정리한 기준이 실제 결과로 이어질 가능성이 더 커집니다.
- 그래서 현재 시기의 선택이 다음 흐름의 안정감, 성취감, 관계의 질을 결정하는 바탕이 될 수 있습니다.
- 미리 방향을 단순하게 정리해 둘수록 다음 흐름의 장점을 더 잘 받기 쉽습니다.
"""
    else:
        core_body = f"""
This chart is read around the {payload.day_master} day master, with {dominant} showing first and {missing} left as the main area that needs support. That makes the contrast between strengths and weak points feel clearer than in a flatter chart.

### 1. Core structure
- The visible pillars are {", ".join(item.display_gan_zhi for item in payload.visible_pillars)}.
- The strong side tends to show results quickly, but the weaker side can create imbalance if it is ignored for too long.
- That makes this chart less flat and more environment-sensitive than average.

### 2. What stands out
- The spread of strengths and gaps is clearer than usual, so the difference between a good fit and a poor fit can show up early.
- The current phase naturally puts more weight on {top_domain_label}, so life focus can gather there more easily.
- In the right environment, the strong side can rise quickly. In the wrong environment, the weak side can also become more visible.

### 3. Strengths and cautions
- The main strength is clarity. Once direction matches the chart, progress can become visible faster than expected.
- The main caution is that the weaker side, especially {missing}, can tilt judgment or drain energy if it stays unsupported.
- The practical direction is not only pushing what is strong, but also building routines and choices that support what is weak.
"""

        love_body = f"""
Current love reading is built from the {payload.love_facts.partner_star_label}, the {payload.love_facts.spouse_house_label}, and the active relationship signals. {love_star_text}

### 1. Relationship style
- This pattern often prefers selective depth over quick emotional expansion.
- The spouse-house signal, {payload.love_facts.spouse_house_ten_god or "relationship signal"}, suggests that stability and role balance matter as much as attraction.
- The chart does not read as emotionally closed, but it is more selective than casual.

### 2. Marriage traits
- Marriage tends to look better when pace is controlled and stability is tested over time.
- A better match is someone who supports rhythm, responsibility, and calm communication.
- A harder match is someone who changes the tone of the relationship too quickly or keeps turning emotion into exhaustion.

### 3. In the current phase
- The current timing is {active_cycle}. This is a better period for checking durability than rushing a conclusion.
- The next timing is {next_cycle}, so current standards can shape the quality of later stability.
- The practical advice is to judge not only attraction, but also daily rhythm, accountability, and how conflict is handled.
"""

        career_body = f"""
Current career reading uses the month pillar, the month-stem signal, and the work-related supporting signals together. The main work metrics are {_metric_text(payload, payload.career_facts.key_ten_gods)}. {career_star_text}

### 1. Work style
- This chart tends to perform better when role and direction are clear.
- In unstable structures where priorities keep moving, fatigue can rise before visible results do.
- That means work environment matters as much as job title.

### 2. Suitable environment
- Roles with clear ownership and room for steady skill-building are usually a better fit.
- At the same time, a fully rigid structure may feel limiting, so some room for judgment and adjustment is helpful.
- The strongest fit is often a balance between structure and autonomy.

### 3. In the current phase
- The current timing is {active_cycle}, which favors sharpening a core specialty over scattering effort.
- The next timing is {next_cycle}, so the direction set now can influence how stable the next stage feels.
- The practical advice is to protect focus, reduce structural fatigue, and build an environment where your strongest skills are used repeatedly.
"""

        wealth_body = f"""
Current wealth reading uses the money-related ten-god flow and the weaker elements together. The main money signals are {_metric_text(payload, payload.wealth_facts.key_ten_gods)}, and the weaker elements are {_local_elements(payload, payload.wealth_facts.missing_elements)}. {wealth_star_text}

### 1. Money flow
- This chart is often less about dramatic gains and more about how well money is managed, protected, and directed.
- Even with decent earning flow, unclear standards can reduce the sense of stability.
- When rules are clear, the chart can feel steadier in practice.

### 2. Strengths and cautions
- The strength is the ability to improve outcomes through discipline and selection.
- The caution is that weak spots can turn into uneven spending, leakage, or mixing people problems with money decisions.
- The safer direction is to build durable structure before chasing scale.

### 3. In the current phase
- The current timing is {active_cycle}. This is a better period for tightening money standards than stretching risk.
- The next timing is {next_cycle}, so habits built now can strongly shape later stability.
- The practical advice is to review fixed expenses, limit impulse spending, and define long-term rules first.
"""

        luck_flow_body = f"""
The chart is currently read on top of {active_cycle}, and the next visible shift is {next_cycle}.

### 1. Current flow
- The current phase favors organizing strengths and setting rules for weak points.
- In love, steady selection matters. In career, clear role structure matters. In wealth, management rules matter.
- The common theme is structure before speed.

### 2. Next flow
- The next phase can turn today's standards into visible outcomes.
- That means the choices made now can shape later stability, performance, and relationship quality.
- The clearer the direction becomes now, the easier it is to use the next flow well.
"""

    report = InterpretationReport(
        provider="fallback",
        model="fallback",
        prompt_version=PROMPT_VERSION,
        summary=InterpretationSummaryBlock(
            headline=_summary_headline(payload),
            overview=_summary_overview(payload),
            confidence="low" if payload.profile.is_birth_time_estimated else "medium",
            evidence_ids=["elements", "luck_cycles"],
        ),
        core_analysis=_section("내 사주의 특징" if locale == "ko" else "Core traits", core_body, ["elements", "ten_gods"]),
        love=_section("연애운과 결혼운" if locale == "ko" else "Love and marriage", love_body, ["ten_gods", "luck_cycles"] + [star.evidence_id for star in payload.special_stars[:2]]),
        career=_section("직장운" if locale == "ko" else "Career", career_body, ["ten_gods", "luck_cycles"]),
        wealth=_section("금전운" if locale == "ko" else "Wealth", wealth_body, ["elements", "luck_cycles"]),
        luck_flow=_section("현재와 다음 흐름" if locale == "ko" else "Current and next flow", luck_flow_body, ["luck_cycles"]),
        warnings=[],
    )
    return report


def _clean_excerpt(text: str, *, limit: int = OUTPUT_EXCERPT_LIMIT) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    return compact[:limit]


def _clean_error_message(error: Exception | str) -> str:
    compact = re.sub(r"\s+", " ", str(error)).strip()
    return compact[:ERROR_MESSAGE_LIMIT]


def _summarize_validation_error(error: ValidationError) -> List[str]:
    issues: List[str] = []
    for item in error.errors()[:6]:
        location = ".".join(str(part) for part in item.get("loc", [])) or "root"
        issues.append(f"{location}:{item.get('type', 'validation_error')}")
    return issues or [_clean_error_message(error)]


def _make_diagnostics(
    *,
    final_provider: str,
    payload_json: str,
    duration_ms: int = 0,
    attempts: List[InterpretationAttemptDiagnostic] | None = None,
    final_response_id: str | None = None,
    fallback_reason: str | None = None,
    validation_issues: List[str] | None = None,
) -> InterpretationDiagnostics:
    return InterpretationDiagnostics(
        configured_provider=settings.llm_provider,
        final_provider=final_provider,
        model=settings.openai_model if settings.llm_provider == "openai" else None,
        prompt_version=PROMPT_VERSION,
        payload_chars=len(payload_json),
        duration_ms=duration_ms,
        final_response_id=final_response_id,
        fallback_reason=fallback_reason,
        validation_issues=validation_issues or [],
        attempts=attempts or [],
    )


def _attach_diagnostics(
    report: InterpretationReport,
    diagnostics: InterpretationDiagnostics,
    *,
    warnings: List[str] | None = None,
    provider: str | None = None,
) -> InterpretationReport:
    updated_warnings = list(dict.fromkeys((warnings if warnings is not None else report.warnings)))
    return report.model_copy(
        update={
            "provider": provider or report.provider,
            "warnings": updated_warnings,
            "diagnostics": diagnostics,
        }
    )


def _build_openai_report(parsed: InterpretationLLMOutput) -> InterpretationReport:
    return InterpretationReport(
        provider="openai",
        model=settings.openai_model,
        prompt_version=PROMPT_VERSION,
        summary=parsed.summary,
        core_analysis=parsed.core_analysis,
        love=parsed.love,
        career=parsed.career,
        wealth=parsed.wealth,
        luck_flow=parsed.luck_flow,
        warnings=[],
    )


def _parse_interpretation_output(output_text: str) -> InterpretationLLMOutput:
    parsed_json = json.loads(output_text)
    normalized = _normalize_llm_output(parsed_json)
    return InterpretationLLMOutput.model_validate(normalized)


def _call_openai_repair_interpretation(
    *,
    client: OpenAI,
    payload_json: str,
    broken_output_text: str,
    attempt_index: int,
    token_budget: int,
) -> Tuple[InterpretationReport | None, InterpretationAttemptDiagnostic, str | None]:
    response = None
    output_text = ""
    try:
        response = client.responses.create(
            model=settings.openai_model,
            reasoning={"effort": settings.llm_reasoning_effort},
            store=settings.llm_store,
            max_output_tokens=token_budget,
            input=[
                {"role": "developer", "content": REPAIR_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "payload": json.loads(payload_json),
                            "broken_output": broken_output_text,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            text={
                "format": _make_openai_json_schema_strict(
                    "saju_interpretation_repair",
                    InterpretationLLMOutput.model_json_schema(),
                )
            },
        )
        response_id = getattr(response, "id", "unknown")
        output_text = getattr(response, "output_text", "") or ""
        parsed = _parse_interpretation_output(output_text)
        return (
            _build_openai_report(parsed),
            InterpretationAttemptDiagnostic(
                attempt_index=attempt_index,
                mode="repair",
                token_budget=token_budget,
                status="success",
                response_id=response_id,
                output_chars=len(output_text),
                output_excerpt=_clean_excerpt(output_text),
            ),
            response_id,
        )
    except JSONDecodeError as exc:
        return (
            None,
            InterpretationAttemptDiagnostic(
                attempt_index=attempt_index,
                mode="repair",
                token_budget=token_budget,
                status="json_invalid",
                response_id=getattr(response, "id", None) if response is not None else None,
                output_chars=len(output_text),
                output_excerpt=_clean_excerpt(output_text) if output_text else None,
                error_type=type(exc).__name__,
                error_message=_clean_error_message(exc),
                issues=["json_decode_error"],
            ),
            getattr(response, "id", None) if response is not None else None,
        )
    except ValidationError as exc:
        return (
            None,
            InterpretationAttemptDiagnostic(
                attempt_index=attempt_index,
                mode="repair",
                token_budget=token_budget,
                status="validation_error",
                response_id=getattr(response, "id", None) if response is not None else None,
                output_chars=len(output_text),
                output_excerpt=_clean_excerpt(output_text) if output_text else None,
                error_type=type(exc).__name__,
                error_message=_clean_error_message(exc),
                issues=_summarize_validation_error(exc),
            ),
            getattr(response, "id", None) if response is not None else None,
        )
    except Exception as exc:
        return (
            None,
            InterpretationAttemptDiagnostic(
                attempt_index=attempt_index,
                mode="repair",
                token_budget=token_budget,
                status="provider_error",
                response_id=getattr(response, "id", None) if response is not None else None,
                output_chars=len(output_text),
                output_excerpt=_clean_excerpt(output_text) if output_text else None,
                error_type=type(exc).__name__,
                error_message=_clean_error_message(exc),
                issues=["repair_request_failed"],
            ),
            getattr(response, "id", None) if response is not None else None,
        )


def _call_openai_structured_interpretation(
    payload: InterpretationPayload,
) -> Tuple[InterpretationReport | None, InterpretationDiagnostics]:
    payload_json = json.dumps(payload.model_dump(mode="json"), ensure_ascii=False)
    if OpenAI is None:
        return None, _make_diagnostics(
            final_provider="fallback",
            payload_json=payload_json,
            fallback_reason="openai_sdk_unavailable",
        )

    client = OpenAI(api_key=settings.openai_api_key)
    token_budgets = [
        max(settings.llm_max_output_tokens, 3200),
        max(settings.llm_max_output_tokens * 2, 5200),
    ]
    attempts: List[InterpretationAttemptDiagnostic] = []
    started = time.perf_counter()
    last_output_text = ""
    last_response_id: str | None = None
    fallback_reason = "openai_response_invalid"

    for attempt_index, token_budget in enumerate(token_budgets, start=1):
        output_text = ""
        response = None
        try:
            response = client.responses.create(
                model=settings.openai_model,
                reasoning={"effort": settings.llm_reasoning_effort},
                store=settings.llm_store,
                max_output_tokens=token_budget,
                input=[
                    {"role": "developer", "content": DEVELOPER_PROMPT},
                    {"role": "user", "content": payload_json},
                ],
                text={
                    "format": _make_openai_json_schema_strict(
                        "saju_interpretation",
                        InterpretationLLMOutput.model_json_schema(),
                    )
                },
            )
            last_response_id = getattr(response, "id", "unknown")
            output_text = getattr(response, "output_text", "") or ""
            parsed = _parse_interpretation_output(output_text)
            attempts.append(
                InterpretationAttemptDiagnostic(
                    attempt_index=attempt_index,
                    mode="generate",
                    token_budget=token_budget,
                    status="success",
                    response_id=last_response_id,
                    output_chars=len(output_text),
                    output_excerpt=_clean_excerpt(output_text),
                )
            )
            duration_ms = int((time.perf_counter() - started) * 1000)
            return _build_openai_report(parsed), _make_diagnostics(
                final_provider="openai",
                payload_json=payload_json,
                duration_ms=duration_ms,
                attempts=attempts,
                final_response_id=last_response_id,
            )
        except JSONDecodeError as exc:
            fallback_reason = "json_decode_error"
            attempts.append(
                InterpretationAttemptDiagnostic(
                    attempt_index=attempt_index,
                    mode="generate",
                    token_budget=token_budget,
                    status="json_invalid",
                    response_id=last_response_id,
                    output_chars=len(output_text),
                    output_excerpt=_clean_excerpt(output_text) if output_text else None,
                    error_type=type(exc).__name__,
                    error_message=_clean_error_message(exc),
                    issues=["json_decode_error"],
                )
            )
            last_output_text = output_text
        except ValidationError as exc:
            fallback_reason = "schema_validation_error"
            attempts.append(
                InterpretationAttemptDiagnostic(
                    attempt_index=attempt_index,
                    mode="generate",
                    token_budget=token_budget,
                    status="validation_error",
                    response_id=last_response_id,
                    output_chars=len(output_text),
                    output_excerpt=_clean_excerpt(output_text) if output_text else None,
                    error_type=type(exc).__name__,
                    error_message=_clean_error_message(exc),
                    issues=_summarize_validation_error(exc),
                )
            )
            last_output_text = output_text
        except Exception as exc:
            fallback_reason = "provider_request_failed"
            attempts.append(
                InterpretationAttemptDiagnostic(
                    attempt_index=attempt_index,
                    mode="generate",
                    token_budget=token_budget,
                    status="provider_error",
                    response_id=getattr(response, "id", None) if response is not None else None,
                    output_chars=len(output_text),
                    output_excerpt=_clean_excerpt(output_text) if output_text else None,
                    error_type=type(exc).__name__,
                    error_message=_clean_error_message(exc),
                    issues=["openai_request_failed"],
                )
            )
            duration_ms = int((time.perf_counter() - started) * 1000)
            return None, _make_diagnostics(
                final_provider="fallback",
                payload_json=payload_json,
                duration_ms=duration_ms,
                attempts=attempts,
                final_response_id=getattr(response, "id", None) if response is not None else None,
                fallback_reason=fallback_reason,
            )

    if last_output_text:
        repair_token_budget = max(settings.llm_max_output_tokens, 2400)
        repaired_report, repair_attempt, repair_response_id = _call_openai_repair_interpretation(
            client=client,
            payload_json=payload_json,
            broken_output_text=last_output_text,
            attempt_index=len(attempts) + 1,
            token_budget=repair_token_budget,
        )
        attempts.append(repair_attempt)
        if repaired_report is not None:
            duration_ms = int((time.perf_counter() - started) * 1000)
            return repaired_report, _make_diagnostics(
                final_provider="openai",
                payload_json=payload_json,
                duration_ms=duration_ms,
                attempts=attempts,
                final_response_id=repair_response_id,
            )
        fallback_reason = f"repair_{repair_attempt.status}"

    duration_ms = int((time.perf_counter() - started) * 1000)
    return None, _make_diagnostics(
        final_provider="fallback",
        payload_json=payload_json,
        duration_ms=duration_ms,
        attempts=attempts,
        final_response_id=last_response_id,
        fallback_reason=fallback_reason,
    )


def _normalize_llm_output(data: Dict[str, Any]) -> Dict[str, Any]:
    section_keys = ["summary", "core_analysis", "love", "career", "wealth", "luck_flow"]
    for key in section_keys:
        block = data.get(key)
        if isinstance(block, dict):
            evidence_ids = block.get("evidence_ids")
            if isinstance(evidence_ids, list):
                block["evidence_ids"] = evidence_ids[:6]
    return data


def _make_openai_json_schema_strict(name: str, schema: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = deepcopy(schema)

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            for key in list(node.keys()):
                if key in SCHEMA_NOISE_KEYS:
                    node.pop(key, None)
                    continue
                visit(node[key])
            if node.get("type") == "object":
                properties = node.get("properties", {})
                if properties:
                    node.setdefault("required", list(properties.keys()))
                node["additionalProperties"] = False
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(cleaned)
    return {"type": "json_schema", "name": name, "strict": True, "schema": cleaned}


def _collect_report_texts(report: InterpretationReport) -> List[str]:
    return [
        report.summary.headline,
        report.summary.overview,
        report.core_analysis.title,
        report.core_analysis.body,
        report.love.title,
        report.love.body,
        report.career.title,
        report.career.body,
        report.wealth.title,
        report.wealth.body,
        report.luck_flow.title,
        report.luck_flow.body,
    ]


def _contains_numeric_relative_claim(text: str) -> bool:
    patterns = [
        r"(상위|하위)\s*\d+\s*%",
        r"(top|bottom)\s*\d+\s*%",
        r"percentile",
    ]
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in patterns)


def _contains_exposed_score(text: str) -> bool:
    patterns = [
        r"\d+\s*점",
        r"score\s+of\s+\d+",
        r"balance score\s+is\s+\d+",
        r"\d+\/100",
    ]
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in patterns)


def _validate_section(key: str, section: InterpretationNarrativeSection) -> List[str]:
    issues: List[str] = []
    body = section.body.strip()
    if len(body) < MIN_SECTION_LENGTH:
        issues.append(f"{key}.body:too_short")
    if "### " not in body:
        issues.append(f"{key}.body:missing_subheadings")
    if "\n-" not in body and not body.startswith("-"):
        issues.append(f"{key}.body:missing_bullets")
    return issues


def _validate_language(report: InterpretationReport, payload: InterpretationPayload) -> List[str]:
    issues: List[str] = []
    locale = _locale(payload)
    for text in _collect_report_texts(report):
        if locale == "ko":
            if contains_hanja(text):
                issues.append("language:contains_hanja")
        else:
            if contains_hanja(text):
                issues.append("language:contains_hanja")
            if contains_hangul(text):
                issues.append("language:contains_hangul")
    return issues


def _validate_report(report: InterpretationReport, payload: InterpretationPayload) -> List[str]:
    issues: List[str] = []
    if len(report.summary.overview.strip()) < MIN_SUMMARY_LENGTH:
        issues.append("summary.overview:too_short")
    if payload.profile.is_birth_time_estimated and report.summary.confidence == "high":
        issues.append("summary.confidence:too_high_for_estimated_time")
    for key in ("core_analysis", "love", "career", "wealth", "luck_flow"):
        issues.extend(_validate_section(key, getattr(report, key)))
    for text in _collect_report_texts(report):
        if _contains_numeric_relative_claim(text):
            issues.append("relative_wording_without_percentile:numeric")
        if _contains_exposed_score(text):
            issues.append("score_exposed_in_user_text")
        for phrase in BANNED_PHRASES:
            if phrase in text:
                issues.append(f"banned_phrase:{phrase}")
    issues.extend(_validate_language(report, payload))
    return issues


def generate_interpretation_report(
    *,
    payload: InterpretationPayload,
    trace_id: str,
    service_name: str,
) -> InterpretationReport:
    started = time.perf_counter()
    payload_json = json.dumps(payload.model_dump(mode="json"), ensure_ascii=False)
    fallback_report = build_fallback_interpretation_report(payload)

    if settings.llm_provider != "openai":
        diagnostics = _make_diagnostics(
            final_provider="fallback",
            payload_json=payload_json,
            duration_ms=int((time.perf_counter() - started) * 1000),
            fallback_reason="provider_not_openai",
        )
        fallback_report = _attach_diagnostics(
            fallback_report,
            diagnostics,
            warnings=["llm_provider_disabled"],
            provider="fallback",
        )
        log_stage(
            service=service_name,
            trace_id=trace_id,
            stage="llm_formatting",
            event="fallback_used",
            duration_ms=int((time.perf_counter() - started) * 1000),
            meta={"reason": "provider_not_openai"},
        )
        return fallback_report

    if settings.openai_api_key in {"", PLACEHOLDER_OPENAI_API_KEY}:
        diagnostics = _make_diagnostics(
            final_provider="fallback",
            payload_json=payload_json,
            duration_ms=int((time.perf_counter() - started) * 1000),
            fallback_reason="missing_api_key",
        )
        fallback_report = _attach_diagnostics(
            fallback_report,
            diagnostics,
            warnings=["openai_api_key_missing"],
            provider="fallback",
        )
        log_stage(
            service=service_name,
            trace_id=trace_id,
            stage="llm_formatting",
            event="fallback_used",
            duration_ms=int((time.perf_counter() - started) * 1000),
            meta={"reason": "missing_api_key"},
        )
        return fallback_report

    report, diagnostics = _call_openai_structured_interpretation(payload)
    if report is None:
        warnings = [diagnostics.fallback_reason or "openai_response_invalid"]
        fallback_report = _attach_diagnostics(
            fallback_report,
            diagnostics,
            warnings=warnings,
            provider="fallback",
        )
        log_stage(
            service=service_name,
            trace_id=trace_id,
            stage="llm_formatting",
            event="fallback_used",
            duration_ms=int((time.perf_counter() - started) * 1000),
            error_code="interpretation_generation_failed",
            meta={
                "reason": diagnostics.fallback_reason or "openai_response_invalid",
                "attempts": [attempt.model_dump(mode="json") for attempt in diagnostics.attempts],
            },
        )
        return fallback_report

    try:
        issues = _validate_report(report, payload)
        if issues:
            diagnostics = diagnostics.model_copy(
                update={
                    "final_provider": "fallback",
                    "fallback_reason": "validation_failed",
                    "validation_issues": issues,
                }
            )
            fallback_report = _attach_diagnostics(
                fallback_report,
                diagnostics,
                warnings=issues,
                provider="fallback",
            )
            log_stage(
                service=service_name,
                trace_id=trace_id,
                stage="llm_formatting",
                event="fallback_used",
                duration_ms=int((time.perf_counter() - started) * 1000),
                meta={
                    "reason": "validation_failed",
                    "issues": issues,
                    "response_id": diagnostics.final_response_id,
                    "attempts": [attempt.model_dump(mode="json") for attempt in diagnostics.attempts],
                },
            )
            return fallback_report

        report = _attach_diagnostics(report, diagnostics, provider="openai")
        log_stage(
            service=service_name,
            trace_id=trace_id,
            stage="llm_formatting",
            event="formatted",
            duration_ms=int((time.perf_counter() - started) * 1000),
            meta={
                "provider": "openai",
                "response_id": diagnostics.final_response_id,
                "prompt_version": PROMPT_VERSION,
                "attempts": [attempt.model_dump(mode="json") for attempt in diagnostics.attempts],
            },
        )
        return report
    except Exception as exc:  # pragma: no cover - network/provider failure path
        diagnostics = diagnostics.model_copy(
            update={
                "final_provider": "fallback",
                "fallback_reason": "post_validation_exception",
                "validation_issues": [_clean_error_message(exc)],
            }
        )
        fallback_report = _attach_diagnostics(
            fallback_report,
            diagnostics,
            warnings=[_clean_error_message(exc)],
            provider="fallback",
        )
        log_stage(
            service=service_name,
            trace_id=trace_id,
            stage="llm_formatting",
            event="fallback_used",
            duration_ms=int((time.perf_counter() - started) * 1000),
            error_code="interpretation_generation_failed",
            meta={
                "reason": type(exc).__name__,
                "attempts": [attempt.model_dump(mode="json") for attempt in diagnostics.attempts],
            },
        )
        return fallback_report
