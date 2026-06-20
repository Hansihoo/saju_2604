"""사주 해석 결과 스키마를 정의한다."""

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


InterpretationLocale = Literal["ko", "en"]
InterpretationConfidence = Literal["low", "medium", "high"]
LLMProvider = Literal["openai", "codex", "fallback"]
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
SajuDetailType = Literal[
    "love_timing",
    "ideal_partner",
    "wealth_timing",
    "career_timing",
    "yearly_caution",
    "monthly_flow",
    "relationship_support",
    "health_condition",
    "compatibility_compare",
]


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
    final_provider: LLMProvider
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
    provider: LLMProvider
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
    provider: LLMProvider
    model: Optional[str] = None
    prompt_version: str = "saju-free-preview-v1"
    warnings: List[str] = Field(default_factory=list)
    diagnostics: Optional[InterpretationDiagnostics] = None


class SajuDetailPreparedReport(BaseModel):
    schema_version: Literal["saju-detail-v1"] = "saju-detail-v1"
    report_id: str
    input_hash: str
    prepared_at: str
    base_context: Dict[str, object]
    detail_analysis_bundle: Dict[str, Dict[str, object]]


class SajuDetailPeriod(BaseModel):
    label: str = Field(max_length=80)
    period: str = Field(max_length=80)
    description: str = Field(max_length=420)


class SajuDetailBody(BaseModel):
    conclusion: str = Field(max_length=700)
    periods: List[SajuDetailPeriod] = Field(default_factory=list, max_items=6)
    cautions: List[str] = Field(default_factory=list, max_items=6)
    advice: List[str] = Field(default_factory=list, max_items=6)
    basis_chips: List[str] = Field(default_factory=list, max_items=8)


class SajuDetailRenderedReport(BaseModel):
    schema_version: Literal["saju-detail-render-v1"] = "saju-detail-render-v1"
    detail_type: SajuDetailType
    title: str = Field(max_length=80)
    summary: str = Field(max_length=260)
    body: SajuDetailBody
