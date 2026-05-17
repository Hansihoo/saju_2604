"""Structured payload models passed from the engine to the interpretation layer."""

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.domain.saju.analysis import InternalGrade
from app.domain.saju.localization import OutputLocale
from app.domain.saju.schemas import ElementKey


OutputSection = Literal[
    "core_analysis",
    "love",
    "wealth",
    "career",
    "luck_flow",
]


class InterpretationInputProfile(BaseModel):
    locale: OutputLocale = "ko"
    calendar_type: Literal["solar", "lunar"]
    birth_date: str
    birth_time: str
    is_birth_time_estimated: bool
    is_lunar_leap_month: bool
    gender: Literal["male", "female"]
    region_id: str
    region_display_name: str
    tzid: str


class InterpretationTimeContext(BaseModel):
    normalized_local_datetime: str
    normalized_utc_datetime: str
    corrected_solar_datetime: str
    regional_time_offset_minutes: float
    daylight_saving_offset_minutes: int
    correction_basis: str
    accuracy_mode: str = "legacy"
    primary_time_basis: str = "legacy_corrected"
    primary_input_datetime_to_lunar_python: str = ""
    primary_midnight_rule: str = "sect1_23_changes_day"


class InterpretationVisiblePillar(BaseModel):
    key: Literal["year", "month", "day", "time"]
    label: str
    gan_zhi: str
    stem: str
    branch: str
    display_label: str
    display_gan_zhi: str
    display_stem: str
    display_branch: str


class InterpretationSignalBlock(BaseModel):
    internal_grade: InternalGrade
    balance_score: int
    charm_score: int
    wealth_score: int
    career_score: int
    leadership_score: int
    dominant_elements: List[ElementKey]
    missing_elements: List[ElementKey]


class InterpretationEvidenceItem(BaseModel):
    key: str
    title: str
    status: Literal["ready", "disabled", "coming_soon"]
    summary: str


class InterpretationUncertaintyFlag(BaseModel):
    code: str
    severity: Literal["warning", "critical"]
    affected_fields: List[str]
    user_message: str


class InterpretationLuckCycle(BaseModel):
    start_age: int
    end_age: int
    start_year: int
    end_year: int
    gan_zhi: str
    display_gan_zhi: str
    start_age_years: Optional[int] = None
    start_age_months: Optional[int] = None
    start_age_total_months: Optional[int] = None
    change_age_years: Optional[int] = None
    change_age_months: Optional[int] = None
    change_age_total_months: Optional[int] = None
    start_datetime: Optional[str] = None
    change_datetime: Optional[str] = None


class InterpretationCountMetric(BaseModel):
    key: str
    label: str
    count: int


class InterpretationCurrentFlowContext(BaseModel):
    current_year: int
    current_age: int
    active_luck_cycle: Optional[InterpretationLuckCycle] = None
    next_luck_cycle: Optional[InterpretationLuckCycle] = None


class InterpretationLuckCycleAnalysis(BaseModel):
    display_gan_zhi: str
    start_year: int
    end_year: int
    start_age: int
    end_age: int
    period: str
    phase: str
    phase_label: str
    overall_tone: str
    cycle_rank: int
    overall_favorability: str
    confidence: str
    stem_ten_god: str
    branch_element: Optional[ElementKey] = None
    favorable_domains: List[str] = Field(default_factory=list)
    caution_domains: List[str] = Field(default_factory=list)
    good_for: List[str] = Field(default_factory=list)
    watch_out: List[str] = Field(default_factory=list)
    reason_tags: List[str] = Field(default_factory=list)
    caution_tags: List[str] = Field(default_factory=list)
    love_impact: str = "medium"
    career_impact: str = "medium"
    wealth_impact: str = "medium"
    relationship_impact: str = "medium"
    summary: str


class InterpretationFavorablePeriod(BaseModel):
    period: str
    luck_cycle: str
    favorable_for: List[str] = Field(default_factory=list)
    reason_tags: List[str] = Field(default_factory=list)
    caution_tags: List[str] = Field(default_factory=list)
    confidence: str = "medium"


class InterpretationLuckFlowFacts(BaseModel):
    current_phase: str = ""
    current_phase_label: str = ""
    current_luck_cycle: str = ""
    current_period: str = ""
    next_luck_cycle: str = ""
    next_period: str = ""
    next_phase: str = ""
    next_phase_label: str = ""
    favorable_periods: List[InterpretationFavorablePeriod] = Field(default_factory=list)
    transition_summary: str = ""
    now_action_tags: List[str] = Field(default_factory=list)


class InterpretationLoveFacts(BaseModel):
    score: int
    spouse_house_label: str
    spouse_house_branch: str
    spouse_house_ten_god: str
    partner_star_label: str
    partner_star_count: int
    active_star_labels: List[str]


class InterpretationCareerFacts(BaseModel):
    score: int
    month_pillar_label: str
    month_pillar_gan_zhi: str
    month_stem_ten_god: str
    key_ten_gods: List[InterpretationCountMetric]
    active_star_labels: List[str]


class InterpretationWealthFacts(BaseModel):
    score: int
    key_ten_gods: List[InterpretationCountMetric]
    active_star_labels: List[str]
    missing_elements: List[str]


class InterpretationSupplementaryPosition(BaseModel):
    key: str
    label: str
    gan_zhi: str
    display_label: str
    display_gan_zhi: str


class InterpretationSpecialStar(BaseModel):
    key: str
    label: str
    tier: Literal["S", "A", "B"]
    category: Literal["auspicious", "sinsal"]
    usage_summary: str
    matched_pillars: List[Literal["year", "month", "day", "time"]]
    evidence_id: str
    display_label: str


class InterpretationPayload(BaseModel):
    schema_version: Literal["m2-preview-v2"] = "m2-preview-v2"
    facts_only: bool = True
    output_sections: List[OutputSection]
    profile: InterpretationInputProfile
    time_context: InterpretationTimeContext
    visible_pillars: List[InterpretationVisiblePillar]
    day_master: str
    element_counts: Dict[ElementKey, int]
    ten_god_stems: Dict[str, str]
    signals: InterpretationSignalBlock
    evidence: List[InterpretationEvidenceItem]
    uncertainty_summary: List[InterpretationUncertaintyFlag] = Field(default_factory=list)
    luck_cycles: List[InterpretationLuckCycle]
    current_flow: InterpretationCurrentFlowContext
    luck_cycle_analysis: List[InterpretationLuckCycleAnalysis] = Field(default_factory=list)
    luck_flow_facts: InterpretationLuckFlowFacts = Field(default_factory=InterpretationLuckFlowFacts)
    love_facts: InterpretationLoveFacts
    career_facts: InterpretationCareerFacts
    wealth_facts: InterpretationWealthFacts
    supplementary_positions: List[InterpretationSupplementaryPosition]
    special_stars: List[InterpretationSpecialStar]
    limitations: List[str]
    disabled_sections: List[str]
    notes: List[str]
    narrative_rules: List[str]
    prompt_seed: Optional[str] = None
