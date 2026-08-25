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
from app.domain.saju.prompts.interpretation_report import get_interpretation_report_prompt
from app.domain.saju.services.codex_provider import CodexProviderError, call_codex_json

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - import guard for local test envs
    OpenAI = None


def _model_dump_json(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return json.loads(model.json())


def _model_copy(model: Any, *, update: Dict[str, Any]) -> Any:
    if hasattr(model, "model_copy"):
        return model.model_copy(update=update)
    return model.copy(update=update, deep=True)


def _model_validate(model_class: Any, data: Dict[str, Any]) -> Any:
    if hasattr(model_class, "model_validate"):
        return model_class.model_validate(data)
    return model_class.parse_obj(data)


def _model_json_schema(model_class: Any) -> Dict[str, Any]:
    if hasattr(model_class, "model_json_schema"):
        return model_class.model_json_schema()
    return model_class.schema()


PROMPT_SPEC = get_interpretation_report_prompt()
MIN_SUMMARY_LENGTH = 220
MIN_SECTION_LENGTH = 850
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
GENERIC_HEADLINES = {
    "당신의 사주 풀이",
    "전체 운세 요약",
    "사주 결과",
    "핵심 요약",
    "운세 분석",
}
SECTION_TITLES = {
    "ko": {
        "core_analysis": "내 사주 특징",
        "love": "연애와 결혼 흐름",
        "career": "직장운",
        "wealth": "금전운",
        "luck_flow": "현재 운과 대운 흐름",
    },
    "en": {
        "core_analysis": "Core traits",
        "love": "Love and long-term relationships",
        "career": "Career",
        "wealth": "Wealth",
        "luck_flow": "Current and next luck flow",
    },
}
REQUIRED_SECTION_HEADINGS = {
    "ko": (
        "### 핵심 결론",
        "### 쉽게 풀어보면",
        "### 조언",
        "### 풀이 포인트",
        "### 전문가 노트",
    ),
    "en": (
        "### Core conclusion",
        "### Plain reading",
        "### Advice",
        "### Interpretation points",
        "### Expert note",
    ),
}
TECHNICAL_START_PATTERNS = {
    "ko": (
        "일간은",
        "오행은",
        "십성은",
        "사주상",
        "명식상",
        "원국은",
        "오행상",
        "십성상",
    ),
    "en": (
        "technically",
        "in the chart",
        "by the five elements",
        "by the ten gods",
    ),
}
INTERNAL_VALUE_PATTERNS = (
    r"\bbalance_score\b",
    r"\binternal_grade\b",
    r"\bevidence_id\b",
    r"\bscore\s*:",
    r"점수\s*:",
    r"등급\s*:",
    r"\b(?:100|90|80|70|60|50)\s*점\b",
    r"(?:100|90|80|70|60|50)\s*점",
)
PLACEHOLDER_USER_PHRASES = (
    "없음 쪽",
    "없음 기운",
    "확인 대기 구간",
)


def _locale(payload: InterpretationPayload) -> str:
    return payload.profile.locale


def _local_elements(payload: InterpretationPayload, values: Sequence[str]) -> str:
    if not values:
        return "없음" if _locale(payload) == "ko" else "none"
    labels = ELEMENT_LABELS[_locale(payload)]
    return ", ".join(labels.get(value, value) for value in values)


def _missing_element_label(payload: InterpretationPayload, values: Sequence[str]) -> str:
    if values:
        return _local_elements(payload, values)
    return "뚜렷한 공백 없음" if _locale(payload) == "ko" else "no clear gap"


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
        return "대운 정보 없음" if _locale(payload) == "ko" else "Luck-cycle information unavailable"
    return cycle.display_gan_zhi


def _cycle_period_context(
    payload: InterpretationPayload,
    cycle: InterpretationLuckCycle | None,
    *,
    position: str,
) -> str:
    if cycle is not None:
        if _locale(payload) == "ko":
            return f"{cycle.display_gan_zhi} 대운 구간"
        return f"the {cycle.display_gan_zhi} luck-cycle period"
    if _locale(payload) == "ko":
        return "첫 대운이 시작되기 전의 현재 구간" if position == "current" else "다음 대운이 확인되지 않은 구간"
    return "the period before the first luck cycle" if position == "current" else "a period without a confirmed next luck cycle"


def _summary_headline(payload: InterpretationPayload) -> str:
    if _locale(payload) == "ko":
        return "기준을 세우고 생활의 균형을 다듬어 가는 사람"
    return "A steady builder of clear standards"


def _summary_overview(payload: InterpretationPayload) -> str:
    dominant = _local_elements(payload, payload.signals.dominant_elements)
    missing_values = payload.signals.missing_elements
    missing = _missing_element_label(payload, missing_values)
    active_period = _cycle_period_context(
        payload,
        payload.current_flow.active_luck_cycle,
        position="current",
    )
    if _locale(payload) == "ko":
        repeating_pattern = (
            f"반복 패턴은 잘 맞는 환경에서는 몰입이 살아나지만, {missing} 쪽 보완이 늦어지면 판단이 한쪽으로 기울 수 있다는 점입니다. "
            if missing_values
            else "반복 패턴은 잘 맞는 환경에서는 몰입이 살아나지만, 환경과 생활 리듬이 흐려지면 판단이 한쪽으로 기울 수 있다는 점입니다. "
        )
        closing = (
            "이 사주는 강한 부분을 성과에 쓰고 약한 부분은 루틴과 환경으로 보완할 때 가장 안정적으로 쓰입니다."
            if missing_values
            else "이 사주는 강한 부분을 성과에 쓰고, 회복 루틴과 주변 환경을 함께 정리할 때 가장 안정적으로 쓰입니다."
        )
        text = (
            "이 사주는 기준을 세우고 오래 밀고 갈 때 힘이 살아나는 사람으로 읽습니다. "
            f"강점은 {dominant} 쪽처럼 빠르게 반응하고 자기 방식으로 정리하는 힘입니다. "
            f"{repeating_pattern}"
            f"현재 시기는 {active_period}을 기준으로 보며, 크게 벌리기보다 관계와 일과 돈의 기준을 정리하는 의미가 큽니다. "
            "주의할 점은 속도만 믿고 밀어붙이면 피로, 지출, 관계 부담이 함께 커질 수 있다는 것입니다. "
            f"{closing}"
        )
        if payload.profile.is_birth_time_estimated:
            text += " 출생시간이 미상이므로 시간에 민감한 해석은 방향성 중심으로만 참고하는 편이 안전합니다."
        return text
    repeating_pattern = (
        f"The repeating pattern is that the right environment brings focus, while the weaker side, {missing}, can tilt judgment when it is ignored. "
        if missing_values
        else "The repeating pattern is that the right environment brings focus, while unclear routines and context can tilt judgment when they are ignored. "
    )
    closing = (
        "The chart works best when strengths are used for results and weaker parts are supported through routine and environment."
        if missing_values
        else "The chart works best when strengths are used for results and recovery routines and environment are kept clear."
    )
    text = (
        "This chart reads as someone who works best when clear standards are built and sustained. "
        f"The core strength is the quick response and organizing power shown through {dominant}. "
        f"{repeating_pattern}"
        f"The current timing is {active_period}, which favors sorting standards before widening the field. "
        "The main caution is that speed alone can increase fatigue, spending leakage, or relationship burden. "
        f"{closing}"
    )
    if payload.profile.is_birth_time_estimated:
        text += " Because the birth time is estimated, hour-pillar-based interpretation stays conservative."
    return text


def _fallback_depth_block(
    payload: InterpretationPayload,
    section_key: str,
    *,
    dominant: str,
    missing: str,
    has_missing: bool,
    active_period: str,
    next_period: str,
    top_domain_label: str,
) -> str:
    locale = _locale(payload)
    if locale == "ko":
        missing_note = (
            f"{missing} 기운은 사주에서 보완 과제로 읽습니다. 이 부분은 타고난 결핍이라는 뜻이 아니라, 생활 습관과 사람 선택으로 의식적으로 채워야 안정감이 커지는 영역입니다."
            if has_missing
            else "특정 오행 하나를 결핍으로 단정하기보다, 생활 루틴과 주변 환경을 안정시키는 방식이 더 중요한 경우로 읽는 편이 안전합니다."
        )
        wealth_caution = (
            f"{missing} 기운이 약하게 보이는 만큼, 돈 문제에서는 감정에 따라 결정을 미루거나 갑자기 크게 움직이는 패턴을 조심하는 편이 좋습니다."
            if has_missing
            else "돈 문제에서는 감정에 따라 결정을 미루거나 갑자기 크게 움직이는 패턴을 조심하는 편이 좋습니다."
        )
        if section_key == "core_analysis":
            return f"""

### 4. 현실에서 드러나는 방식
- {dominant} 기운이 먼저 드러나는 사람은 판단과 반응이 빠르게 보일 수 있습니다. 다만 빠른 반응이 늘 장점으로만 쓰이는 것은 아니어서, 상황을 충분히 확인하기 전에 결론을 앞당기면 피로가 쌓일 수 있습니다.
- {missing_note}
- 특히 {top_domain_label} 쪽 이슈가 먼저 체감되기 쉬우므로, 중요한 선택을 할 때는 감정의 크기보다 반복해서 유지 가능한 방식인지를 같이 보는 편이 좋습니다.

### 5. 이 사주를 좋게 쓰는 방향
- 강한 부분은 성과를 빠르게 만들 때 쓰고, 약한 부분은 루틴과 환경으로 보완하는 식의 분업이 필요합니다.
- 잘 맞는 환경에서는 자신감이 빨리 올라오지만, 맞지 않는 환경에서는 같은 장점이 고집이나 과한 몰입처럼 보일 수 있습니다.
- 그래서 사주를 좋게 쓰는 핵심은 나를 바꾸는 것이 아니라, 힘이 잘 쓰이는 자리와 힘이 새는 자리를 구분하는 데 있습니다.
"""
        if section_key == "love":
            return f"""

### 4. 관계에서 반복되기 쉬운 장면
- 이 연애운은 단순히 사람이 들어오느냐보다, 들어온 관계를 어떤 기준으로 유지하느냐가 더 중요합니다. 처음에는 매력이나 호감이 분명해도, 시간이 지나면 생활 리듬과 책임감의 차이가 더 크게 느껴질 수 있습니다.
- 상대가 감정을 크게 표현하더라도 실제 행동이 일정하지 않으면 마음이 쉽게 피곤해질 수 있습니다. 반대로 표현이 화려하지 않아도 약속, 대화, 생활 감각이 안정적인 사람에게는 신뢰가 천천히 쌓이기 쉽습니다.
- 현재 흐름은 {active_period}이며, 관계를 급하게 확정하기보다 갈등이 생겼을 때 대화가 이어지는지 확인하는 과정이 더 중요합니다.

### 5. 관계 조언
- 호감이 생겼을 때 바로 결론을 내리기보다, 반복되는 행동을 몇 번 더 확인해 보세요.
- 대화가 잘 되는 사람인지, 생활 패턴이 지나치게 흔들리지 않는지, 돈과 시간 약속을 어떻게 다루는지 같이 보는 편이 좋습니다.
- 다음 흐름은 {next_period}으로 이어지므로 지금 세운 관계 기준이 더 중요해질 수 있습니다. 끌림과 안정감을 함께 보는 균형이 필요합니다.
"""
        if section_key == "career":
            return f"""

### 4. 성과가 나는 방식
- 이 직장운은 막연히 바쁜 환경보다 역할이 분명한 환경에서 더 잘 살아납니다. 해야 할 일, 책임 범위, 평가 기준이 정리되어 있을수록 실력이 누적되고 주변에서도 신뢰를 확인하기 쉽습니다.
- 반대로 기준이 자주 바뀌거나 말로만 급한 일이 많은 곳에서는 능력보다 소모가 먼저 커질 수 있습니다. 이런 경우에는 더 열심히 하는 것보다 업무 범위와 우선순위를 문서나 대화로 정리하는 편이 도움이 됩니다.
- 현재 흐름은 {active_period}이며, 넓게 벌리기보다 핵심 역량을 선명하게 만드는 쪽이 좋습니다. 다음 흐름은 {next_period}으로 이어지며, 지금 만든 전문성의 기준이 역할 변화나 책임 증가로 이어질 수 있습니다.

### 5. 직업 선택 기준
- 직업명보다 실제 업무 방식이 더 중요합니다.
- 반복해서 쌓이는 기술, 정리와 검토가 필요한 업무, 책임 범위가 분명한 자리가 잘 맞을 가능성이 있습니다.
- 피해야 할 것은 기준 없이 계속 불이 나는 환경입니다. 그런 곳에서는 장점이 드러나기 전에 피로가 먼저 커질 수 있습니다.
"""
        if section_key == "wealth":
            return f"""

### 4. 돈이 모이고 새는 지점
- 이 금전운은 한 번에 크게 키우는 흐름보다, 들어온 돈을 어떻게 남기고 배치하느냐가 중요합니다. 수입이 생겨도 기준이 흐리면 관계 비용, 충동 소비, 급한 선택으로 체감 안정감이 줄어들 수 있습니다.
- {wealth_caution} 숫자를 복잡하게 다루기보다 고정 지출, 예비비, 반복 소비를 먼저 나누는 단순한 기준이 더 잘 맞습니다.
- 현재 흐름은 {active_period}이며, 확장보다 정리가 먼저입니다. 다음 흐름은 {next_period}으로 이어지므로 더 안정적으로 쓰려면 지금 새는 곳을 줄이는 습관이 바탕이 됩니다.

### 5. 금전 조언
- 큰 계획을 세우기 전에 매달 반복되는 지출부터 확인하세요.
- 사람 때문에 쓰는 돈과 나를 위해 투자하는 돈을 구분해 두는 편이 좋습니다.
- 수익을 키우는 선택은 가능성을 보되, 유지 가능한 구조인지 먼저 확인하는 것이 중요합니다.
"""
        if section_key == "luck_flow":
            return f"""

### 흐름을 쓰는 법
- 대운은 사건을 하나씩 맞히는 도구라기보다, 어떤 태도가 더 잘 먹히는 시기인지 보는 기준에 가깝습니다. 현재는 {active_period}의 영향을 받는 시기라 속도를 내기보다 기준을 세우고, 다음에는 {next_period}으로 흐름이 이어지며 그 기준이 실제 선택과 책임으로 드러나는 흐름으로 읽습니다.
- 그래서 지금 해야 할 일은 운이 좋아질 때를 기다리는 것이 아니라, 좋아지는 흐름을 받을 수 있는 상태를 만들어 두는 것입니다. 관계에서는 오래 갈 기준을, 일에서는 반복해서 쓸 전문성을, 금전에서는 새지 않는 구조를 먼저 준비하는 편이 좋습니다.
- 좋고 나쁨은 고정된 결과가 아니라 관리 포인트입니다. 같은 흐름도 준비가 되어 있으면 기회처럼 느껴지고, 기준이 없으면 부담처럼 느껴질 수 있습니다.
"""
    missing_note = (
        f"The weaker side, {missing}, is not a fixed flaw. It is the part that needs routines, environment, and repeated choices to become more stable."
        if has_missing
        else "No single element is treated as a fixed gap here. Stable routines, environment, and repeated choices are the more useful support points."
    )
    wealth_caution = (
        f"Because {missing} needs more support, money decisions should be made with simple rules rather than mood."
        if has_missing
        else "Money decisions should be made with simple rules rather than mood."
    )
    if section_key == "core_analysis":
        return f"""

### 4. How this appears in real life
- When {dominant} shows first, the person can seem quick to respond and quick to recognize what works. That speed is useful, but it can also become tiring if conclusions are made before the situation is fully checked.
- {missing_note}
- Because {top_domain_label} is likely to be felt first, major decisions should be judged not only by intensity but also by whether the pattern can be sustained.

### 5. How to use the chart well
- Use the strong side for momentum and the weaker side as a design problem.
- A good environment can make the strengths visible quickly, while a poor environment can turn the same strengths into stubbornness or over-focus.
- The practical goal is not to change the person, but to separate places where energy works well from places where it leaks.
"""
    if section_key == "love":
        return f"""

### 4. Repeating relationship pattern
- This love reading is less about whether someone appears and more about how the relationship is maintained. Attraction can be clear at first, but daily rhythm and responsibility may become more important over time.
- A partner who is expressive but inconsistent can become tiring. A partner who is calmer but steady with promises, time, and communication may build trust more naturally.
- In the current timing, {active_period}, checking durability is more useful than rushing a label.

### 5. Relationship advice
- Watch repeated behavior before making a conclusion.
- Notice how the person handles conversation, daily rhythm, money, and time promises.
- As the chart moves toward {next_period}, the relationship standards built now can matter more, so attraction and stability should be read together.
"""
    if section_key == "career":
        return f"""

### 4. How results are built
- This career pattern works better where roles, ownership, and standards are clear. When responsibilities are defined, skill can accumulate and trust can become easier to see.
- In a place where priorities constantly move, effort may turn into fatigue before results become visible. In that case, clarifying scope and order can help more than simply working harder.
- In the current timing, {active_period}, sharpening the core specialty is more useful than spreading effort. In {next_period}, the standards built now can shape later role changes.

### 5. Work-fit criteria
- The actual work pattern matters more than the job title.
- Roles involving accumulated skill, review, organization, responsibility, or structured execution can be a better fit.
- The main environment to avoid is one where everything is urgent but nothing is defined.
"""
    if section_key == "wealth":
        return f"""

### 4. Where money gathers and leaks
- This wealth reading emphasizes keeping and directing money more than dramatic expansion. Even when income appears, unclear standards can reduce the felt stability through relationship costs, impulse spending, or rushed choices.
- {wealth_caution} Fixed expenses, reserve funds, and repeated spending are better starting points than complicated plans.
- In the current timing, {active_period}, organization comes before expansion. Habits built now can make {next_period} feel more stable.

### 5. Money advice
- Review recurring expenses before making larger plans.
- Separate money spent for people from money invested in yourself.
- When considering growth, first check whether the structure can be maintained.
"""
    return f"""

### How to use the flow
- Luck cycles are better used as timing context than as fixed event prediction. The current timing, {active_period}, favors setting standards, while {next_period} can make those standards more visible through choices and responsibility.
- The task now is not simply waiting for better timing. It is preparing the condition that can receive a better flow.
- Better and worse are management points. The same timing can feel like opportunity when standards exist and like pressure when they do not.
"""


def _luck_flow_transition_detail(
    payload: InterpretationPayload,
    active_cycle: str,
    next_cycle: str,
) -> str:
    facts = payload.luck_flow_facts
    favorable = facts.favorable_periods[0] if facts.favorable_periods else None
    current_analysis = next(
        (
            item
            for item in payload.luck_cycle_analysis
            if item.display_gan_zhi == facts.current_luck_cycle
            and item.period == facts.current_period
        ),
        None,
    )
    next_analysis = next(
        (
            item
            for item in payload.luck_cycle_analysis
            if item.display_gan_zhi == facts.next_luck_cycle
            and item.period == facts.next_period
        ),
        None,
    )
    if facts.current_luck_cycle or facts.next_luck_cycle:
        if _locale(payload) == "ko":
            current_label = facts.current_luck_cycle or active_cycle
            current_period = facts.current_period or "현재 대운의 시작 시점은 확인되지 않았습니다"
            next_label = facts.next_luck_cycle or next_cycle
            next_period = facts.next_period or "다음 대운의 시작 시점은 확인되지 않았습니다"
            favorable_text = (
                f"{favorable.period}의 {favorable.luck_cycle} 대운부터 "
                f"{', '.join(favorable.favorable_for[:3])} 쪽에 상대적으로 힘이 실립니다."
                if favorable
                else "뚜렷하게 유리하다고 표시된 대운이 없어서, 현재와 다음 대운의 차이만 보수적으로 봅니다."
            )
            current_good = ", ".join(current_analysis.good_for[:3]) if current_analysis else "기준 정리"
            current_watch = ", ".join(current_analysis.watch_out[:3]) if current_analysis else "무리한 확장"
            next_good = ", ".join(next_analysis.good_for[:3]) if next_analysis else "다음 기준 만들기"
            next_watch = ", ".join(next_analysis.watch_out[:3]) if next_analysis else "부담 증가"
            same_cycle_profile = bool(
                current_analysis
                and next_analysis
                and current_analysis.phase_label == next_analysis.phase_label
                and current_analysis.good_for[:3] == next_analysis.good_for[:3]
                and current_analysis.watch_out[:3] == next_analysis.watch_out[:3]
            )
            next_phase_label = facts.next_phase_label or "다음 단계 준비"
            if same_cycle_profile:
                next_good = "현재 정리한 기준을 이어서 적용"
                next_watch = "현재의 관리 포인트를 계속 점검"
                next_phase_label = "현재 흐름의 기준을 이어서 적용하는 단계"
            action_lines = "\n".join(f"- {item}" for item in facts.now_action_tags[:5])
            limitation = (
                "\n출생 시간이 미상이거나 추정이면 대운 전환 해석은 확정적으로 보지 않고 방향성만 참고해야 합니다."
                if payload.profile.is_birth_time_estimated
                else ""
            )
            return f"""

### 지금은 어떤 시기인가
현재 {current_label} 대운은 {current_period} 구간이며, 성격은 {facts.current_phase_label or "현재 흐름 점검"}에 가깝습니다.
지금은 큰 결론을 급하게 내기보다 {current_good} 쪽을 정리할수록 체감이 나아지기 쉽습니다.
반대로 {current_watch} 쪽은 부담으로 느껴질 수 있어 속도보다 기준을 먼저 잡는 편이 좋습니다.

### 좋아지는 시기는 언제인가
{favorable_text}
이 표현은 좋은 일이 정해져 있다는 뜻이 아니라, 해당 기간에 어떤 선택이 더 잘 받쳐질 수 있는지를 말합니다.

### 어떤 운이 좋아지는가
- 현재 대운에서 힘이 실리는 부분: {current_good}
- 현재 대운에서 주의할 부분: {current_watch}
- 다음 대운에서 좋아지기 쉬운 부분: {next_good}
- 다음 대운에서 주의할 부분: {next_watch}

### 다음 대운에서 무엇이 바뀌는가
다음 {next_label} 대운은 {next_period} 구간이며, 성격은 {next_phase_label} 쪽으로 읽습니다.
{facts.transition_summary}
현재가 정리와 조율의 성격이라면, 다음 대운은 그 기준이 생활, 일, 돈 관리 방식으로 고정되는 흐름에 더 가깝습니다.{limitation}

### 지금 해야 할 것
{action_lines}

### 풀이 포인트
[{current_label}] [{next_label}] [대운 변화] [분야별 영향]

### 전문가 노트
대운은 십 년 단위의 환경 변화를 보는 자료입니다. 여기서는 백엔드가 계산한 대운별 성격, 유리 분야, 주의 태그를 바탕으로 현재와 다음 구간만 비교했습니다.
"""

        current_label = facts.current_luck_cycle or active_cycle
        current_period = facts.current_period or "not available"
        next_label = facts.next_luck_cycle or next_cycle
        next_period = facts.next_period or "not available"
        favorable_text = (
            f"From {favorable.period}, the {favorable.luck_cycle} cycle is relatively more supportive for "
            f"{', '.join(favorable.favorable_for[:3])}."
            if favorable
            else "No cycle is explicitly marked as strongly favorable, so the reading stays focused on the current-to-next transition."
        )
        current_good = ", ".join(current_analysis.good_for[:3]) if current_analysis else "setting standards"
        current_watch = ", ".join(current_analysis.watch_out[:3]) if current_analysis else "over-expansion"
        next_good = ", ".join(next_analysis.good_for[:3]) if next_analysis else "preparing the next standard"
        next_watch = ", ".join(next_analysis.watch_out[:3]) if next_analysis else "greater pressure"
        action_lines = "\n".join(f"- {item}" for item in facts.now_action_tags[:5])
        limitation = (
            "\nIf the birth time is estimated or unknown, luck-cycle transition reading should stay directional rather than certain."
            if payload.profile.is_birth_time_estimated
            else ""
        )
        return f"""

### What kind of period this is
The current {current_label} cycle covers {current_period}, and its character is close to {facts.current_phase_label or "current-flow review"}.
This period tends to work better when the user focuses on {current_good} rather than forcing a quick conclusion.
The area needing more care is {current_watch}, so standards matter more than speed.

### When the more favorable period begins
{favorable_text}
This does not mean a fixed event will happen. It means that certain choices may be supported more easily in that period.

### Which area improves
- Current cycle support: {current_good}
- Current cycle caution: {current_watch}
- Next cycle support: {next_good}
- Next cycle caution: {next_watch}

### What changes in the next cycle
The next {next_label} cycle covers {next_period}, and its character moves toward {facts.next_phase_label or "next-stage preparation"}.
{facts.transition_summary}
If the current cycle is more about adjustment, the next cycle is more about turning those standards into life, work, and money-management structure.{limitation}

### What to do now
{action_lines}

### Interpretation points
[{current_label}] [{next_label}] [luck-cycle transition] [domain impact]

### Expert note
Luck cycles show broad ten-year environmental changes. This section compares only the current and next cycle using backend-calculated cycle traits, favorable domains, and caution tags.
"""

    if _locale(payload) == "ko":
        active_period = _cycle_period_context(
            payload,
            payload.current_flow.active_luck_cycle,
            position="current",
        )
        next_period = _cycle_period_context(
            payload,
            payload.current_flow.next_luck_cycle,
            position="next",
        )
        limitation = (
            "\n출생 시간이 미상이거나 추정이면 대운 전환 해석은 확정적으로 보지 않고 방향성만 참고해야 합니다."
            if payload.profile.is_birth_time_estimated
            else ""
        )
        return f"""

### 현재와 다음 대운의 차이
- 현재는 {active_period}의 영향을 받는 시기라 이미 가진 강점을 정리하고, 생활과 일과 돈의 기준을 세우는 쪽이 좋아지기 쉽습니다.
- 다만 기준이 흐려지면 속도보다 피로, 지출, 관계 부담이 먼저 커질 수 있어 주의가 필요합니다.
- 다음에는 {next_period}으로 흐름이 바뀌며 지금 만든 기준이 결과나 역할 변화로 드러나기 쉽습니다.
- 좋아지는 부분은 선택의 선명함, 일의 책임 범위, 관리 능력이고, 주의할 부분은 과한 확장, 관계 비용, 급한 결정입니다.{limitation}

### 풀이 포인트
[대운] [현재 흐름] [다음 흐름]

### 전문가 노트
현재와 다음 대운만 비교해 방향을 잡았습니다. 좋고 나쁨은 확정 사건이 아니라, 생활 선택에 따라 더 잘 쓰이거나 부담이 커질 수 있는 영역으로 읽어야 합니다.
"""

    limitation = (
        "\nIf the birth time is estimated or unknown, luck-cycle transition reading should stay directional rather than certain."
        if payload.profile.is_birth_time_estimated
        else ""
    )
    return f"""

### Difference between the current and next cycle
- In the current cycle, {active_period}, the easier gains tend to come from organizing strengths and setting standards for life, work, and money.
- The part that needs more care is losing those standards, because fatigue, spending leakage, or relationship burden can become more noticeable than speed.
- In the next cycle, {next_period}, the standards built now can show up more clearly as results, responsibility, or role changes.
- What may improve is clearer selection, work ownership, and management ability. What needs more care is over-expansion, relationship costs, and rushed decisions.{limitation}

### Interpretation points
[luck cycle] [current flow] [next flow]

### Expert note
This compares only the current and next luck cycle. Better or worse areas are not fixed outcomes; they are practical tendencies that can become helpful or burdensome depending on choices.
"""


def _section(title: str, body: str, evidence_ids: Sequence[str]) -> InterpretationNarrativeSection:
    return InterpretationNarrativeSection(title=title, body=body.strip(), evidence_ids=list(evidence_ids)[:6] or ["elements"])


def build_fallback_interpretation_report(payload: InterpretationPayload) -> InterpretationReport:
    locale = _locale(payload)
    dominant = _local_elements(payload, payload.signals.dominant_elements)
    missing_values = payload.signals.missing_elements
    has_missing = bool(missing_values)
    missing = _missing_element_label(payload, missing_values)
    wealth_missing_values = payload.wealth_facts.missing_elements
    wealth_missing = _missing_element_label(payload, wealth_missing_values)
    top_domain_label = {
        "ko": "일·관계·생활 리듬",
        "en": "work, relationships, and daily rhythm",
    }[locale]
    active_cycle = _cycle_label(payload, payload.current_flow.active_luck_cycle)
    next_cycle = _cycle_label(payload, payload.current_flow.next_luck_cycle)
    active_period = _cycle_period_context(
        payload,
        payload.current_flow.active_luck_cycle,
        position="current",
    )
    next_period = _cycle_period_context(
        payload,
        payload.current_flow.next_luck_cycle,
        position="next",
    )
    love_star_text = _star_text(payload, payload.love_facts.active_star_labels)
    career_star_text = _star_text(payload, payload.career_facts.active_star_labels)
    wealth_star_text = _star_text(payload, payload.wealth_facts.active_star_labels)
    titles = SECTION_TITLES[locale]
    if locale == "ko":
        core_support_line = (
            f"보완할 부분은 {missing} 쪽의 생활 리듬입니다."
            if has_missing
            else "보완할 부분은 생활 리듬과 주변 환경을 꾸준히 정리하는 일입니다."
        )
        core_body = f"""
### 핵심 결론
이 사람은 기준이 맞으면 오래 밀고 가고, 맞지 않으면 피로를 빨리 알아차리는 타입입니다. 강점은 {dominant} 쪽의 빠른 반응과 정리력이고, {core_support_line}

### 쉽게 풀어보면
평균적으로 무난하게 퍼지는 사주보다, 잘 맞는 자리와 맞지 않는 자리가 비교적 선명하게 갈릴 수 있습니다. 그래서 환경이 맞으면 집중력이 빨리 살아나고, 스스로 해야 할 일의 우선순위도 빠르게 잡힙니다.

다만 기준이 흐려진 상태에서 오래 버티면 장점이 고집이나 과한 몰입처럼 보일 수 있습니다. {top_domain_label} 쪽 이슈가 먼저 체감되기 쉬워 중요한 선택을 할 때도 그 주제가 중심으로 올라올 가능성이 큽니다.

이 사주를 좋게 쓰려면 강한 부분만 더 밀어붙이기보다, 약한 부분을 보완하는 루틴을 같이 만들어야 합니다. 사람, 일, 돈을 한꺼번에 판단하기보다 각각의 기준을 나누어 보면 흔들림이 줄어듭니다.

### 조언
- 잘 맞는 환경에서는 속도를 내되, 맞지 않는 환경에서는 먼저 기준을 정리하세요.
- 중요한 선택은 감정의 크기보다 반복해서 유지 가능한 방식인지 확인하세요.
- 강한 장점은 성과를 만들 때 쓰고, 약한 부분은 생활 습관으로 보완하세요.
- 사람 관계와 일의 기준을 분리하면 피로가 덜 쌓입니다.
- 너무 오래 참기보다 부담이 커지는 지점을 빨리 알아차리는 편이 좋습니다.

### 풀이 포인트
[{payload.day_master}] [{dominant}] [{missing}] [{top_domain_label}]

### 전문가 노트
일간, 오행 분포, 십성 신호를 새로 계산하지 않고 payload에 들어온 결과만 바탕으로 정리했습니다. 강한 요소는 장점의 방향으로, 약한 요소는 관리해야 할 반복 패턴으로 풀었습니다.
"""

        love_body = f"""
### 핵심 결론
관계에서는 빠른 확정보다 오래 유지될 수 있는 기준이 더 중요하게 보입니다. 끌림은 분명할 수 있지만, 실제로 마음이 깊어지는지는 생활 리듬과 책임감이 맞는지에 달려 있습니다.

### 쉽게 풀어보면
이 연애 흐름은 가볍게 넓어지는 관계보다, 신뢰가 쌓일 때 깊어지는 관계에 더 가깝습니다. 처음에는 호감이나 매력이 눈에 들어와도 시간이 지나면 대화 방식, 약속을 지키는 태도, 일상의 안정감이 더 중요해질 수 있습니다.

{love_star_text} 이런 보조 신호는 매력이나 사회적 주목을 뜻하는 참고 자료로만 보아야 합니다. 관계의 결과를 단정하기보다는, 어떤 사람과 있을 때 마음이 덜 소모되는지 확인하는 데 쓰는 편이 안전합니다.

현재는 {active_period}을 기준으로 관계의 속도를 밀기보다 지속 가능성을 확인하는 시기입니다. 다음 흐름은 {next_period}으로 이어지며, 지금 세운 관계 기준이 더 중요해질 수 있습니다.

### 조언
- 호감이 생겨도 반복되는 행동을 몇 번 더 확인하세요.
- 잘 맞는 사람은 감정 표현보다 생활 리듬과 책임감이 안정적인 사람입니다.
- 맞추기 어려운 관계는 속도는 빠른데 기준이 자주 바뀌는 패턴입니다.
- 장기 관계는 끌림과 안정감이 함께 있을 때 더 편하게 이어집니다.
- 갈등이 생겼을 때 대화가 이어지는지를 중요한 기준으로 보세요.

### 풀이 포인트
[{payload.love_facts.spouse_house_label}] [{payload.love_facts.partner_star_label}] [{payload.love_facts.spouse_house_ten_god or "관계 신호"}] [{active_cycle}]

### 전문가 노트
연애와 장기 관계는 배우자궁, 성별 기준 배우자 별, 현재 흐름, 보조 신살을 함께 보되 단정적으로 해석하지 않았습니다. 도화나 홍염 계열 신호는 관계 결과가 아니라 매력과 주목의 보조 지표로만 사용했습니다.
"""

        career_body = f"""
### 핵심 결론
일에서는 맡은 역할이 분명하고 기준이 정리될수록 실력이 살아나는 편입니다. 결과물을 쌓아 신뢰를 만드는 방식이 맞고, 이 구조가 금전 흐름의 안정감으로도 이어질 수 있습니다.

### 쉽게 풀어보면
이 직장운은 직업명을 하나로 정하는 것보다 어떤 방식으로 일할 때 덜 지치고 성과가 남는지를 보는 것이 중요합니다. 책임 범위, 우선순위, 평가 기준이 정리되어 있으면 집중력이 살아나고 주변에서도 신뢰를 확인하기 쉬워집니다.

반대로 해야 할 일은 많은데 기준이 자주 바뀌는 곳에서는 능력보다 피로가 먼저 커질 수 있습니다. 그래서 안정감만 있는 조직보다, 구조는 있되 스스로 판단하고 조정할 여지가 있는 환경이 더 잘 맞습니다.

현재는 {active_period}을 기준으로 실력을 넓게 흩뿌리기보다 핵심 분야를 선명하게 만드는 시기입니다. 다음 흐름은 {next_period}으로 이어지며, 지금 만든 전문성, 기록, 결과물이 수입 구조와 역할 안정성에 영향을 줄 수 있습니다.

### 조언
- 직업명보다 실제 업무 방식과 책임 범위를 먼저 보세요.
- 반복해서 쌓이는 기술, 정리와 검토, 운영, 문서화, 교육, 실행력이 필요한 역할이 잘 맞을 수 있습니다.
- 모든 일을 떠안기보다 성과로 남는 일과 피로만 남는 일을 구분하세요.
- 돈의 안정감을 키우려면 일의 결과물이 어떻게 보상과 연결되는지 확인하세요.
- 현재 시기에는 넓은 확장보다 핵심 역량을 선명하게 만드는 전략이 좋습니다.

### 풀이 포인트
[{payload.career_facts.month_pillar_label}] [{payload.career_facts.month_pillar_gan_zhi}] [{_metric_text(payload, payload.career_facts.key_ten_gods)}] [{active_cycle}]

### 전문가 노트
직장운은 월주, 월간 십성, 직업 관련 보조 신호, 현재 대운을 payload 기준으로만 해석했습니다. {career_star_text} 이런 신호는 직업 적성의 단정이 아니라 강점이 드러나는 방식의 보조 자료로 사용했습니다.
"""

        wealth_body = f"""
### 핵심 결론
돈은 한 번에 크게 키우는 방식보다 들어온 흐름을 남기고 지키는 기준이 중요합니다. 일에서 만든 결과물과 책임이 수입의 단서가 되고, 관리 기준이 흐리면 체감 안정감이 쉽게 줄 수 있습니다.

### 쉽게 풀어보면
이 금전운은 수입의 크기를 단정하기보다 돈이 어떤 경로로 들어오고 어디서 새는지를 보는 쪽이 더 현실적입니다. {_metric_text(payload, payload.wealth_facts.key_ten_gods)} 신호는 성과, 생산성, 역할, 관계 비용 같은 요소가 금전 판단과 연결될 수 있음을 보여줍니다.

돈이 모이는 조건은 단순합니다. 반복되는 지출을 먼저 파악하고, 사람 때문에 쓰는 돈과 나를 위해 쓰는 돈을 나누며, 일에서 만든 결과물이 보상으로 이어지는 구조를 확인해야 합니다.

현재는 {active_period}을 기준으로 규모를 키우기보다 새는 지점을 줄이고 기준을 세우는 시기입니다. 다음 흐름은 {next_period}으로 이어지며, 지금 만든 습관이 금전의 안정감이나 선택 폭에 영향을 줄 수 있습니다.

### 조언
- 고정 지출, 반복 소비, 관계 비용을 먼저 구분하세요.
- 일의 결과물이 수입으로 이어지는 경로를 확인하고 기록하세요.
- 급한 확장보다 유지 가능한 관리 구조를 먼저 만드세요.
- 투자, 주식, 코인처럼 특정 선택을 지시하기보다 스스로 지킬 수 있는 기준을 세우는 편이 안전합니다.
- 수입이 생겼을 때 바로 쓰기보다 남기는 비율과 목적을 먼저 정하세요.

### 풀이 포인트
[{_metric_text(payload, payload.wealth_facts.key_ten_gods)}] [{wealth_missing}] [{wealth_star_text}] [{active_cycle}]

### 전문가 노트
금전운은 재성, 식상, 비겁, 부족한 오행, 현재 대운을 payload 기준으로만 연결했습니다. 여기서는 수익 보장이나 특정 투자 지시를 하지 않고, 돈이 들어오고 새는 구조와 관리 방향만 문장화했습니다.
"""

        luck_flow_body = f"""
### 핵심 결론
지금은 흐름을 기다리는 때라기보다 다음 선택을 받을 수 있는 기준을 만드는 시기입니다. 현재는 {active_period}의 영향을 받는 시기라 정리와 조율이 중요하고, 다음에는 {next_period}으로 흐름이 이어지며 지금 만든 기준이 더 분명한 선택으로 이어질 수 있습니다.

### 쉽게 풀어보면
대운은 사건이 정해졌다는 뜻이 아니라 어떤 태도와 선택이 더 잘 작동하는지를 보는 시간표에 가깝습니다. 지금은 이미 가진 강점을 정리하고 약한 부분을 루틴으로 보완할수록 관계, 일, 돈의 판단이 덜 흔들립니다.

현재 대운에서 좋아지는 점은 기준을 세우고 역할을 정리할 때 체감 안정감이 커질 수 있다는 점입니다. 조심할 점은 속도만 보고 밀어붙이면 피로, 지출, 관계 부담이 함께 커질 수 있다는 것입니다.

다음 대운에서는 지금 정리한 기준이 생활 방식, 일의 책임, 돈 관리 방식으로 더 선명하게 드러날 수 있습니다. 그래서 지금 준비해야 할 것은 큰 예언을 기다리는 일이 아니라, 오래 유지할 기준을 작게라도 세우는 일입니다.

### 조언
- 현재 시기는 관계, 일, 돈의 기준을 다시 정리하는 데 쓰세요.
- 다음 흐름을 위해 지금 반복 가능한 습관과 업무 방식을 만들어 두세요.
- 좋은 시기를 기다리기보다 좋은 선택을 받을 수 있는 상태를 준비하세요.
- 변화가 생겨도 사건 확정처럼 받아들이지 말고 선택과 태도의 흐름으로 보세요.
- 대운 해석은 전체 표보다 현재와 다음 흐름의 차이를 중심으로 참고하세요.

### 풀이 포인트
[{active_cycle}] [{next_cycle}] [대운 변화] [분야별 영향]

### 전문가 노트
대운은 백엔드가 계산한 현재 대운, 다음 대운, 대운별 성격과 유리 분야를 바탕으로 문장화했습니다. 여기서는 사건 예언이 아니라 선택과 태도의 시간 흐름으로만 설명했습니다.
"""
        luck_flow_body += _luck_flow_transition_detail(payload, active_cycle, next_cycle)
        core_body += _fallback_depth_block(
            payload,
            "core_analysis",
            dominant=dominant,
            missing=missing,
            has_missing=has_missing,
            active_period=active_period,
            next_period=next_period,
            top_domain_label=top_domain_label,
        )
        love_body += _fallback_depth_block(
            payload,
            "love",
            dominant=dominant,
            missing=missing,
            has_missing=has_missing,
            active_period=active_period,
            next_period=next_period,
            top_domain_label=top_domain_label,
        )
        career_body += _fallback_depth_block(
            payload,
            "career",
            dominant=dominant,
            missing=missing,
            has_missing=has_missing,
            active_period=active_period,
            next_period=next_period,
            top_domain_label=top_domain_label,
        )
        wealth_body += _fallback_depth_block(
            payload,
            "wealth",
            dominant=dominant,
            missing=missing,
            has_missing=has_missing,
            active_period=active_period,
            next_period=next_period,
            top_domain_label=top_domain_label,
        )
        luck_flow_body += _fallback_depth_block(
            payload,
            "luck_flow",
            dominant=dominant,
            missing=missing,
            has_missing=has_missing,
            active_period=active_period,
            next_period=next_period,
            top_domain_label=top_domain_label,
        )
    else:
        core_support_line = (
            f"The {missing} side needs routine and context so judgment does not become one-sided."
            if has_missing
            else "Recovery routines and a clear environment matter more than treating any one element as a fixed gap."
        )
        wealth_signal_sentence = (
            f"The main money signals are {_metric_text(payload, payload.wealth_facts.key_ten_gods)}, with {wealth_missing} needing more support."
            if wealth_missing_values
            else f"The main money signals are {_metric_text(payload, payload.wealth_facts.key_ten_gods)}. No single element is treated as a clear gap in this reading."
        )
        core_body = f"""
### Core conclusion
This person works best when standards are clear and the environment supports sustained effort. The stronger side is {dominant}. {core_support_line}

### Plain reading
Rather than spreading evenly everywhere, this chart reads as someone whose fit with a place or relationship can become clear fairly quickly. When the setting is right, focus and response speed rise; when the setting is wrong, fatigue can also show up quickly.

The main difference from an average pattern is the stronger contrast between useful strengths and areas that need support. The current focus is likely to gather around {top_domain_label}, so major choices should be judged by whether the pattern can be sustained, not only by how intense it feels.

The best way to use this chart is to let strengths create results while weaker areas are supported by repeated habits. This keeps confidence from turning into over-focus and helps the person choose places where energy is used well.

### Advice
- Use speed and clarity where they create concrete results.
- Treat weaker areas as routine design rather than personal flaws.
- Separate relationship, work, and money standards before making big decisions.
- Notice early when the environment is turning strength into fatigue.
- Choose settings where effort can accumulate instead of resetting every day.

### Interpretation points
[{payload.day_master}] [{dominant}] [{missing}] [{top_domain_label}]

### Expert note
This fallback does not recalculate the chart. It only verbalizes the provided day master, element balance, ten-god signals, and domain emphasis from the interpretation payload.
"""

        love_body = f"""
### Core conclusion
In relationships, lasting standards matter more than a fast label. Attraction can be clear, but the relationship becomes easier when daily rhythm, responsibility, and communication stay steady.

### Plain reading
This pattern often moves toward selective depth rather than quick emotional expansion. A person may feel interesting at first, but trust is built by repeated behavior, promises kept, and a rhythm that does not drain the user.

{love_star_text} These supporting signals should be read as attraction or social attention indicators, not as fixed relationship outcomes. The current timing, {active_period}, is better for checking durability than rushing a conclusion, while {next_period} makes today's standards more important.

### Advice
- Watch repeated behavior before making a relationship decision.
- A better match is steady with time, responsibility, and conflict handling.
- A harder match is fast-changing, emotionally exhausting, or inconsistent.
- Long-term partnership works better when attraction and daily stability both exist.
- Use the current period to clarify standards rather than forcing a result.

### Interpretation points
[{payload.love_facts.spouse_house_label}] [{payload.love_facts.partner_star_label}] [{payload.love_facts.spouse_house_ten_god or "relationship signal"}] [{active_cycle}]

### Expert note
Love and long-term relationship tendencies are based on spouse-house, partner-star, current-flow, and special-star facts already provided in the payload. The fallback avoids fixed claims about marriage, breakup, reunion, or cheating.
"""

        career_body = f"""
### Core conclusion
Work goes better when role, standards, and ownership are clear. Accumulated output and responsibility can become the bridge between career stability and money flow.

### Plain reading
This career pattern is less about naming one job and more about the way work is structured. When priorities, scope, and evaluation standards are clear, skill can accumulate and trust becomes easier to build.

In environments where priorities constantly move, effort may become fatigue before results become visible. The current timing, {active_period}, favors sharpening a core specialty, while {next_period} can make today's standards more visible through role or responsibility.

### Advice
- Judge the work pattern before judging the job title.
- Look for roles involving organization, review, documentation, operations, responsibility, education, or execution when supported by the actual job context.
- Protect focus by clarifying scope and order.
- Connect work output to how compensation, trust, or responsibility is built.
- Build a repeatable specialty before widening the field.

### Interpretation points
[{payload.career_facts.month_pillar_label}] [{payload.career_facts.month_pillar_gan_zhi}] [{_metric_text(payload, payload.career_facts.key_ten_gods)}] [{active_cycle}]

### Expert note
Career reading uses the provided month-pillar context, career facts, ten-god metrics, current flow, and supporting star labels. {career_star_text} Supporting signals are treated as hints about work style, not as job guarantees.
"""

        wealth_body = f"""
### Core conclusion
Money is better read through how it enters, leaks, and remains rather than through a fixed promise of gain. Work output, responsibility, and repeated management rules are the practical anchors of this wealth pattern.

### Plain reading
{wealth_signal_sentence} This suggests that income stability is helped by concrete output, clear responsibilities, and habits that reduce leakage.

Money can leak through unclear standards, rushed choices, shared costs, or spending tied to relationships. In the current timing, {active_period}, tightening rules matters more than stretching risk, and habits built now can shape stability in {next_period}.

### Advice
- Review fixed expenses, repeat spending, and people-related costs first.
- Track how work results connect to income or responsibility.
- Build rules that can be followed repeatedly.
- Avoid turning this reading into stock, coin, or guaranteed-profit advice.
- Set a purpose for saved money before expanding financial commitments.

### Interpretation points
[{_metric_text(payload, payload.wealth_facts.key_ten_gods)}] [{wealth_missing}] [{wealth_star_text}] [{active_cycle}]

### Expert note
Wealth reading uses the provided wealth-star, output-star, peer-star, element-balance, missing-element, and current-flow facts. The fallback only describes structure and management direction, not investment instructions or profit guarantees.
"""

        luck_flow_body = f"""
### Core conclusion
The current phase is better used for setting standards than waiting for a fixed event. {active_period} favors organization and adjustment, while {next_period} can make today's standards show up more clearly in choices.

### Plain reading
Luck cycles are timing context, not event certainty. The current period works better when the user organizes strengths, supports weaker areas with routine, and separates relationship, work, and money standards.

The current cycle can feel better when roles, habits, and limits become clearer. The main caution is pushing too fast before the structure is ready, because that can increase fatigue or leakage.

The next cycle can make today's choices more visible through responsibility, stability, or work-and-money structure. What matters now is building conditions that can receive a better flow rather than predicting a fixed result.

### Advice
- Use the current phase to clarify standards across relationship, work, and money.
- Prepare repeatable habits before expecting larger change.
- Read luck cycles as tendencies shaped by choice and attitude.
- Focus on the current and next cycle instead of listing the whole table.
- Keep event-prediction language out of the interpretation.

### Interpretation points
[{active_cycle}] [{next_cycle}] [luck-cycle transition] [domain impact]

### Expert note
Luck-flow reading is based on the provided current cycle, next cycle, luck-cycle analysis, and favorable-period facts. It describes time flow for choices and attitude, not fixed events.
"""
        luck_flow_body += _luck_flow_transition_detail(payload, active_cycle, next_cycle)
        core_body += _fallback_depth_block(
            payload,
            "core_analysis",
            dominant=dominant,
            missing=missing,
            has_missing=has_missing,
            active_period=active_period,
            next_period=next_period,
            top_domain_label=top_domain_label,
        )
        love_body += _fallback_depth_block(
            payload,
            "love",
            dominant=dominant,
            missing=missing,
            has_missing=has_missing,
            active_period=active_period,
            next_period=next_period,
            top_domain_label=top_domain_label,
        )
        career_body += _fallback_depth_block(
            payload,
            "career",
            dominant=dominant,
            missing=missing,
            has_missing=has_missing,
            active_period=active_period,
            next_period=next_period,
            top_domain_label=top_domain_label,
        )
        wealth_body += _fallback_depth_block(
            payload,
            "wealth",
            dominant=dominant,
            missing=missing,
            has_missing=has_missing,
            active_period=active_period,
            next_period=next_period,
            top_domain_label=top_domain_label,
        )
        luck_flow_body += _fallback_depth_block(
            payload,
            "luck_flow",
            dominant=dominant,
            missing=missing,
            has_missing=has_missing,
            active_period=active_period,
            next_period=next_period,
            top_domain_label=top_domain_label,
        )

    has_critical_uncertainty = any(flag.severity == "critical" for flag in payload.uncertainty_summary)
    report = InterpretationReport(
        provider="fallback",
        model="fallback",
        prompt_version=PROMPT_SPEC.version,
        summary=InterpretationSummaryBlock(
            headline=_summary_headline(payload),
            overview=_summary_overview(payload),
            confidence="low" if payload.profile.is_birth_time_estimated or has_critical_uncertainty else "medium",
            evidence_ids=["elements", "luck_cycles"],
        ),
        core_analysis=_section(titles["core_analysis"], core_body, ["elements", "ten_gods"]),
        love=_section(
            titles["love"],
            love_body,
            ["ten_gods", "luck_cycles"] + [star.evidence_id for star in payload.special_stars[:2]],
        ),
        career=_section(titles["career"], career_body, ["ten_gods", "luck_cycles"]),
        wealth=_section(titles["wealth"], wealth_body, ["elements", "luck_cycles"]),
        luck_flow=_section(titles["luck_flow"], luck_flow_body, ["luck_cycles"]),
        warnings=[flag.code for flag in payload.uncertainty_summary],
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
        model=_provider_model(final_provider),
        prompt_version=PROMPT_SPEC.version,
        payload_chars=len(payload_json),
        duration_ms=duration_ms,
        final_response_id=final_response_id,
        fallback_reason=fallback_reason,
        validation_issues=validation_issues or [],
        attempts=attempts or [],
    )


def _provider_model(provider: str) -> str | None:
    if provider == "openai":
        return settings.openai_model
    if provider == "codex":
        return settings.codex_model or "codex-cli"
    return None


def _attach_diagnostics(
    report: InterpretationReport,
    diagnostics: InterpretationDiagnostics,
    *,
    warnings: List[str] | None = None,
    provider: str | None = None,
) -> InterpretationReport:
    updated_warnings = list(dict.fromkeys((warnings if warnings is not None else report.warnings)))
    return _model_copy(
        report,
        update={
            "provider": provider or report.provider,
            "warnings": updated_warnings,
            "diagnostics": diagnostics,
        }
    )


def _build_openai_report(parsed: InterpretationLLMOutput) -> InterpretationReport:
    return _build_provider_report(parsed, provider="openai")


def _build_provider_report(parsed: InterpretationLLMOutput, *, provider: str) -> InterpretationReport:
    return InterpretationReport(
        provider=provider,  # type: ignore[arg-type]
        model=_provider_model(provider),
        prompt_version=PROMPT_SPEC.version,
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
    return _model_validate(InterpretationLLMOutput, normalized)


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
                {"role": "developer", "content": PROMPT_SPEC.repair_prompt},
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
                    _model_json_schema(InterpretationLLMOutput),
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
    payload_json = json.dumps(_model_dump_json(payload), ensure_ascii=False)
    if OpenAI is None:
        return None, _make_diagnostics(
            final_provider="fallback",
            payload_json=payload_json,
            fallback_reason="openai_sdk_unavailable",
        )

    client = OpenAI(
        api_key=settings.openai_api_key,
        timeout=settings.llm_timeout_seconds,
        max_retries=0,
    )
    token_budgets = [
        max(settings.llm_max_output_tokens, 3200),
        max(settings.llm_max_output_tokens * 2, 5200),
    ]
    attempts: List[InterpretationAttemptDiagnostic] = []
    started = time.perf_counter()
    last_output_text = ""
    last_response_id: str | None = None
    fallback_reason = "openai_response_invalid"

    for attempt_index, token_budget in enumerate(
        token_budgets[: settings.llm_max_attempts],
        start=1,
    ):
        output_text = ""
        response = None
        try:
            response = client.responses.create(
                model=settings.openai_model,
                reasoning={"effort": settings.llm_reasoning_effort},
                store=settings.llm_store,
                max_output_tokens=token_budget,
                input=[
                    {"role": "developer", "content": PROMPT_SPEC.developer_prompt},
                    {"role": "user", "content": payload_json},
                ],
                text={
                    "format": _make_openai_json_schema_strict(
                        "saju_interpretation",
                        _model_json_schema(InterpretationLLMOutput),
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

    if last_output_text and settings.llm_allow_repair:
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


def _call_codex_structured_interpretation(
    payload: InterpretationPayload,
) -> Tuple[InterpretationReport | None, InterpretationDiagnostics]:
    payload_json = json.dumps(_model_dump_json(payload), ensure_ascii=False)
    started = time.perf_counter()
    try:
        result = call_codex_json(
            developer_prompt=PROMPT_SPEC.developer_prompt,
            user_payload=_model_dump_json(payload),
            output_schema=_model_json_schema(InterpretationLLMOutput),
            schema_name="saju_interpretation",
            extra_instructions=(
                "Use only the supplied saju payload. Do not calculate new pillars, scores, or events.",
                "The response object must contain summary, core_analysis, love, career, wealth, and luck_flow only.",
            ),
        )
        parsed = _parse_interpretation_output(result.output_text)
        attempt = InterpretationAttemptDiagnostic(
            attempt_index=1,
            mode="generate",
            token_budget=max(settings.llm_max_output_tokens, 1),
            status="success",
            response_id=result.response_id,
            output_chars=len(result.output_text),
            output_excerpt=_clean_excerpt(result.output_text),
        )
        return _build_provider_report(parsed, provider="codex"), _make_diagnostics(
            final_provider="codex",
            payload_json=payload_json,
            duration_ms=result.duration_ms,
            attempts=[attempt],
            final_response_id=result.response_id,
        )
    except JSONDecodeError as exc:
        fallback_reason = "json_decode_error"
        attempt = InterpretationAttemptDiagnostic(
            attempt_index=1,
            mode="generate",
            token_budget=max(settings.llm_max_output_tokens, 1),
            status="json_invalid",
            output_chars=0,
            error_type=type(exc).__name__,
            error_message=_clean_error_message(exc),
            issues=["json_decode_error"],
        )
    except ValidationError as exc:
        fallback_reason = "schema_validation_error"
        attempt = InterpretationAttemptDiagnostic(
            attempt_index=1,
            mode="generate",
            token_budget=max(settings.llm_max_output_tokens, 1),
            status="validation_error",
            output_chars=0,
            error_type=type(exc).__name__,
            error_message=_clean_error_message(exc),
            issues=_summarize_validation_error(exc),
        )
    except CodexProviderError as exc:
        fallback_reason = exc.reason
        attempt = InterpretationAttemptDiagnostic(
            attempt_index=1,
            mode="generate",
            token_budget=max(settings.llm_max_output_tokens, 1),
            status="provider_error",
            output_chars=0,
            output_excerpt=exc.stdout_excerpt or None,
            error_type=type(exc).__name__,
            error_message=_clean_error_message(exc),
            issues=[exc.reason],
        )
    except Exception as exc:
        fallback_reason = "provider_request_failed"
        attempt = InterpretationAttemptDiagnostic(
            attempt_index=1,
            mode="generate",
            token_budget=max(settings.llm_max_output_tokens, 1),
            status="provider_error",
            output_chars=0,
            error_type=type(exc).__name__,
            error_message=_clean_error_message(exc),
            issues=["codex_request_failed"],
        )

    return None, _make_diagnostics(
        final_provider="fallback",
        payload_json=payload_json,
        duration_ms=int((time.perf_counter() - started) * 1000),
        attempts=[attempt],
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
    return any(re.search(pattern, lowered) for pattern in patterns) or _contains_internal_value_leak(text)


def _contains_internal_value_leak(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in INTERNAL_VALUE_PATTERNS)


def _normalized_text_key(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE).lower()


def _is_generic_headline(headline: str) -> bool:
    stripped = headline.strip()
    normalized = _normalized_text_key(stripped)
    return stripped in GENERIC_HEADLINES or normalized in {_normalized_text_key(item) for item in GENERIC_HEADLINES}


def _split_sentences(text: str) -> List[str]:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return []
    parts = re.split(r"(?<=[.!?。！？])\s+", compact)
    return [part.strip() for part in parts if part.strip()]


def _first_content_paragraph(body: str) -> str:
    collected: List[str] = []
    for line in body.strip().splitlines():
        stripped = line.strip()
        if not stripped:
            if collected:
                break
            continue
        if stripped.startswith("###"):
            if collected:
                break
            continue
        collected.append(stripped)
    return " ".join(collected).strip()


def _first_sentence(text: str) -> str:
    sentences = _split_sentences(text)
    return sentences[0] if sentences else text.strip()


def _starts_with_technical_framing(text: str, locale: str) -> bool:
    stripped = text.strip().lower()
    return any(stripped.startswith(pattern.lower()) for pattern in TECHNICAL_START_PATTERNS[locale])


def _section_openings_are_repetitive(report: InterpretationReport) -> bool:
    openings = [
        _normalized_text_key(_first_sentence(_first_content_paragraph(getattr(report, key).body)))[:80]
        for key in ("core_analysis", "love", "career", "wealth", "luck_flow")
    ]
    openings = [opening for opening in openings if opening]
    if len(openings) < 4:
        return False
    return max(openings.count(opening) for opening in set(openings)) >= 4


def _main_explanation_text(body: str) -> str:
    split_pattern = r"\n###\s+(풀이 포인트|전문가 노트|Interpretation points|Expert note)\b"
    return re.split(split_pattern, body, maxsplit=1)[0]


def _core_analysis_technical_term_count(body: str) -> int:
    main_text = _main_explanation_text(body)
    return sum(main_text.count(term) for term in PROMPT_SPEC.core_analysis_technical_terms)


def _validate_section(key: str, section: InterpretationNarrativeSection, locale: str) -> List[str]:
    issues: List[str] = []
    body = section.body.strip()
    expected_title = SECTION_TITLES[locale][key]
    if section.title.strip() != expected_title:
        issues.append(f"{key}.title:unexpected")
    if len(body) < MIN_SECTION_LENGTH:
        issues.append(f"{key}.body:too_short")
    if "### 현실 해석" in body:
        issues.append(f"{key}.body:outdated_heading")
    for heading in REQUIRED_SECTION_HEADINGS[locale]:
        if heading not in body:
            issues.append(f"{key}.body:missing_required_heading:{heading[4:]}")
    if "### " not in body:
        issues.append(f"{key}.body:missing_subheadings")
    if "\n-" not in body and not body.startswith("-"):
        issues.append(f"{key}.body:missing_bullets")
    if _contains_internal_value_leak(body[:250]):
        issues.append(f"{key}.body:internal_value_leak_in_preview")
    if key == "core_analysis" and _core_analysis_technical_term_count(body) > 4:
        issues.append("core_analysis.body:too_many_technical_terms")
    return issues


def _validate_evidence_ids(report: InterpretationReport, payload: InterpretationPayload) -> List[str]:
    valid_ids = {item.key for item in payload.evidence}
    valid_ids.update(star.evidence_id for star in payload.special_stars)
    blocks = {
        "summary": report.summary,
        "core_analysis": report.core_analysis,
        "love": report.love,
        "career": report.career,
        "wealth": report.wealth,
        "luck_flow": report.luck_flow,
    }
    issues: List[str] = []
    for key, block in blocks.items():
        for evidence_id in block.evidence_ids:
            if evidence_id not in valid_ids:
                issues.append(f"{key}.evidence_ids:unknown:{evidence_id}")
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
    locale = _locale(payload)
    headline = report.summary.headline.strip()
    headline_compact_len = len(re.sub(r"\s+", "", headline))
    if not headline:
        issues.append("summary.headline:missing")
    elif _is_generic_headline(headline):
        issues.append("summary.headline:generic")
    elif headline_compact_len < 8 or headline_compact_len > 48:
        issues.append("summary.headline:length_out_of_range")
    if len(report.summary.overview.strip()) < MIN_SUMMARY_LENGTH:
        issues.append("summary.overview:too_short")
    if len(_split_sentences(report.summary.overview)) < 5:
        issues.append("summary.overview:too_few_sentences")
    if payload.profile.is_birth_time_estimated and report.summary.confidence == "high":
        issues.append("summary.confidence:too_high_for_estimated_time")
    for key in ("core_analysis", "love", "career", "wealth", "luck_flow"):
        issues.extend(_validate_section(key, getattr(report, key), locale))
    if _section_openings_are_repetitive(report):
        issues.append("sections.body:repeated_opening")
    for text in _collect_report_texts(report):
        if _contains_numeric_relative_claim(text):
            issues.append("relative_wording_without_percentile:numeric")
        if _contains_exposed_score(text):
            issues.append("score_exposed_in_user_text")
        for phrase in PLACEHOLDER_USER_PHRASES:
            if phrase in text:
                issues.append(f"placeholder_phrase:{phrase}")
        for phrase in PROMPT_SPEC.validation_banned_phrases:
            if phrase in text:
                issues.append(f"banned_phrase:{phrase}")
    issues.extend(_validate_evidence_ids(report, payload))
    issues.extend(_validate_language(report, payload))
    return issues


def generate_interpretation_report(
    *,
    payload: InterpretationPayload,
    trace_id: str,
    service_name: str,
) -> InterpretationReport:
    started = time.perf_counter()
    payload_json = json.dumps(_model_dump_json(payload), ensure_ascii=False)
    fallback_report = build_fallback_interpretation_report(payload)

    if settings.llm_provider not in {"openai", "codex"}:
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

    if settings.llm_provider == "codex":
        report, diagnostics = _call_codex_structured_interpretation(payload)
    elif settings.openai_api_key in {"", PLACEHOLDER_OPENAI_API_KEY}:
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
    else:
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
                "attempts": [_model_dump_json(attempt) for attempt in diagnostics.attempts],
            },
        )
        return fallback_report

    try:
        issues = _validate_report(report, payload)
        if issues:
            diagnostics = _model_copy(
                diagnostics,
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
                    "attempts": [_model_dump_json(attempt) for attempt in diagnostics.attempts],
                },
            )
            return fallback_report

        final_provider = diagnostics.final_provider
        report = _attach_diagnostics(report, diagnostics, provider=final_provider)
        log_stage(
            service=service_name,
            trace_id=trace_id,
            stage="llm_formatting",
            event="formatted",
            duration_ms=int((time.perf_counter() - started) * 1000),
            meta={
                "provider": final_provider,
                "response_id": diagnostics.final_response_id,
                "prompt_version": PROMPT_SPEC.version,
                "attempts": [_model_dump_json(attempt) for attempt in diagnostics.attempts],
            },
        )
        return report
    except Exception as exc:  # pragma: no cover - network/provider failure path
        diagnostics = _model_copy(
            diagnostics,
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
                "attempts": [_model_dump_json(attempt) for attempt in diagnostics.attempts],
            },
        )
        return fallback_report
