"""Versioned knowledge and reading contracts, independent of provider/UI schemas."""

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, constr


class StrictReadingModel(BaseModel):
    class Config:
        extra = "forbid"


ReadingRole = Literal["answer", "scene", "tradeoff", "action"]
ReadingFeature = Literal[
    "love.spouse_house_ten_god", "career.month_stem_ten_god",
    "core.dominant_element", "luck.current_stem_ten_god",
]


class KnowledgeSource(StrictReadingModel):
    id: str
    kind: Literal["project_policy"]
    reference: str
    expert_review: Literal["not_completed"]
    description: str


class RuleCopy(StrictReadingModel):
    question: str = Field(min_length=1, max_length=48)
    answer: str = Field(min_length=8, max_length=240)
    scene: str = Field(min_length=8, max_length=300)
    tradeoff: str = Field(min_length=8, max_length=300)
    action: str = Field(min_length=8, max_length=240)
    next_question: str = Field(min_length=1, max_length=160)
    analysis_note: str = Field(min_length=8, max_length=360)


class ReadingRule(StrictReadingModel):
    id: str
    version: int = Field(ge=1)
    source_id: str
    status: Literal["active_project_policy", "draft"]
    claim_scope: Literal["interpretation_only"]
    topic: Literal["core", "love", "work_money", "luck_flow"]
    feature: ReadingFeature
    any_of: List[str] = Field(min_items=1)
    exclusions: List[str]
    wording: Dict[str, RuleCopy]


class QuestionPolicy(StrictReadingModel):
    id: str
    topic: Literal["love", "career", "wealth", "comparison"]
    question: Dict[str, str]
    status: Literal["needs_rule_review", "needs_reference_population"]
    required_data: List[str] = Field(min_items=1)
    supported_scope: str
    forbidden_claims: List[str] = Field(min_items=1)


class KnowledgeBundle(StrictReadingModel):
    schema_version: Literal["saju-knowledge-v1"]
    knowledge_version: str
    format_version: Literal["question-reading-v1"]
    copy_version: str
    sources: List[KnowledgeSource] = Field(min_items=1)
    rules: List[ReadingRule] = Field(min_items=1)
    questions: List[QuestionPolicy] = Field(min_items=1)


class ReadingFact(StrictReadingModel):
    id: str
    value: str
    source_path: str


class ReadingBlock(StrictReadingModel):
    role: ReadingRole
    text: str = Field(min_length=8, max_length=300)
    kind: Literal["interpretation", "illustration", "advice"]
    fact_ids: List[str] = Field(min_items=1)
    rule_id: str


class ReadingAnalysisNote(StrictReadingModel):
    facts: List[constr(min_length=1, max_length=96)] = Field(min_items=1, max_items=3)
    reading: str = Field(min_length=1, max_length=360)


class ReadingStructure(StrictReadingModel):
    format_version: Literal["question-reading-v1"] = "question-reading-v1"
    knowledge_version: str
    copy_version: str
    provenance: Literal["server_project_policy"] = "server_project_policy"
    expert_review: Literal["not_completed"] = "not_completed"
    question: str
    source_id: str
    rule_id: str
    rule_version: int
    facts: List[ReadingFact] = Field(min_items=1)
    blocks: List[ReadingBlock] = Field(min_items=4, max_items=4)
    analysis_note: ReadingAnalysisNote


class QuestionCapability(StrictReadingModel):
    question_id: str
    question: str
    status: Literal["needs_rule_review", "needs_reference_population"]
    supported_scope: str
    missing_requirements: List[str]
    forbidden_claims: List[str]


class ReadingPlan(StrictReadingModel):
    format_version: Literal["question-reading-v1"] = "question-reading-v1"
    knowledge_version: str
    sections: Dict[str, ReadingStructure] = Field(default_factory=dict)
    question_capabilities: List[QuestionCapability] = Field(default_factory=list)
    unclassified_topics: List[str] = Field(default_factory=list)
