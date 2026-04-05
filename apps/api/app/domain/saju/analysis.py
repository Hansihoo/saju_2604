from dataclasses import dataclass
from typing import Dict, List, Literal


InternalGrade = Literal["S", "A", "B", "C"]


@dataclass
class AnalysisResult:
    visible_element_counts: Dict[str, int]
    dominant_elements: List[str]
    missing_elements: List[str]
    balance_score: int
    internal_grade: InternalGrade
    charm_score: int
    wealth_score: int
    career_score: int
    leadership_score: int
    summary: str
    strengths: List[str]
    cautions: List[str]
    action_advice: str
