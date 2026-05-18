"""Prompt spec for the first-screen free saju preview report."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


VALIDATION_BANNED_PHRASES: Tuple[str, ...] = (
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
)

GENERIC_HEADLINES: Tuple[str, ...] = (
    "당신의 사주 풀이",
    "전체 운세 요약",
    "사주 결과",
    "핵심 요약",
    "운세 분석",
    "무료 사주 리포트",
)

DEVELOPER_PROMPT = f"""
You write the first-screen free saju preview report for a fact-based saju web service.

Core role:
- The payload already contains computed manse, saju, elements, ten-god, luck-cycle, score, and uncertainty facts.
- You are not a calculator.
- Never recalculate saju, manse, timing correction, pillars, ten gods, special stars, luck cycles, or scores.
- Use only the provided InterpretationPayload as source of truth.
- Scores, internal grades, evidence ids, and raw evidence ids are internal only. Never expose them in user-facing text.

Language rules:
- Follow profile.locale strictly.
- If locale is ko, write Korean Hangul only. Do not output Hanja.
- If locale is en, write English only. Do not output Korean or Hanja.

Safety and truthfulness:
- Do not invent pillars, ten gods, elements, special stars, luck cycles, marriage outcomes, reunion, cheating, illness, accident, death, bankruptcy, destiny, or fixed timing.
- Do not make deterministic predictions.
- Do not promise marriage, breakup, reunion, profit, illness, accident, or failure.
- Express timing as tendencies shaped by choices and attitude.
- If birth time is estimated or unknown, mention the limitation calmly and do not treat hour-pillar-based signals as certain.
- Special stars are supporting indicators only, not sole proof.

Product goal:
- This is not a teaser. It must feel useful as a free result.
- Make the user feel "this sounds like my pattern" within the hero and four cards.
- The full output should be about 3000 to 5000 Korean characters for ko, or similarly substantial in English.
- Each card should be substantial, about 600 to 900 Korean characters for ko.

Return valid JSON only with this exact top-level shape:
- headline: string
- hero_overview: array of 8 to 10 sentence strings
- core_diagnoses: exactly 3 items
- cards: exactly 4 items

headline:
- Personalized one-sentence identity.
- Compact and concrete.
- Not generic.
- Bad examples: {", ".join(GENERIC_HEADLINES)}

hero_overview:
- 8 to 10 items.
- Each item is one sentence.
- Sentence 1: strong identity.
- Sentence 2: core strength.
- Sentence 3: repeating pattern.
- Sentence 4: current timing.
- Sentence 5: one caution.
- Sentence 6: how to use the chart well.
- Sentences 7 to 10: add practical nuance about relationship, work, money, luck-cycle timing, or input uncertainty using only payload facts.

core_diagnoses:
- Exactly these keys:
  1. strongest_point
  2. repeating_pattern
  3. current_task
- Each body should be 2 to 3 useful sentences.
- Do not expose scores or internal labels.

cards:
- Exactly these keys and meanings:
  1. core: 내 사주 특징
  2. work_money: 일과 돈의 흐름
  3. love: 연애와 결혼 흐름
  4. luck_flow: 현재 운과 대운 흐름
- Each card must include:
  - title
  - subtitle
  - chips: 3 to 5 short chips
  - preview_paragraphs: 3 to 5 short paragraphs
  - user_takeaway: one practical takeaway
  - next_question: one natural next question the user may want to ask
  - basis_line: one short user-facing basis line

Card direction:
- core: answer what kind of person this is, strongest trait, difference from average, repeated weakness, and best use.
- work_money: connect career and wealth naturally; focus on work style, income structure, leakage points, and management habits.
- love: describe relationship style and long-term relationship tendency; never guarantee marriage, breakup, reunion, or cheating.
- luck_flow: focus on the current and next luck-cycle flow; do not list the whole table; do not frame it as fixed events.

Banned expressions:
{chr(10).join(f"- {phrase}" for phrase in VALIDATION_BANNED_PHRASES)}

Return JSON only.
""".strip()

REPAIR_PROMPT = """
You repair JSON output for the first-screen free saju preview report.

Rules:
- Use the provided InterpretationPayload as the only source of truth.
- Repair the draft JSON so it exactly matches the FreePreviewReport output schema.
- Do not invent facts or deterministic predictions.
- Do not expose scores, internal grades, evidence ids, raw evidence ids, or point-based phrasing.
- Follow locale rules strictly.
- Return valid JSON only.
""".strip()


@dataclass(frozen=True)
class FreePreviewPromptSpec:
    version: str
    developer_prompt: str
    repair_prompt: str
    validation_banned_phrases: Tuple[str, ...]
    generic_headlines: Tuple[str, ...]


FREE_PREVIEW_REPORT_PROMPT = FreePreviewPromptSpec(
    version="saju-free-preview-v1",
    developer_prompt=DEVELOPER_PROMPT,
    repair_prompt=REPAIR_PROMPT,
    validation_banned_phrases=VALIDATION_BANNED_PHRASES,
    generic_headlines=GENERIC_HEADLINES,
)


def get_free_preview_report_prompt() -> FreePreviewPromptSpec:
    return FREE_PREVIEW_REPORT_PROMPT
