"""Versioned Korean lunar/solar reference table lookup."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


REFERENCE_DIR = Path(__file__).resolve().parent / "data" / "lunar_reference"
TABLE_ID = "kasi_lunar_calendar_1900_2050"
ROWS_PATH = REFERENCE_DIR / f"{TABLE_ID}.jsonl"
META_PATH = REFERENCE_DIR / f"{TABLE_ID}.meta.json"
LunarKey = Tuple[int, int, int, bool]


@dataclass(frozen=True)
class LunarReferenceRecord:
    solar_date: str
    solar_year: int
    solar_month: int
    solar_day: int
    lunar_date: str
    lunar_year: int
    lunar_month: int
    lunar_day: int
    is_lunar_leap_month: bool
    day_ganzhi_korean: str
    day_ganzhi_hanja: str
    julian_day: int


@dataclass(frozen=True)
class LunarReferenceTable:
    metadata: Dict[str, Any]
    by_solar_date: Dict[str, LunarReferenceRecord]
    by_lunar_date: Dict[LunarKey, LunarReferenceRecord]


def _record_from_dict(payload: Dict[str, Any]) -> LunarReferenceRecord:
    return LunarReferenceRecord(
        solar_date=payload["solar_date"],
        solar_year=int(payload["solar_year"]),
        solar_month=int(payload["solar_month"]),
        solar_day=int(payload["solar_day"]),
        lunar_date=payload["lunar_date"],
        lunar_year=int(payload["lunar_year"]),
        lunar_month=int(payload["lunar_month"]),
        lunar_day=int(payload["lunar_day"]),
        is_lunar_leap_month=bool(payload["is_lunar_leap_month"]),
        day_ganzhi_korean=payload["day_ganzhi_korean"],
        day_ganzhi_hanja=payload["day_ganzhi_hanja"],
        julian_day=int(payload["julian_day"]),
    )


def _lunar_key(record: LunarReferenceRecord) -> LunarKey:
    return (
        record.lunar_year,
        record.lunar_month,
        record.lunar_day,
        record.is_lunar_leap_month,
    )


def _validate_rows_hash(metadata: Dict[str, Any], rows_bytes: bytes) -> None:
    expected_hash = metadata.get("rows_sha256")
    actual_hash = hashlib.sha256(rows_bytes).hexdigest()
    if actual_hash != expected_hash:
        raise ValueError(
            f"Lunar reference table hash mismatch: expected {expected_hash}, got {actual_hash}"
        )


@lru_cache(maxsize=1)
def load_lunar_reference_table() -> LunarReferenceTable:
    metadata = json.loads(META_PATH.read_text(encoding="utf-8"))
    rows_bytes = ROWS_PATH.read_bytes()
    _validate_rows_hash(metadata, rows_bytes)

    by_solar_date: Dict[str, LunarReferenceRecord] = {}
    by_lunar_date: Dict[LunarKey, LunarReferenceRecord] = {}
    for line in rows_bytes.splitlines():
        record = _record_from_dict(json.loads(line.decode("utf-8")))
        by_solar_date[record.solar_date] = record
        by_lunar_date[_lunar_key(record)] = record

    row_count = int(metadata["row_count"])
    if len(by_solar_date) != row_count or len(by_lunar_date) != row_count:
        raise ValueError(
            "Lunar reference table contains duplicate or missing solar/lunar keys."
        )

    return LunarReferenceTable(
        metadata=metadata,
        by_solar_date=by_solar_date,
        by_lunar_date=by_lunar_date,
    )


def lookup_lunar_reference_by_solar_date(solar_date: date) -> Optional[LunarReferenceRecord]:
    table = load_lunar_reference_table()
    return table.by_solar_date.get(solar_date.isoformat())


def lookup_lunar_reference_by_lunar_date(
    *,
    lunar_year: int,
    lunar_month: int,
    lunar_day: int,
    is_lunar_leap_month: bool,
) -> Optional[LunarReferenceRecord]:
    table = load_lunar_reference_table()
    return table.by_lunar_date.get(
        (
            lunar_year,
            lunar_month,
            lunar_day,
            is_lunar_leap_month,
        )
    )


def get_lunar_reference_metadata() -> Dict[str, Any]:
    return dict(load_lunar_reference_table().metadata)
