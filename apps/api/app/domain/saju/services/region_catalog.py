import re
import unicodedata
from typing import Dict, Iterable, List

from fastapi import HTTPException

from app.domain.saju.mock_data import LEGACY_REGION_ID_MAP, REGION_OPTIONS
from app.domain.saju.schemas import RegionSuggestion


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().lower()
    return re.sub(r"[\s,]+", "", normalized)


def _candidate_terms(region: Dict[str, object]) -> Iterable[str]:
    values = [
        str(region.get("display_name", "")),
        str(region.get("country", "")),
        str(region.get("city", "")),
        str(region.get("province", "")),
        *[str(alias) for alias in region.get("aliases", [])],
    ]
    for value in values:
        if value:
            yield _normalize_text(value)


def search_regions(*, query: str, limit: int) -> List[Dict[str, object]]:
    normalized = _normalize_text(query)
    if not normalized:
        return []

    starts_with: List[Dict[str, object]] = []
    contains: List[Dict[str, object]] = []
    for region in REGION_OPTIONS:
        terms = list(_candidate_terms(region))
        if any(term.startswith(normalized) for term in terms):
            starts_with.append(region)
        elif any(normalized in term for term in terms):
            contains.append(region)

    return (starts_with + contains)[:limit]


def find_region_by_id(region_id: str) -> RegionSuggestion:
    resolved_region_id = LEGACY_REGION_ID_MAP.get(region_id, region_id)
    for region in REGION_OPTIONS:
        if region["id"] == resolved_region_id:
            return RegionSuggestion(**region)

    raise HTTPException(
        status_code=400,
        detail={
            "stage": "region_resolution",
            "error_code": "REGION_NOT_SELECTED",
            "message": "A valid region must be selected from the suggestion list.",
        },
    )
