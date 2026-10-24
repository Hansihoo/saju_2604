"""Additive contracts for basic facts and one explicitly supported question."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.domain.saju.interpretation import ReadingBasisExplanation
from app.domain.saju.schemas import SajuPreviewRequest, SajuPreviewResponse
from app.domain.saju.reading_information_contracts import ReadingInformation, ReadingInformationItem
from app.domain.saju.chart_characteristics import ChartCharacteristics
from app.domain.saju.distinctive_contracts import DistinctiveReading
from app.domain.saju.natal_structure_contracts import NatalStructureReading


QuestionId = Literal["chart.pillars", "luck.current_next", "period.this_year", "stars.dohwa", "wealth.locations",
                     "features.taegeuk", "features.study_solitude", "features.dohwa"]
ReadingCategory = Literal["core", "love", "wealth", "career", "luck_flow"]


class QuestionVersions(BaseModel):
    facts: str = "question-facts-2026-10-09.1"
    knowledge: str = "question-knowledge-2026-10-09.1"
    rules: str = "question-rules-2026-10-10.2"
    copy_version: str = Field(default="question-copy-2026-10-10.5", alias="copy")
    format: str = "basic-question-reading-v3"


class QuestionOption(BaseModel):
    id: QuestionId
    category: ReadingCategory
    title: str
    description: str
    requires_context: bool = False
    context_options: List[Dict[str, str]] = Field(default_factory=list)


class QuestionFlow(BaseModel):
    versions: QuestionVersions = Field(default_factory=QuestionVersions)
    as_of: str
    questions: List[QuestionOption]
    notices: List[str] = Field(default_factory=list)


class SajuQuestionRequest(BaseModel):
    input: SajuPreviewRequest
    question_id: QuestionId
    context: None = None

    class Config:
        extra = "forbid"


class QuestionFact(BaseModel):
    id: str
    label: str
    value: Any
    source_path: str


class QuestionSection(BaseModel):
    id: str
    title: str
    text: str
    kind: Literal["reading", "memo"] = "memo"


class BasicReadingVersions(BaseModel):
    facts: str = "basic-reading-facts-2026-10-08.2"
    knowledge: str = "basic-reading-knowledge-2026-10-08.2"
    copy_version: str = Field(default="basic-reading-copy-2026-10-08.7", alias="copy")
    format: str = "basic-overview-v2"


class BasicReadingSection(BaseModel):
    id: str
    title: str
    text: str
    fact_ids: List[str]


class BasicReading(BaseModel):
    as_of: str
    title: str
    headline: str
    sections: List[BasicReadingSection]
    memo_sections: List[BasicReadingSection] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    memo: ReadingBasisExplanation
    notices: List[str]
    facts: List[QuestionFact]
    source_context: Dict[str, Any]
    versions: BasicReadingVersions = Field(default_factory=BasicReadingVersions)
    provider: Literal["deterministic"] = "deterministic"


class SajuBasicResponse(SajuPreviewResponse):
    question_flow: QuestionFlow
    basic_reading: BasicReading


class PublishedReadingBlock(BaseModel):
    id: str
    kind: Literal["interpretation", "structural_reading", "traditional_definition", "traditional_theme", "calculation_summary", "heading", "availability_notice"]
    text: str
    title: str = ""


class PublishedChapter(BaseModel):
    version: str
    scope: Literal["natal_structure", "conditional_natal_structure", "supported_reading_excerpt", "conditional_traditional_themes", "traditional_themes", "provisional_information", "calculation_information", "traditional_information", "unavailable"]
    blocks: List[PublishedReadingBlock]
    memo_body: str
    notice: str = ""


class CategoryReadingSection(BaseModel):
    id: ReadingCategory
    title: str
    body: str
    memo_body: str
    status: Literal["existing_interpretation", "blocked_calculation", "needs_rule_review"]
    information: List[ReadingInformationItem] = Field(default_factory=list)
    visible: bool = True
    publication: Optional[PublishedChapter] = None


class CategoryReading(BaseModel):
    sections: List[CategoryReadingSection]
    provider: Literal["openai", "codex", "fallback", "deterministic"]
    format: str = "category-reading-v1"
    copy_version: str = "category-reading-copy-2026-10-24.1"
    reading_information: ReadingInformation = Field(default_factory=ReadingInformation)
    characteristics: Optional[ChartCharacteristics] = None
    distinctive_reading: Optional[DistinctiveReading] = None
    natal_structure: Optional[NatalStructureReading] = None
    source_context: Dict[str, Any]
    calculation_notices: List[str] = Field(default_factory=list)
    notices: List[str] = Field(default_factory=list)


class SajuCategoryResponse(SajuBasicResponse):
    category_reading: CategoryReading


class SajuQuestionResponse(BaseModel):
    trace_id: str
    as_of: str
    response_mode: Literal["question"] = "question"
    question_id: QuestionId
    question: str
    title: str
    answer: str
    sections: List[QuestionSection]
    memo: ReadingBasisExplanation
    notices: List[str]
    facts: List[QuestionFact]
    versions: QuestionVersions = Field(default_factory=QuestionVersions)
    provider: Literal["deterministic"] = "deterministic"
    cached: bool = False
    followups: List[QuestionOption] = Field(default_factory=list)
    source_context: Dict[str, Any] = Field(default_factory=dict)
