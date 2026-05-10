"""이 파일은 API 요청과 응답에 사용하는 Pydantic schema를 정의한다."""

from datetime import date
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, constr

from app.domain.saju.analysis import InternalGrade
from app.domain.saju.interpretation import InterpretationReport


PipelineState = Literal["passed", "failed", "skipped", "disabled"]
try:
    BirthTimeStr = constr(pattern=r"^\d{2}:\d{2}$")
except TypeError:
    BirthTimeStr = constr(regex=r"^\d{2}:\d{2}$")
ElementKey = Literal["wood", "fire", "earth", "metal", "water"]


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
    aliases: List[str] = Field(default_factory=list)
    latitude: Optional[float] = None
    admin_code: Optional[str] = None
    source: str = "csv_seed"
    is_active: bool = True


class RegionSearchResponse(BaseModel):
    trace_id: str
    items: List[RegionSuggestion]
    total: int


class SajuPreviewRequest(BaseModel):
    locale: Literal["ko", "en"] = "ko"
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


class ManseSpecialStarMatch(BaseModel):
    pillar_key: Literal["year", "month", "day", "time"]
    pillar_label: str
    gan_zhi: str
    stem: str
    branch: str
    matched_field: Literal["stem", "branch", "gan_zhi", "pair"]
    matched_value: str
    counterpart_pillar_key: Optional[Literal["year", "month", "day", "time"]] = None
    counterpart_pillar_label: Optional[str] = None
    counterpart_gan_zhi: Optional[str] = None
    counterpart_branch: Optional[str] = None


class ManseSpecialStar(BaseModel):
    key: str
    family: str
    label: str
    category: Literal["auspicious", "sinsal"]
    tier: Literal["S", "A", "B"]
    scope: Literal["core", "expanded", "optional"]
    weight: float
    method_id: str
    basis_key: str
    basis: str
    anchor_value: str
    target_values: List[str] = Field(default_factory=list)
    usage_summary: str
    usage_keywords: List[str] = Field(default_factory=list)
    note: Optional[str] = None
    active: bool
    count: int
    matches: List[ManseSpecialStarMatch] = Field(default_factory=list)


class ManseLuckCycle(BaseModel):
    index: int
    gan_zhi: str
    start_year: int
    end_year: int
    start_age: int
    end_age: int
    start_datetime: Optional[str] = None
    change_datetime: Optional[str] = None


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


class ManseElementPercentageSummary(BaseModel):
    wood: float
    fire: float
    earth: float
    metal: float
    water: float


class ManseMeta(BaseModel):
    schema_version: Literal["v1"] = "v1"
    day_master: str
    pillar_order: List[Literal["year", "month", "day", "time"]]
    visible_pillar_keys: List[Literal["year", "month", "day", "time"]]
    hour_pillar_enabled: bool


class ManseAnalysisSummary(BaseModel):
    visible_element_total: int
    imbalance_gap: int
    dominant_elements: List[ElementKey]
    missing_elements: List[ElementKey]
    element_percentages: ManseElementPercentageSummary
    visible_ten_god_distribution: Dict[str, int]
    balance_score: int
    internal_grade: InternalGrade
    charm_score: int
    wealth_score: int
    career_score: int
    leadership_score: int
    first_luck_cycle_direction: Optional[Literal["forward", "backward"]] = None
    first_luck_cycle_exact_start_age_years: Optional[float] = None
    first_luck_cycle_precise_start_age_years: Optional[float] = None
    first_luck_cycle_boundary_datetime: Optional[str] = None


class ManseData(BaseModel):
    meta: ManseMeta
    pillars: MansePillarSet
    table_rows: List[ManseTableRow]
    elements: ManseElementSummary
    analysis: ManseAnalysisSummary
    luck_cycles_enabled: bool
    luck_cycles: List[ManseLuckCycle]
    supplementary_positions: ManseSupplementaryPositionSet
    special_stars: List[ManseSpecialStar] = Field(default_factory=list)
    notes: List[str]


class SajuResultSignals(BaseModel):
    visible_pillar_keys: List[Literal["year", "month", "day", "time"]]
    visible_pillar_values: List[str]
    dominant_elements: List[ElementKey]
    missing_elements: List[ElementKey]
    balance_score: int
    charm_score: int
    wealth_score: int
    career_score: int
    leadership_score: int
    internal_grade: InternalGrade


class SajuPreviewResult(BaseModel):
    overview: str
    strengths: List[str]
    cautions: List[str]
    love: str
    career: str
    wealth: str
    action_advice: str
    interpretation: Optional[InterpretationReport] = None
    limitations: List[str]
    disabled_sections: List[str]
    evidence_sections: Dict[str, EvidenceSection]
    hour_pillar_enabled: bool
    signals: SajuResultSignals


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
    response_mode: Literal["preview"] = "preview"
    pipeline_status: PipelineStatus
    region: RegionSuggestion
    time_correction: TimeCorrectionSummary
    regional_solar_correction: RegionalSolarCorrectionSummary
    calendar_normalization: CalendarNormalizationSummary
    manse: ManseData
    result: SajuPreviewResult
    debug_trace: Optional[DebugTrace] = None
