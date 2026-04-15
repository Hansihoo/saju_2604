"""이 파일은 지역 검색과 선택 검증 로직을 제공한다."""

import re
import unicodedata
from typing import Dict, Iterable, List

from fastapi import HTTPException

from app.domain.saju.region_model import RegionRecord
from app.domain.saju.region_repository import get_region_by_id, load_region_records
from app.domain.saju.schemas import RegionSuggestion


def _normalize_text(value: str) -> str:
    """텍스트를 정규화한다."""
    normalized = unicodedata.normalize("NFKC", value).strip().lower()
    return re.sub(r"[\s,]+", "", normalized)


def _candidate_terms(region: RegionRecord) -> Iterable[str]:
    """terms 관련 값을 반환하거나 처리한다."""
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
    """검색어에 맞는 지역 후보를 찾아 반환한다."""
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
    """선택된 region_id를 검증하고 해당 지역 모델을 반환한다."""
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
