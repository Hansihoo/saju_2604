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
    evidence_ids: List[str] = Field(min_length=1, max_length=6)


class InterpretationSummaryBlock(BaseModel):
    headline: str = Field(max_length=64)
    overview: str = Field(max_length=900)
    confidence: InterpretationConfidence
    evidence_ids: List[str] = Field(min_length=1, max_length=6)


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
    prompt_version: str = "saju-report-v7"
    warnings: List[str] = Field(default_factory=list)
    diagnostics: Optional[InterpretationDiagnostics] = None
