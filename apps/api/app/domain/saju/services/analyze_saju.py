from typing import Dict, List

from app.domain.saju.analysis import AnalysisResult
from app.domain.saju.engine import SajuCalculationResult


ELEMENT_KEY_BY_CHAR = {
    "\u6728": "wood",
    "\u706b": "fire",
    "\u571f": "earth",
    "\u91d1": "metal",
    "\u6c34": "water",
}

ELEMENT_LABELS = {
    "wood": "Wood",
    "fire": "Fire",
    "earth": "Earth",
    "metal": "Metal",
    "water": "Water",
}


def _clamp_score(value: int) -> int:
    return max(0, min(100, value))


def _count_visible_elements(
    saju_calculation: SajuCalculationResult,
    visible_pillar_keys: List[str],
) -> Dict[str, int]:
    counts = {key: 0 for key in ELEMENT_LABELS.keys()}
    for pillar_key in visible_pillar_keys:
        for char in saju_calculation.pillars[pillar_key].five_elements:
            if char in ELEMENT_KEY_BY_CHAR:
                counts[ELEMENT_KEY_BY_CHAR[char]] += 1
    return counts


def analyze_saju(
    *,
    saju_calculation: SajuCalculationResult,
    visible_pillar_keys: List[str],
) -> AnalysisResult:
    counts = _count_visible_elements(
        saju_calculation=saju_calculation,
        visible_pillar_keys=visible_pillar_keys,
    )
    max_count = max(counts.values())
    min_count = min(counts.values())
    imbalance_gap = max_count - min_count
    visible_element_total = sum(counts.values())
    element_percentages = {
        key: round((value / visible_element_total) * 100, 1) if visible_element_total else 0.0
        for key, value in counts.items()
    }
    missing_elements = [key for key, value in counts.items() if value == 0]
    dominant_elements = [key for key, value in counts.items() if value == max_count and value > 0]
    balance_score = _clamp_score(100 - (imbalance_gap * 15) - (len(missing_elements) * 10))

    if len(missing_elements) == 0 and imbalance_gap <= 1:
        internal_grade = "S"
    elif len(missing_elements) <= 1 and imbalance_gap <= 2:
        internal_grade = "A"
    elif len(missing_elements) <= 2 and imbalance_gap <= 3:
        internal_grade = "B"
    else:
        internal_grade = "C"

    charm_score = _clamp_score(45 + (counts["fire"] * 8) + (counts["water"] * 5) - (counts["earth"] * 3))
    wealth_score = _clamp_score(45 + (counts["earth"] * 7) + (counts["metal"] * 6) - (len(missing_elements) * 3))
    career_score = _clamp_score(45 + (counts["wood"] * 7) + (counts["earth"] * 4) + (counts["metal"] * 3))
    leadership_score = _clamp_score(45 + (counts["fire"] * 6) + (counts["metal"] * 6) + (counts["wood"] * 4))

    dominant_labels = ", ".join(ELEMENT_LABELS[key] for key in dominant_elements) or "none"
    missing_labels = ", ".join(ELEMENT_LABELS[key] for key in missing_elements) or "none"

    strengths = [
        f"Dominant visible elements: {dominant_labels}.",
        f"Visible balance score: {balance_score}/100.",
    ]
    cautions = []
    if missing_elements:
        cautions.append(f"Missing visible elements: {missing_labels}.")
    if imbalance_gap >= 3:
        cautions.append("The visible element spread is wide, so balance-sensitive interpretations should stay conservative.")
    if not cautions:
        cautions.append("No major visible imbalance was detected in the current baseline rules.")

    return AnalysisResult(
        visible_element_counts=counts,
        visible_element_total=visible_element_total,
        element_percentages=element_percentages,
        imbalance_gap=imbalance_gap,
        dominant_elements=dominant_elements,
        missing_elements=missing_elements,
        balance_score=balance_score,
        internal_grade=internal_grade,
        charm_score=charm_score,
        wealth_score=wealth_score,
        career_score=career_score,
        leadership_score=leadership_score,
        summary=(
            f"Visible element balance is led by {dominant_labels}, "
            f"with missing elements {missing_labels} and an internal grade of {internal_grade}."
        ),
        strengths=strengths,
        cautions=cautions,
        action_advice=(
            "Use the visible balance and score profile as a code-driven baseline, then refine the narrative layer only after the scoring rules are reviewed."
        ),
    )
