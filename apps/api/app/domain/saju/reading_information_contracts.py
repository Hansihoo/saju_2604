"""Independent calculation descriptions and traditional glossary, not predictions."""
from typing import Any, Dict, List, Literal
from pydantic import BaseModel, Field


class ReadingInformationFact(BaseModel):
    id: str
    value: Any
    source_path: str


class ReadingInformationItem(BaseModel):
    id: str
    category: Literal["core", "love", "wealth", "career", "luck_flow"]
    title: str
    body: str
    memo_body: str
    kind: Literal["calculation_description", "traditional_term_definition"]
    fact_ids: List[str]
    provisional: bool = False
    star_keys: List[str] = Field(default_factory=list)
    methods: List[str] = Field(default_factory=list)
    matched_pillars: List[str] = Field(default_factory=list)


class ReadingInformationVersions(BaseModel):
    facts: str = "reading-information-facts-2026-10-09.1"
    knowledge: str = "present-signals-knowledge-2026-10-09.2"
    rules: str = "reading-information-rules-2026-10-11.1"
    copy_version: str = Field(default="reading-information-copy-2026-10-11.1", alias="copy")
    format: str = "reading-information-v1"


class ReadingInformation(BaseModel):
    items: List[ReadingInformationItem] = Field(default_factory=list)
    facts: List[ReadingInformationFact] = Field(default_factory=list)
    versions: ReadingInformationVersions = Field(default_factory=ReadingInformationVersions)
    derivations: List[Dict[str, Any]] = Field(default_factory=list)
    scope: Literal["calculation_and_glossary"] = "calculation_and_glossary"
    interpretation_withheld: bool = False
    expert_review: Literal["not_completed"] = "not_completed"
