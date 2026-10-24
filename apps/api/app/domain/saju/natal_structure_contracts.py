"""Bounded natal structure, independently versioned from stars and LLM copy."""
from typing import Any, Dict, List, Literal
from pydantic import BaseModel, Field


class NatalStructureVersions(BaseModel):
    knowledge: str = "natal-structure-knowledge-2026-10-10.1"
    rules: str = "natal-structure-rules-2026-10-10.1"
    copy_version: str = Field(default="natal-structure-copy-2026-10-23.1", alias="copy")
    selection: str = "natal-conclusion-selection-2026-10-11.1"
    format: str = "natal-structure-v1"


class NatalStructureBlock(BaseModel):
    id: str
    title: str
    text: str
    rule_ids: List[str]
    fact_ids: List[str]


class NatalConclusion(BaseModel):
    id: str
    title: str
    text: str
    one_line: str = ""
    category: Literal["core"] = "core"
    source_block_ids: List[str]
    rule_ids: List[str]
    fact_ids: List[str]
    conditions: Dict[str, Any]
    scope: Literal["bounded_natal_relations"] = "bounded_natal_relations"


class NatalStructureReading(BaseModel):
    status: Literal["available", "conditional", "blocked_calculation"] = "blocked_calculation"
    scope: str = "bounded_natal_relations_not_global_verdict"
    assumption: str = ""
    versions: NatalStructureVersions = Field(default_factory=NatalStructureVersions)
    facts: List[Dict[str, Any]] = Field(default_factory=list)
    profile: Dict[str, Any] = Field(default_factory=dict)
    blocks: List[NatalStructureBlock] = Field(default_factory=list)
    conclusions: List[NatalConclusion] = Field(default_factory=list)
    memo_body: str = ""
    comparisons: List[Dict[str, Any]] = Field(default_factory=list)
    blocked_reasons: List[str] = Field(default_factory=list)
    expert_review: Literal["not_completed"] = "not_completed"
    final_strength_supported: Literal[False] = False
    useful_element_supported: Literal[False] = False
    event_timing_supported: Literal[False] = False
    whole_chart_synthesis_supported: Literal[False] = False
