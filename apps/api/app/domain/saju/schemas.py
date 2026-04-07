from datetime import date
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, constr


PipelineState = Literal["passed", "failed", "skipped", "disabled"]
BirthTimeStr = constr(pattern=r"^\d{2}:\d{2}$")


class RegionSuggestion(BaseModel):
    id: str
    display_name: str
    country: str
    province: str
    city: str
    tzid: str
    longitude: float
    regional_time_offset_minutes: float
    correction_basis: str


class RegionSearchResponse(BaseModel):
    trace_id: str
    items: List[RegionSuggestion]
    total: int


class SajuPreviewRequest(BaseModel):
    calendar_type: Literal["solar", "lunar"] = "solar"
    birth_date: date
    birth_time: BirthTimeStr = Field(default="00:00")
    is_birth_time_estimated: bool = False
    is_lunar_leap_month: bool = False
    gender: Literal["male", "female"] = "male"
    region_id: str
    debug: bool = False


class PipelineStatus(BaseModel):
    input_validation: PipelineState = "passed"
    region_resolution: PipelineState = "passed"
    time_correction: PipelineState = "skipped"
    calendar_normalization: PipelineState = "skipped"
    regional_solar_correction: PipelineState = "skipped"
    saju_calculation: PipelineState = "skipped"
    analysis_engine: PipelineState = "skipped"
    llm_formatting: PipelineState = "skipped"


class EvidenceSection(BaseModel):
    title: str
    status: Literal["ready", "disabled", "coming_soon"]
    summary: str


class TimeCorrectionSummary(BaseModel):
    tzid: str
    source_local_datetime: str
    normalized_local_datetime: str
    normalized_utc_datetime: str
    offset_minutes: int
    ambiguous: bool
    fold: int


class RegionalSolarCorrectionSummary(BaseModel):
    source_solar_datetime: str
    corrected_solar_datetime: str
    longitude: float
    regional_time_offset_minutes: float
    daylight_saving_offset_minutes: int = 0
    correction_basis: str


class CalendarNormalizationSummary(BaseModel):
    calendar_type: Literal["solar", "lunar"]
    is_lunar_leap_month: bool
    input_date: str
    input_time: str
    normalized_solar_datetime: str
    normalized_lunar_datetime: str
    solar_year: int
    solar_month: int
    solar_day: int
    solar_hour: int
    solar_minute: int
    lunar_year: int
    lunar_month: int
    lunar_day: int


class MansePillar(BaseModel):
    key: Literal["year", "month", "day", "time"]
    label: str
    enabled: bool
    gan_zhi: Optional[str] = None
    stem: Optional[str] = None
    branch: Optional[str] = None
    stem_element: Optional[str] = None
    branch_element: Optional[str] = None
    stem_ten_god: Optional[str] = None
    branch_ten_god: Optional[str] = None
    branch_ten_gods: List[str] = Field(default_factory=list)
    hidden_stems: List[str] = Field(default_factory=list)
    twelve_fortune: Optional[str] = None
    twelve_shinsal: Optional[str] = None
    na_yin: Optional[str] = None
    xun: Optional[str] = None
    xun_kong: Optional[str] = None


class MansePillarSet(BaseModel):
    year: MansePillar
    month: MansePillar
    day: MansePillar
    time: MansePillar


class ManseTableRow(BaseModel):
    label: str
    year: str
    month: str
    day: str
    time: str


class ManseLuckCycle(BaseModel):
    index: int
    gan_zhi: str
    start_year: int
    end_year: int
    start_age: int
    end_age: int


class ManseSupplementaryPosition(BaseModel):
    key: str
    label: str
    gan_zhi: str
    na_yin: str


class ManseSupplementaryPositionSet(BaseModel):
    tai_yuan: ManseSupplementaryPosition
    ming_gong: ManseSupplementaryPosition
    shen_gong: ManseSupplementaryPosition
    tai_xi: ManseSupplementaryPosition


class ManseElementSummary(BaseModel):
    wood: int
    fire: int
    earth: int
    metal: int
    water: int


class ManseMeta(BaseModel):
    schema_version: Literal["v1"] = "v1"
    day_master: str
    pillar_order: List[Literal["year", "month", "day", "time"]]
    visible_pillar_keys: List[Literal["year", "month", "day", "time"]]
    hour_pillar_enabled: bool


class ManseData(BaseModel):
    meta: ManseMeta
    pillars: MansePillarSet
    table_rows: List[ManseTableRow]
    elements: ManseElementSummary
    luck_cycles_enabled: bool
    luck_cycles: List[ManseLuckCycle]
    supplementary_positions: ManseSupplementaryPositionSet
    notes: List[str]


class SajuPreviewResult(BaseModel):
    overview: str
    strengths: List[str]
    cautions: List[str]
    love: str
    career: str
    wealth: str
    action_advice: str
    limitations: List[str]
    disabled_sections: List[str]
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
    time_correction: TimeCorrectionSummary
    regional_solar_correction: RegionalSolarCorrectionSummary
    calendar_normalization: CalendarNormalizationSummary
    manse: ManseData
    result: SajuPreviewResult
    debug_trace: Optional[DebugTrace] = None
