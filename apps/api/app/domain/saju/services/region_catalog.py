from typing import Dict, List

from fastapi import HTTPException

from app.domain.saju.mock_data import LEGACY_REGION_ID_MAP, REGION_OPTIONS
from app.domain.saju.schemas import RegionSuggestion


def search_regions(*, query: str, limit: int) -> List[Dict[str, object]]:
    normalized = query.strip().lower()
    if not normalized:
        return []

    starts_with: List[Dict[str, object]] = []
    contains: List[Dict[str, object]] = []
    for region in REGION_OPTIONS:
        aliases = [alias.lower() for alias in region.get("aliases", [])]
        haystack = " ".join(
            [
                region["display_name"],
                region["country"],
                region["city"],
                region["tzid"],
                *region.get("aliases", []),
            ]
        ).lower()
        if (
            region["city"].lower().startswith(normalized)
            or region["display_name"].lower().startswith(normalized)
            or any(alias.startswith(normalized) for alias in aliases)
        ):
            starts_with.append(region)
        elif normalized in haystack:
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
