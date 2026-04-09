from typing import Dict, List, Literal, Optional

from pydantic import BaseModel

from app.domain.saju.analysis import InternalGrade
from app.domain.saju.schemas import ElementKey


OutputSection = Literal[
    "summary",
    "strengths",
    "cautions",
    "love",
    "career",
    "wealth",
    "action_advice",
]


class InterpretationInputProfile(BaseModel):
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


class InterpretationVisiblePillar(BaseModel):
    key: Literal["year", "month", "day", "time"]
    label: str
    gan_zhi: str
    stem: str
    branch: str


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


class InterpretationLuckCycle(BaseModel):
    start_age: int
    end_age: int
    start_year: int
    end_year: int
    gan_zhi: str


class InterpretationSupplementaryPosition(BaseModel):
    key: str
    label: str
    gan_zhi: str


class InterpretationPayload(BaseModel):
    schema_version: Literal["m2-preview-v1"] = "m2-preview-v1"
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
    luck_cycles: List[InterpretationLuckCycle]
    supplementary_positions: List[InterpretationSupplementaryPosition]
    limitations: List[str]
    disabled_sections: List[str]
    notes: List[str]
    narrative_rules: List[str]
    prompt_seed: Optional[str] = None
