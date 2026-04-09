from __future__ import annotations

from functools import lru_cache
from typing import Dict, Tuple

from app.domain.saju.mock_data import LEGACY_REGION_ID_MAP, REGION_OPTIONS
from app.domain.saju.region_model import RegionRecord


@lru_cache(maxsize=1)
def load_region_records() -> Tuple[RegionRecord, ...]:
    return tuple(RegionRecord.from_mapping(option) for option in REGION_OPTIONS)


@lru_cache(maxsize=1)
def load_region_payloads() -> Tuple[Dict[str, object], ...]:
    return tuple(region.to_public_dict() for region in load_region_records())


@lru_cache(maxsize=1)
def load_region_index() -> Dict[str, RegionRecord]:
    return {region.id: region for region in load_region_records()}


def resolve_region_id(region_id: str) -> str:
    return LEGACY_REGION_ID_MAP.get(region_id, region_id)


def get_region_by_id(region_id: str) -> RegionRecord | None:
    resolved_region_id = resolve_region_id(region_id)
    return load_region_index().get(resolved_region_id)
