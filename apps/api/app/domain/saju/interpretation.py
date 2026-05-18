"""사주 해석 결과 스키마를 정의한다."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


InterpretationLocale = Literal["ko", "en"]
InterpretationConfidence = Literal["low", "medium", "high"]
InterpretationAttemptMode = Literal["generate", "repair"]
InterpretationAttemptStatus = Literal[
    "success",
    "json_invalid",
    "validation_error",
    "provider_error",
    "skipped",
]
FreePreviewDiagnosisKey = Literal["strongest_point", "repeating_pattern", "current_task"]
FreePreviewCardKey = Literal["core", "work_money", "love", "luck_flow"]


class InterpretationNarrative(BaseModel):
    schema_version: Literal["m2-fallback-v1"] = "m2-fallback-v1"
    locale: InterpretationLocale
    summary: str
    strengths: List[str]
    cautions: List[str]
    love: str
    career: str
    wealth: str
    action_advice: str


class InterpretationNarrativeSection(BaseModel):
    title: str = Field(max_length=64)
    body: str = Field(max_length=6000)
    evidence_ids: List[str] = Field(min_items=1, max_items=6)


class InterpretationSummaryBlock(BaseModel):
    headline: str = Field(max_length=64)
    overview: str = Field(max_length=900)
    confidence: InterpretationConfidence
    evidence_ids: List[str] = Field(min_items=1, max_items=6)


class InterpretationLLMOutput(BaseModel):
    summary: InterpretationSummaryBlock
    core_analysis: InterpretationNarrativeSection
    love: InterpretationNarrativeSection
    career: InterpretationNarrativeSection
    wealth: InterpretationNarrativeSection
    luck_flow: InterpretationNarrativeSection


class InterpretationAttemptDiagnostic(BaseModel):
    attempt_index: int = Field(ge=1)
    mode: InterpretationAttemptMode
    token_budget: int = Field(ge=1)
    status: InterpretationAttemptStatus
    response_id: Optional[str] = None
    output_chars: int = 0
    output_excerpt: Optional[str] = Field(default=None, max_length=320)
    error_type: Optional[str] = Field(default=None, max_length=64)
    error_message: Optional[str] = Field(default=None, max_length=320)
    issues: List[str] = Field(default_factory=list)


class InterpretationDiagnostics(BaseModel):
    configured_provider: str
    final_provider: Literal["openai", "fallback"]
    model: Optional[str] = None
    prompt_version: str
    payload_chars: int = 0
    duration_ms: int = 0
    final_response_id: Optional[str] = None
    fallback_reason: Optional[str] = None
    validation_issues: List[str] = Field(default_factory=list)
    attempts: List[InterpretationAttemptDiagnostic] = Field(default_factory=list)


class InterpretationReport(InterpretationLLMOutput):
    schema_version: Literal["m2-llm-v5"] = "m2-llm-v5"
    provider: Literal["openai", "fallback"]
    model: Optional[str] = None
    prompt_version: str = "saju-report-v14"
    warnings: List[str] = Field(default_factory=list)
    diagnostics: Optional[InterpretationDiagnostics] = None


class FreePreviewDiagnosis(BaseModel):
    key: FreePreviewDiagnosisKey
    title: str = Field(max_length=48)
    body: str = Field(max_length=700)


class FreePreviewCard(BaseModel):
    key: FreePreviewCardKey
    title: str = Field(max_length=48)
    subtitle: str = Field(max_length=96)
    chips: List[str] = Field(min_items=3, max_items=5)
    preview_paragraphs: List[str] = Field(min_items=3, max_items=5)
    user_takeaway: str = Field(max_length=360)
    next_question: str = Field(max_length=160)
    basis_line: str = Field(max_length=180)


class FreePreviewLLMOutput(BaseModel):
    headline: str = Field(max_length=64)
    hero_overview: List[str] = Field(min_items=8, max_items=10)
    core_diagnoses: List[FreePreviewDiagnosis] = Field(min_items=3, max_items=3)
    cards: List[FreePreviewCard] = Field(min_items=4, max_items=4)


class FreePreviewReport(FreePreviewLLMOutput):
    schema_version: Literal["free-preview-v1"] = "free-preview-v1"
    provider: Literal["openai", "fallback"]
    model: Optional[str] = None
    prompt_version: str = "saju-free-preview-v1"
    warnings: List[str] = Field(default_factory=list)
    diagnostics: Optional[InterpretationDiagnostics] = None
