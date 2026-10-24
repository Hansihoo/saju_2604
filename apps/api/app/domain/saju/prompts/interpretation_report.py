"""Central prompt spec for the structured interpretation report."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple
from app.domain.saju.prompts.commercial_reading import (
    NARRATIVE_RULES, DEVELOPER_PROMPT, REPAIR_PROMPT,
)


DEVELOPER_BANNED_EXPRESSIONS: Tuple[str, ...] = (
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

CORE_ANALYSIS_DENSE_TERMS: Tuple[str, ...] = (
    "일간",
    "십성",
    "상관",
    "인성",
    "편관",
    "정관",
    "화개",
    "귀문관",
    "장성",
    "괴강",
)

CORE_ANALYSIS_TECHNICAL_TERMS: Tuple[str, ...] = (
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
)

@dataclass(frozen=True)
class InterpretationPromptSpec:
    version: str
    developer_prompt: str
    repair_prompt: str
    narrative_rules: Tuple[str, ...]
    validation_banned_phrases: Tuple[str, ...]
    core_analysis_technical_terms: Tuple[str, ...]
    prompt_seed_template: str

    def build_prompt_seed(self, *, locale: str, region_display_name: str) -> str:
        return self.prompt_seed_template.format(
            locale=locale,
            region_display_name=region_display_name,
        )


INTERPRETATION_REPORT_PROMPT = InterpretationPromptSpec(
    # v20 aligns exact titles/fact IDs and supplies selected initial-publication judgments.
    version="saju-report-v20",
    developer_prompt=DEVELOPER_PROMPT,
    repair_prompt=REPAIR_PROMPT,
    narrative_rules=NARRATIVE_RULES,
    validation_banned_phrases=VALIDATION_BANNED_PHRASES,
    core_analysis_technical_terms=CORE_ANALYSIS_TECHNICAL_TERMS,
    prompt_seed_template=(
        "Use {locale} only. Build a grounded saju reading for {region_display_name} "
        "with focus on current flow, love, career, wealth, and structure."
    ),
)


def get_interpretation_report_prompt() -> InterpretationPromptSpec:
    return INTERPRETATION_REPORT_PROMPT
