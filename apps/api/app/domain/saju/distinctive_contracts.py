"""Versioned, bounded natal themes; separate from the legacy full report."""
from typing import Any, Dict, List, Literal
from pydantic import BaseModel, Field


class DistinctiveVersions(BaseModel):
    knowledge: str = "distinctive-knowledge-2026-10-09.1"
    rules: str = "distinctive-rules-2026-10-09.2"
    copy_version: str = Field(default="distinctive-copy-2026-10-24.1", alias="copy")
    format: str = "distinctive-reading-v1"


class DistinctiveTheme(BaseModel):
    id: str
    category: Literal["core", "love"]
    title: str
    body: str
    memo_body: str
    fact_ids: List[str]
    eligible_matches: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    rule_id: str
    direction: Literal["mixed"] = "mixed"
    degree: Literal["bounded_theme_not_global_magnitude"] = "bounded_theme_not_global_magnitude"
    question_ids: List[str] = Field(default_factory=list)


class DistinctiveReading(BaseModel):
    status: Literal["available", "conditional", "blocked_calculation", "no_matching_rules"]
    scope: str = "project_traditional_symbol_themes"
    assumption: str = ""
    themes: List[DistinctiveTheme] = Field(default_factory=list)
    facts: List[Dict[str, Any]] = Field(default_factory=list)
    comparisons: List[Dict[str, Any]] = Field(default_factory=list)
    blocked_reasons: List[str] = Field(default_factory=list)
    versions: DistinctiveVersions = Field(default_factory=DistinctiveVersions)
    expert_review: Literal["not_completed"] = "not_completed"
