import re
import unicodedata
from typing import Dict, Iterable, List

from fastapi import HTTPException

from app.domain.saju.region_model import RegionRecord
from app.domain.saju.region_repository import get_region_by_id, load_region_records
from app.domain.saju.schemas import RegionSuggestion


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().lower()
    return re.sub(r"[\s,]+", "", normalized)


def _candidate_terms(region: RegionRecord) -> Iterable[str]:
    values = [
        region.display_name,
        region.country,
        region.city,
        region.province,
        *region.aliases,
    ]
    for value in values:
        if value:
            yield _normalize_text(value)


def search_regions(*, query: str, limit: int) -> List[Dict[str, object]]:
    normalized = _normalize_text(query)
    if not normalized:
        return []

    starts_with: List[RegionRecord] = []
    contains: List[RegionRecord] = []
    for region in load_region_records():
        terms = list(_candidate_terms(region))
        if any(term.startswith(normalized) for term in terms):
            starts_with.append(region)
        elif any(normalized in term for term in terms):
            contains.append(region)

    return [region.to_public_dict() for region in (starts_with + contains)[:limit]]


def find_region_by_id(region_id: str) -> RegionSuggestion:
    region = get_region_by_id(region_id)
    if region is not None:
        return RegionSuggestion(**region.to_public_dict())

    raise HTTPException(
        status_code=400,
        detail={
            "stage": "region_resolution",
            "error_code": "REGION_NOT_SELECTED",
            "message": "A valid region must be selected from the suggestion list.",
        },
    )
