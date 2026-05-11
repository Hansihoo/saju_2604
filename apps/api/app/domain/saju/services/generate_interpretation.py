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


PROMPT_VERSION = "saju-report-v13"
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
BANNED_PHRASES = [
    "반드시",
    "무조건",
    "운명적으로",
    "100%",
    "대박",
    "큰돈을 번다",
    "결혼한다",
    "이혼한다",
    "바람난다",
    "사고가 난다",
    "병이 생긴다",
    "죽음",
    "파산",
    "망한다",
]
CORE_ANALYSIS_TECHNICAL_TERMS = [
    "일간",
    "십성",
    "상관",
    "인성",
    "편관",
    "정관",
    "식신",
    "재성",
    "관성",
    "신살",
    "화개",
    "귀문관",
    "장성",
    "괴강",
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
You are a modern Korean saju interpretation writer for a fact-based saju web service.

Core role:
- The payload already contains computed manse and saju facts.
- You are not a calculator. You are a user-facing interpretation writer.
- Never recalculate saju, manse, timing correction, pillars, ten gods, stars, luck cycles, or scores.
- Use only the provided payload as the source of truth.

Language rules:
- Follow profile.locale strictly.
- If locale is ko, write in Korean Hangul only. Do not output Hanja.
- If locale is en, write in English only. Do not output Korean or Hanja.

Truthfulness rules:
- Do not invent pillars, ten gods, elements, special stars, luck cycles, marriage outcomes, reunion, cheating, illness, accident, death, destiny, or timing.
- Do not make deterministic predictions.
- Avoid exaggerated certainty.
- Do not expose numeric scores, score labels, point-based phrasing, or internal scoring logic.
- If a score or signal exists in the payload, use it only to adjust tone and strength.
- If birth time is estimated or unknown, clearly mention the limitation and do not use hour-pillar-based interpretation as certain.
- Special stars must be used only as supporting indicators, never as the sole basis for a conclusion.

Style goal:
- Make the result easy to read but visibly grounded.
- The user should feel: "This is readable, but it is not random."
- Use simple everyday Korean first, especially in the main explanatory paragraphs.
- The main body should not read like a saju glossary.
- Use the plain meaning first, then put technical saju terms in "풀이 포인트" or "전문가 노트".
- If a saju term is necessary in the main body, explain it immediately in everyday language.
- Do not overload the user with technical terms.
- The result should feel substantial, not like a teaser.
- Prefer concrete life situations, tradeoffs, and practical reading logic over short generic summaries.
- Keep the reading scannable. Do not write long unbroken paragraphs.
- Every paragraph should be 1 to 2 sentences.
- If one idea needs more explanation, split it into separate short paragraphs instead of one long item.
- Bullet items should be short. Use one sentence per bullet when possible, and never put several dense explanations into one bullet.

Output structure:
- Return valid JSON that matches the existing schema.
- Do not add new top-level fields.
- Keep the existing section keys:
  summary, core_analysis, love, career, wealth, luck_flow.
- Put user-facing basis chips and expert notes inside each section body using markdown text.

Writing format for each major section body:
1. Start with a clear conclusion.
2. Explain the interpretation in plain Korean with enough detail.
3. Add practical advice.
4. Add a short "풀이 포인트" block with 2 to 4 basis chips.
5. Add a short "전문가 노트" block with 1 to 2 sentences explaining why the interpretation was made.

Length requirements:
- summary.overview should be 6 to 8 sentences.
- Each major section body must be substantial: about 900 to 1400 Korean characters for ko, or similarly detailed in English.
- Do not satisfy a section with only three bullets. Give the user enough context to understand why the conclusion follows from the payload.
- If a section feels short, expand with "how it appears in real life", "what to watch", and "how to use it well".

Use this section body pattern:

### 핵심 결론
Write 3 to 4 sentences.

### 쉽게 풀어보면
Write 5 to 8 sentences.
Split those sentences into 3 to 4 short paragraphs.
For ko, use the exact heading "쉽게 풀어보면". Do not use "현실 해석".
For en, use "Plain reading".

### 조언
- Write 4 to 6 practical bullet points.
- Each bullet should be one short idea. If a bullet needs two ideas, split it into two bullets.

### 풀이 포인트
[일간] [십성] [오행] [대운] style chips.
Use only terms that exist in the payload.

### 전문가 노트
Write 1 to 2 sentences.
Explain the logic simply.
This is the proper place for technical basis such as 일간, 십성, 오행, 신살, 대운.
Do not use raw evidence IDs.
Do not use the English word "evidence".

Section requirements:

summary:
- headline must be short and personalized.
- overview must summarize the whole reading in 6 to 8 sentences.
- Mention the strongest personality direction, current-period theme, and one caution.
- Do not include raw pillar tables in the overview.

core_analysis:
- Include standout traits, comparison, strengths, cautions, and direction.
- Use day master, element balance, ten gods, and major signals from the payload as hidden basis, but translate them into plain user-facing traits.
- In "핵심 결론", "쉽게 풀어보면", and "조언", avoid dense terms such as 일간, 십성, 상관, 인성, 편관, 정관, 화개, 귀문관, 장성, 괴강.
- Do not list many saju terms in consecutive sentences.
- Put detailed saju terms in "풀이 포인트" or "전문가 노트", and briefly explain what they mean.
- Prefer everyday phrases such as 기준이 뚜렷함, 분석과 정리, 표현력, 책임감, 몰입, 피로 누적, 관계의 부드러움, 속도 조절.
- Avoid abstract repetition such as "흐름", "기운", "안정" too often.

love:
- Include relationship style, marriage tendency, good match, difficult match, advice, and current-period reading.
- Use spouse house, partner star, love_facts, relevant ten gods, current_flow, and special stars if provided.
- Do not promise marriage, reunion, breakup, cheating, or fate.
- If 도화, 홍염, or similar stars appear, explain them as attraction or social attention indicators only.

career:
- Include work style, suitable environment, risks, strategy, and current-period reading.
- Use month pillar, career_facts, officer/resource/output indicators, current_flow, and relevant special stars if provided.
- Translate technical terms into practical work language such as planning, documentation, operations, responsibility, review, education, leadership, or execution.

wealth:
- Include money flow type, earning pattern, spending risk, management direction, and current-period reading.
- Interpret wealth using wealth star, output star, peer star, element balance, missing elements, current_flow, and relevant special stars if provided.
- If wealth star is weak or absent, do not say money luck is strong.
- If output exists, explain income through results, productivity, skills, content, sales, or deliverables.
- If peer is strong, explain competition, shared costs, relationship spending, or leakage risk.
- Do not give investment instructions, stock advice, coin advice, or guaranteed profit predictions.

luck_flow:
- The luck_flow section must answer the user's real timing questions.
- Use luck_flow_facts and luck_cycle_analysis as the main basis.
- Do not merely describe the current and next luck cycles.
- Explain what kind of period the user is in now.
- Explain whether the current period is a preparation, expansion, adjustment, stabilization, or transition period.
- Explain when the next major favorable period begins, based only on provided favorable_periods.
- Explain which domain improves: love, career, wealth, relationships, stability, visibility, or responsibility.
- Explain how long that favorable tendency lasts using provided periods only.
- Explain what changes when moving from the current luck cycle to the next luck cycle.
- Explain what the user should do now to use the next period well.
- If locale is ko, prefer labels such as "지금은 어떤 시기인가", "좋아지는 시기는 언제인가", "어떤 운이 좋아지는가", "다음 대운에서 무엇이 바뀌는가", and "지금 해야 할 것".
- If locale is en, prefer labels such as "what kind of period this is", "when the more favorable period begins", "which area improves", "what changes in the next cycle", and "what to do now".
- Describe better/worse areas as tendencies and management points, never as guaranteed outcomes.
- Do not list every luck cycle unless the schema or payload requires it.
- Do not say "best period" unless the payload explicitly marks a cycle as favorable.
- Use phrases like "상대적으로 유리한 구간", "힘이 실리는 시기", or "기반이 잡히는 시기" instead of deterministic claims.

Tone:
- Professional, readable, calm, and grounded.
- No fortune-teller exaggeration.
- No fear-based writing.
- No vague filler.
- Prefer concrete situations and choices.

Banned expressions:
- 반드시
- 무조건
- 운명적으로
- 대박
- 큰돈을 번다
- 결혼한다
- 이혼한다
- 바람난다
- 사고가 난다
- 병이 생긴다
- 죽음
- 파산
- 망한다

Return valid JSON only.
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
            f"강하게 드러나는 기운은 {dominant}이고, 약하게 보이는 기운은 {missing}입니다. "
            "그래서 장점이 살아나는 환경에서는 반응이 빠르지만, 부족한 쪽을 오래 방치하면 피로와 판단의 쏠림이 생기기 쉽습니다. "
            f"현재 기준 흐름은 {active_cycle}이며, 지금은 가진 장점을 크게 쓰기 전에 생활과 선택의 기준을 정리하는 의미가 큽니다. "
            "연애에서는 관계의 속도보다 지속 가능성을 보고, 직장에서는 역할과 책임의 선명함을 먼저 보는 편이 좋습니다. "
            "금전에서는 크게 키우는 감각보다 새는 지점을 줄이고 관리 기준을 세우는 쪽이 더 중요합니다. "
            "전체적으로는 강점을 믿되, 부족한 부분을 보완하는 루틴을 같이 만들 때 해석이 가장 좋게 쓰입니다."
        )
        if payload.profile.is_birth_time_estimated:
            text += " 출생시간이 미상이므로 시주 기반 해석은 보수적으로 제한했습니다."
        return text
    text = (
        f"The current reading uses the visible structure {pillars}. "
        f"The stronger elements are {dominant}, and the weaker side is {missing}. "
        "That means the chart can respond quickly in the right environment, while the weaker side can create fatigue or one-sided judgment when it is ignored. "
        f"The current timing is {_cycle_label(payload, payload.current_flow.active_luck_cycle)}. "
        "This makes the present period better for setting standards than forcing fast conclusions. "
        "In love, durability matters more than speed; in career, clear responsibility matters more than scattered effort. "
        "In wealth, the reading emphasizes reducing leakage and building rules before chasing scale. "
        "Overall, the chart works best when strengths are used together with routines that support the weaker side."
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
    active_cycle: str,
    next_cycle: str,
    top_domain_label: str,
) -> str:
    locale = _locale(payload)
    if locale == "ko":
        if section_key == "core_analysis":
            return f"""

### 4. 현실에서 드러나는 방식
- {dominant} 기운이 먼저 드러나는 사람은 판단과 반응이 빠르게 보일 수 있습니다. 다만 빠른 반응이 늘 장점으로만 쓰이는 것은 아니어서, 상황을 충분히 확인하기 전에 결론을 앞당기면 피로가 쌓일 수 있습니다.
- {missing} 기운은 사주에서 보완 과제로 읽습니다. 이 부분은 타고난 결핍이라는 뜻이 아니라, 생활 습관과 사람 선택으로 의식적으로 채워야 안정감이 커지는 영역입니다.
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
- 현재 흐름인 {active_cycle}에서는 관계를 급하게 확정하기보다, 갈등이 생겼을 때 대화가 이어지는지 확인하는 과정이 더 중요합니다.

### 5. 관계 조언
- 호감이 생겼을 때 바로 결론을 내리기보다, 반복되는 행동을 몇 번 더 확인해 보세요.
- 대화가 잘 되는 사람인지, 생활 패턴이 지나치게 흔들리지 않는지, 돈과 시간 약속을 어떻게 다루는지 같이 보는 편이 좋습니다.
- 다음 흐름인 {next_cycle}로 갈수록 지금 세운 관계 기준이 더 중요해질 수 있으니, 끌림과 안정감을 함께 보는 균형이 필요합니다.
"""
        if section_key == "career":
            return f"""

### 4. 성과가 나는 방식
- 이 직장운은 막연히 바쁜 환경보다 역할이 분명한 환경에서 더 잘 살아납니다. 해야 할 일, 책임 범위, 평가 기준이 정리되어 있을수록 실력이 누적되고 주변에서도 신뢰를 확인하기 쉽습니다.
- 반대로 기준이 자주 바뀌거나 말로만 급한 일이 많은 곳에서는 능력보다 소모가 먼저 커질 수 있습니다. 이런 경우에는 더 열심히 하는 것보다 업무 범위와 우선순위를 문서나 대화로 정리하는 편이 도움이 됩니다.
- 현재 흐름인 {active_cycle}에서는 넓게 벌리기보다 핵심 역량을 선명하게 만드는 쪽이 좋습니다. 다음 흐름인 {next_cycle}에서는 지금 만든 전문성의 기준이 역할 변화나 책임 증가로 이어질 수 있습니다.

### 5. 직업 선택 기준
- 직업명보다 실제 업무 방식이 더 중요합니다.
- 반복해서 쌓이는 기술, 정리와 검토가 필요한 업무, 책임 범위가 분명한 자리가 잘 맞을 가능성이 있습니다.
- 피해야 할 것은 기준 없이 계속 불이 나는 환경입니다. 그런 곳에서는 장점이 드러나기 전에 피로가 먼저 커질 수 있습니다.
"""
        if section_key == "wealth":
            return f"""

### 4. 돈이 모이고 새는 지점
- 이 금전운은 한 번에 크게 키우는 흐름보다, 들어온 돈을 어떻게 남기고 배치하느냐가 중요합니다. 수입이 생겨도 기준이 흐리면 관계 비용, 충동 소비, 급한 선택으로 체감 안정감이 줄어들 수 있습니다.
- {missing} 기운이 약하게 보이는 만큼, 돈 문제에서는 감정에 따라 결정을 미루거나 갑자기 크게 움직이는 패턴을 조심하는 편이 좋습니다. 숫자를 복잡하게 다루기보다 고정 지출, 예비비, 반복 소비를 먼저 나누는 단순한 기준이 더 잘 맞습니다.
- 현재 흐름인 {active_cycle}에서는 확장보다 정리가 먼저입니다. 다음 흐름인 {next_cycle}에서 더 안정적으로 쓰려면 지금 새는 곳을 줄이는 습관이 바탕이 됩니다.

### 5. 금전 조언
- 큰 계획을 세우기 전에 매달 반복되는 지출부터 확인하세요.
- 사람 때문에 쓰는 돈과 나를 위해 투자하는 돈을 구분해 두는 편이 좋습니다.
- 수익을 키우는 선택은 가능성을 보되, 유지 가능한 구조인지 먼저 확인하는 것이 중요합니다.
"""
        if section_key == "luck_flow":
            return f"""

### 흐름을 쓰는 법
- 대운은 사건을 하나씩 맞히는 도구라기보다, 어떤 태도가 더 잘 먹히는 시기인지 보는 기준에 가깝습니다. 현재 {active_cycle}에서는 속도를 내기보다 기준을 세우고, 다음 {next_cycle}에서는 그 기준이 실제 선택과 책임으로 드러나는 흐름으로 읽습니다.
- 그래서 지금 해야 할 일은 운이 좋아질 때를 기다리는 것이 아니라, 좋아지는 흐름을 받을 수 있는 상태를 만들어 두는 것입니다. 관계에서는 오래 갈 기준을, 일에서는 반복해서 쓸 전문성을, 금전에서는 새지 않는 구조를 먼저 준비하는 편이 좋습니다.
- 좋고 나쁨은 고정된 결과가 아니라 관리 포인트입니다. 같은 흐름도 준비가 되어 있으면 기회처럼 느껴지고, 기준이 없으면 부담처럼 느껴질 수 있습니다.
"""
    if section_key == "core_analysis":
        return f"""

### 4. How this appears in real life
- When {dominant} shows first, the person can seem quick to respond and quick to recognize what works. That speed is useful, but it can also become tiring if conclusions are made before the situation is fully checked.
- The weaker side, {missing}, is not a fixed flaw. It is the part that needs routines, environment, and repeated choices to become more stable.
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
- In the current timing, {active_cycle}, checking durability is more useful than rushing a label.

### 5. Relationship advice
- Watch repeated behavior before making a conclusion.
- Notice how the person handles conversation, daily rhythm, money, and time promises.
- As the chart moves toward {next_cycle}, the relationship standards built now can matter more, so attraction and stability should be read together.
"""
    if section_key == "career":
        return f"""

### 4. How results are built
- This career pattern works better where roles, ownership, and standards are clear. When responsibilities are defined, skill can accumulate and trust can become easier to see.
- In a place where priorities constantly move, effort may turn into fatigue before results become visible. In that case, clarifying scope and order can help more than simply working harder.
- In the current timing, {active_cycle}, sharpening the core specialty is more useful than spreading effort. In {next_cycle}, the standards built now can shape later role changes.

### 5. Work-fit criteria
- The actual work pattern matters more than the job title.
- Roles involving accumulated skill, review, organization, responsibility, or structured execution can be a better fit.
- The main environment to avoid is one where everything is urgent but nothing is defined.
"""
    if section_key == "wealth":
        return f"""

### 4. Where money gathers and leaks
- This wealth reading emphasizes keeping and directing money more than dramatic expansion. Even when income appears, unclear standards can reduce the felt stability through relationship costs, impulse spending, or rushed choices.
- Because {missing} is weaker, money decisions should be made with simple rules rather than mood. Fixed expenses, reserve funds, and repeated spending are better starting points than complicated plans.
- In the current timing, {active_cycle}, organization comes before expansion. Habits built now can make {next_cycle} feel more stable.

### 5. Money advice
- Review recurring expenses before making larger plans.
- Separate money spent for people from money invested in yourself.
- When considering growth, first check whether the structure can be maintained.
"""
    return f"""

### How to use the flow
- Luck cycles are better used as timing context than as fixed event prediction. The current {active_cycle} favors setting standards, while the next {next_cycle} can make those standards more visible through choices and responsibility.
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
            current_period = facts.current_period or "확인 대기"
            next_label = facts.next_luck_cycle or next_cycle
            next_period = facts.next_period or "확인 대기"
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
다음 {next_label} 대운은 {next_period} 구간이며, 성격은 {facts.next_phase_label or "다음 단계 준비"} 쪽으로 이동합니다.
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
        limitation = (
            "\n출생 시간이 미상이거나 추정이면 대운 전환 해석은 확정적으로 보지 않고 방향성만 참고해야 합니다."
            if payload.profile.is_birth_time_estimated
            else ""
        )
        return f"""

### 현재와 다음 대운의 차이
- 현재 대운인 {active_cycle}에서는 이미 가진 강점을 정리하고, 생활과 일과 돈의 기준을 세우는 쪽이 좋아지기 쉽습니다.
- 다만 기준이 흐려지면 속도보다 피로, 지출, 관계 부담이 먼저 커질 수 있어 주의가 필요합니다.
- 다음 대운인 {next_cycle}로 넘어가면 지금 만든 기준이 결과나 역할 변화로 드러나기 쉽습니다.
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
- In the current cycle, {active_cycle}, the easier gains tend to come from organizing strengths and setting standards for life, work, and money.
- The part that needs more care is losing those standards, because fatigue, spending leakage, or relationship burden can become more noticeable than speed.
- In the next cycle, {next_cycle}, the standards built now can show up more clearly as results, responsibility, or role changes.
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

### 2. 내 사주의 특징
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
        luck_flow_body += _luck_flow_transition_detail(payload, active_cycle, next_cycle)
        core_body += _fallback_depth_block(
            payload,
            "core_analysis",
            dominant=dominant,
            missing=missing,
            active_cycle=active_cycle,
            next_cycle=next_cycle,
            top_domain_label=top_domain_label,
        )
        love_body += _fallback_depth_block(
            payload,
            "love",
            dominant=dominant,
            missing=missing,
            active_cycle=active_cycle,
            next_cycle=next_cycle,
            top_domain_label=top_domain_label,
        )
        career_body += _fallback_depth_block(
            payload,
            "career",
            dominant=dominant,
            missing=missing,
            active_cycle=active_cycle,
            next_cycle=next_cycle,
            top_domain_label=top_domain_label,
        )
        wealth_body += _fallback_depth_block(
            payload,
            "wealth",
            dominant=dominant,
            missing=missing,
            active_cycle=active_cycle,
            next_cycle=next_cycle,
            top_domain_label=top_domain_label,
        )
        luck_flow_body += _fallback_depth_block(
            payload,
            "luck_flow",
            dominant=dominant,
            missing=missing,
            active_cycle=active_cycle,
            next_cycle=next_cycle,
            top_domain_label=top_domain_label,
        )
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
        luck_flow_body += _luck_flow_transition_detail(payload, active_cycle, next_cycle)
        core_body += _fallback_depth_block(
            payload,
            "core_analysis",
            dominant=dominant,
            missing=missing,
            active_cycle=active_cycle,
            next_cycle=next_cycle,
            top_domain_label=top_domain_label,
        )
        love_body += _fallback_depth_block(
            payload,
            "love",
            dominant=dominant,
            missing=missing,
            active_cycle=active_cycle,
            next_cycle=next_cycle,
            top_domain_label=top_domain_label,
        )
        career_body += _fallback_depth_block(
            payload,
            "career",
            dominant=dominant,
            missing=missing,
            active_cycle=active_cycle,
            next_cycle=next_cycle,
            top_domain_label=top_domain_label,
        )
        wealth_body += _fallback_depth_block(
            payload,
            "wealth",
            dominant=dominant,
            missing=missing,
            active_cycle=active_cycle,
            next_cycle=next_cycle,
            top_domain_label=top_domain_label,
        )
        luck_flow_body += _fallback_depth_block(
            payload,
            "luck_flow",
            dominant=dominant,
            missing=missing,
            active_cycle=active_cycle,
            next_cycle=next_cycle,
            top_domain_label=top_domain_label,
        )

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
    return _model_copy(
        report,
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


def _main_explanation_text(body: str) -> str:
    split_pattern = r"\n###\s+(풀이 포인트|전문가 노트|Interpretation points|Expert note)\b"
    return re.split(split_pattern, body, maxsplit=1)[0]


def _core_analysis_technical_term_count(body: str) -> int:
    main_text = _main_explanation_text(body)
    return sum(main_text.count(term) for term in CORE_ANALYSIS_TECHNICAL_TERMS)


def _validate_section(key: str, section: InterpretationNarrativeSection) -> List[str]:
    issues: List[str] = []
    body = section.body.strip()
    if len(body) < MIN_SECTION_LENGTH:
        issues.append(f"{key}.body:too_short")
    if "### 현실 해석" in body:
        issues.append(f"{key}.body:outdated_heading")
    if "### " not in body:
        issues.append(f"{key}.body:missing_subheadings")
    if "\n-" not in body and not body.startswith("-"):
        issues.append(f"{key}.body:missing_bullets")
    if key == "core_analysis" and _core_analysis_technical_term_count(body) > 4:
        issues.append("core_analysis.body:too_many_technical_terms")
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
    payload_json = json.dumps(_model_dump_json(payload), ensure_ascii=False)
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
