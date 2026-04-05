from datetime import date
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


PipelineState = Literal["passed", "failed", "skipped", "disabled"]


class RegionSuggestion(BaseModel):
    id: str
    display_name: str
    country: str
    city: str
    tzid: str


class RegionSearchResponse(BaseModel):
    trace_id: str
    items: List[RegionSuggestion]
    total: int


class SajuPreviewRequest(BaseModel):
    calendar_type: Literal["solar", "lunar"] = "solar"
    birth_date: date
    birth_time: str = Field(default="00:00")
    is_birth_time_estimated: bool = False
    gender: Literal["male", "female"] = "male"
    region_id: str
    debug: bool = False


class PipelineStatus(BaseModel):
    input_validation: PipelineState = "passed"
    region_resolution: PipelineState = "passed"
    time_correction: PipelineState = "skipped"
    calendar_normalization: PipelineState = "skipped"
    saju_calculation: PipelineState = "skipped"
    analysis_engine: PipelineState = "skipped"
    llm_formatting: PipelineState = "skipped"


class EvidenceSection(BaseModel):
    title: str
    status: Literal["ready", "disabled", "coming_soon"]
    summary: str


class SajuPreviewResult(BaseModel):
    overview: str
    strengths: List[str]
    cautions: List[str]
    love: str
    career: str
    wealth: str
    action_advice: str
    limitations: List[str]
    evidence_sections: Dict[str, EvidenceSection]
    hour_pillar_enabled: bool


class DebugCheckpoint(BaseModel):
    stage: str
    status: PipelineState
    note: Optional[str] = None
    error_code: Optional[str] = None


class DebugTrace(BaseModel):
    stage_order: List[str]
    failed_stage: Optional[str] = None
    checkpoints: List[DebugCheckpoint]
    request_echo: Dict[str, str]


class SajuPreviewResponse(BaseModel):
    trace_id: str
    response_mode: Literal["mock"] = "mock"
    pipeline_status: PipelineStatus
    region: RegionSuggestion
    result: SajuPreviewResult
    debug_trace: Optional[DebugTrace] = None
