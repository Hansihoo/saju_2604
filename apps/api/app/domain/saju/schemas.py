"""이 파일은 API 요청과 응답에 사용하는 Pydantic schema를 정의한다."""

from datetime import date
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, constr

from app.domain.saju.analysis import InternalGrade
from app.domain.saju.interpretation import (
    FreePreviewReport,
    InterpretationReport,
    SajuDetailPreparedReport,
    SajuDetailRenderedReport,
    SajuDetailType,
)


PipelineState = Literal["passed", "failed", "skipped", "disabled"]
FreePreviewFormattingState = Literal["success", "fallback", "failed", "skipped"]
try:
    BirthTimeStr = constr(pattern=r"^\d{2}:\d{2}$")
except TypeError:
    BirthTimeStr = constr(regex=r"^\d{2}:\d{2}$")
ElementKey = Literal["wood", "fire", "earth", "metal", "water"]
AccuracyMode = Literal["legacy", "standard_time", "mean_solar_time", "compare"]


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
    accuracy_mode: AccuracyMode = "legacy"
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
    free_preview_formatting: FreePreviewFormattingState = "skipped"


class EvidenceSection(BaseModel):
    title: str
    status: Literal["ready", "disabled", "coming_soon"]
    summary: str


class UncertaintyFlagSummary(BaseModel):
    code: str
    severity: Literal["info", "warning", "critical"]
    affected_fields: List[str]
    user_message: str
    developer_message: str
    evidence: Dict[str, object] = Field(default_factory=dict)


class CalculationBasisSummary(BaseModel):
    accuracy_mode: AccuracyMode = "legacy"
    primary_candidate_id: str = "legacy_corrected"
    primary_time_basis: str = "legacy_corrected"
    primary_midnight_rule: str = "sect1_23_changes_day"
    primary_input_datetime_to_lunar_python: str = ""
    primary_day_pillar_basis_datetime: str = ""
    legacy_corrected_solar_datetime: str = ""
    compare_candidates_enabled: bool = False


class TimeCorrectionSummary(BaseModel):
    tzid: str
    source_local_datetime: str
    normalized_local_datetime: str
    normalized_utc_datetime: str
    offset_minutes: int
    ambiguous: bool
    fold: int
    is_placeholder_time: bool = False
    placeholder_reason: Optional[str] = None


class RegionalSolarCorrectionSummary(BaseModel):
    source_solar_datetime: str
    corrected_solar_datetime: str
    longitude: float
    regional_time_offset_minutes: float
    daylight_saving_offset_minutes: int = 0
    correction_basis: str
    is_placeholder_time: bool = False
    placeholder_reason: Optional[str] = None


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
    is_placeholder_time: bool = False
    placeholder_reason: Optional[str] = None


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
    start_age_years: Optional[int] = None
    start_age_months: Optional[int] = None
    start_age_total_months: Optional[int] = None
    change_age_years: Optional[int] = None
    change_age_months: Optional[int] = None
    change_age_total_months: Optional[int] = None
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
    day_pillar_rule: str = ""
    day_time_basis_datetime: str = ""
    civil_date: str = ""
    day_pillar_basis_date: str = ""
    iljin_query_date: str = ""
    day_pillar_source: str = ""
    day_pillar_reference_matched_lunar_python: str = ""


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
    first_luck_cycle_start_age_years: Optional[int] = None
    first_luck_cycle_start_age_months: Optional[int] = None
    first_luck_cycle_start_age_total_months: Optional[int] = None
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
    free_preview: Optional[FreePreviewReport] = None
    limitations: List[str]
    disabled_sections: List[str]
    evidence_sections: Dict[str, EvidenceSection]
    calculation_basis: CalculationBasisSummary = Field(default_factory=CalculationBasisSummary)
    uncertainty_summary: List[UncertaintyFlagSummary] = Field(default_factory=list)
    hour_pillar_enabled: bool
    signals: SajuResultSignals


class DebugCheckpoint(BaseModel):
    stage: str
    status: PipelineState
    note: Optional[str] = None
    error_code: Optional[str] = None


class BirthTimeContextSummary(BaseModel):
    legal_local_datetime: str
    normalized_local_datetime: str
    normalized_utc_datetime: str
    timezone_id: str
    utc_offset_minutes: int
    dst_offset_minutes: int
    normalized_solar_datetime: str
    standard_local_datetime: str
    mean_solar_datetime: str
    legacy_corrected_solar_datetime: str
    corrected_solar_datetime: str
    longitude: float
    standard_meridian: float
    regional_time_offset_minutes: float
    daylight_saving_offset_minutes: int
    ambiguous: bool
    fold: int
    warnings: List[str] = Field(default_factory=list)


class CandidateChartDifferenceSummary(BaseModel):
    primary: Optional[str] = None
    candidate: Optional[str] = None


class CandidateChartSummary(BaseModel):
    candidate_id: str
    time_basis: str
    midnight_rule: str
    input_datetime_to_lunar_python: str
    day_pillar_basis_datetime: str = ""
    iljin_query_date: str = ""
    day_pillar_rule: str = ""
    year_pillar: str
    month_pillar: str
    day_pillar: str
    hour_pillar: str
    luck_cycle_start_age: Optional[int] = None
    luck_cycle_start_age_years: Optional[int] = None
    luck_cycle_start_age_months: Optional[int] = None
    luck_cycle_start_age_total_months: Optional[int] = None
    luck_cycle_first_ganzhi: Optional[str] = None
    differences_from_primary: Dict[str, CandidateChartDifferenceSummary]
    aliases: List[str] = Field(default_factory=list)


class DebugTrace(BaseModel):
    stage_order: List[str]
    failed_stage: Optional[str] = None
    checkpoints: List[DebugCheckpoint]
    request_echo: Dict[str, str]
    accuracy_mode: AccuracyMode = "legacy"
    calculation_basis: CalculationBasisSummary = Field(default_factory=CalculationBasisSummary)
    birth_time_context: Optional[BirthTimeContextSummary] = None
    year_month_boundary_context: Dict[str, object] = Field(default_factory=dict)
    candidate_charts: List[CandidateChartSummary] = Field(default_factory=list)
    uncertainty_flags: List[UncertaintyFlagSummary] = Field(default_factory=list)


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


class SajuFreeDetailResponse(BaseModel):
    trace_id: str
    response_mode: Literal["free_detail"] = "free_detail"
    pipeline_status: PipelineStatus
    interpretation: InterpretationReport
    detail_report: InterpretationReport
    debug_trace: Optional[DebugTrace] = None


class SajuDetailPrepareRequest(BaseModel):
    input: SajuPreviewRequest
    input_hash: Optional[str] = None
    detail_type: Optional[SajuDetailType] = None


class SajuDetailPrepareResponse(BaseModel):
    trace_id: str
    response_mode: Literal["detail_prepare"] = "detail_prepare"
    report_id: str
    input_hash: str
    cached: bool
    available_detail_types: List[SajuDetailType]
    bundle: SajuDetailPreparedReport


class SajuDetailRenderRequest(BaseModel):
    detail_type: SajuDetailType
    input: Optional[SajuPreviewRequest] = None
    input_hash: Optional[str] = None
    locale: Literal["ko", "en"] = "ko"


class SajuDetailRenderResponse(BaseModel):
    trace_id: str
    response_mode: Literal["detail_render"] = "detail_render"
    report_id: str
    input_hash: str
    detail_type: SajuDetailType
    provider: Literal["openai", "fallback"]
    model: Optional[str] = None
    prompt_version: str
    cached: bool
    report: SajuDetailRenderedReport
    warnings: List[str] = Field(default_factory=list)
