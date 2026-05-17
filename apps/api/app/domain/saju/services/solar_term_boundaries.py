"""Solar-term boundary lookup with verified-reference and Skyfield fallback.

Verified reference rows are preferred when available. Skyfield provides an
independent ephemeris-based boundary for years/timezones where checked-in
reference rows are unavailable. The previous lunar_python lookup remains as a
last-resort fallback.
"""

from __future__ import annotations

import os
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional, Sequence

from lunar_python import Solar

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python 3.8 fallback
    from backports.zoneinfo import ZoneInfo


REFERENCE_TABLE_ID = "solar_terms_extended_1946_2027"
REFERENCE_DIR = Path(__file__).resolve().parents[1] / "data" / "solar_terms_reference"
REFERENCE_ROWS_PATH = REFERENCE_DIR / f"{REFERENCE_TABLE_ID}.jsonl"
REFERENCE_META_PATH = REFERENCE_DIR / f"{REFERENCE_TABLE_ID}.meta.json"
REFERENCE_TIMEZONE_ID = "Asia/Seoul"
VERIFIED_SOURCE_ROLE = "official_reference_table"
SKYFIELD_EPHEMERIS = "de440s.bsp"
SKYFIELD_EPHEMERIS_SIZE_BYTES = 32_726_016
SKYFIELD_EPHEMERIS_SHA256 = "c1c7feeab882263fc493a9d5a5b2ddd71b54826cdf65d8d17a76126b260a49f2"
SKYFIELD_CACHE_ENV = "SAJU_SKYFIELD_DATA_DIR"
SKYFIELD_SEARCH_DAYS = 45
SKYFIELD_PROVIDER_APIS = [
    "skyfield.almanac_east_asia.solar_terms",
    "skyfield.almanac.find_discrete",
]
JIE_TERM_TYPE = "jeolgi"
SkyfieldTermDirection = Literal["forward", "backward"]
JIE_TERM_IDS = {
    "ipchun",
    "gyeongchip",
    "cheongmyeong",
    "ipha",
    "mangjong",
    "soseo",
    "ipchu",
    "baengno",
    "hallo",
    "ipdong",
    "daeseol",
    "sohan",
}
JIE_TERM_IDS_IN_MONTH_ORDER = (
    "ipchun",
    "gyeongchip",
    "cheongmyeong",
    "ipha",
    "mangjong",
    "soseo",
    "ipchu",
    "baengno",
    "hallo",
    "ipdong",
    "daeseol",
    "sohan",
)
JIE_TERM_APPROX_DATES = {
    "sohan": (1, 6),
    "ipchun": (2, 4),
    "gyeongchip": (3, 6),
    "cheongmyeong": (4, 5),
    "ipha": (5, 6),
    "mangjong": (6, 6),
    "soseo": (7, 7),
    "ipchu": (8, 8),
    "baengno": (9, 8),
    "hallo": (10, 8),
    "ipdong": (11, 7),
    "daeseol": (12, 7),
}
TERM_ID_BY_LUNAR_PYTHON_NAME = {
    "\u7acb\u6625": "ipchun",
    "\u60ca\u86f0": "gyeongchip",
    "\u6e05\u660e": "cheongmyeong",
    "\u7acb\u590f": "ipha",
    "\u8292\u79cd": "mangjong",
    "\u5c0f\u6691": "soseo",
    "\u7acb\u79cb": "ipchu",
    "\u767d\u9732": "baengno",
    "\u5bd2\u9732": "hallo",
    "\u7acb\u51ac": "ipdong",
    "\u5927\u96ea": "daeseol",
    "\u5c0f\u5bd2": "sohan",
}


SKYFIELD_TERM_DEFINITIONS: Dict[int, Dict[str, str]] = {
    0: {"term_id": "chunbun", "term_name": "\u6625\u5206", "term_type": "junggi"},
    1: {"term_id": "cheongmyeong", "term_name": "\u6e05\u660e", "term_type": JIE_TERM_TYPE},
    2: {"term_id": "gogu", "term_name": "\u7a40\u96e8", "term_type": "junggi"},
    3: {"term_id": "ipha", "term_name": "\u7acb\u590f", "term_type": JIE_TERM_TYPE},
    4: {"term_id": "soman", "term_name": "\u5c0f\u6eff", "term_type": "junggi"},
    5: {"term_id": "mangjong", "term_name": "\u8292\u7a2e", "term_type": JIE_TERM_TYPE},
    6: {"term_id": "haji", "term_name": "\u590f\u81f3", "term_type": "junggi"},
    7: {"term_id": "soseo", "term_name": "\u5c0f\u6691", "term_type": JIE_TERM_TYPE},
    8: {"term_id": "daeseo", "term_name": "\u5927\u6691", "term_type": "junggi"},
    9: {"term_id": "ipchu", "term_name": "\u7acb\u79cb", "term_type": JIE_TERM_TYPE},
    10: {"term_id": "cheoseo", "term_name": "\u8655\u6691", "term_type": "junggi"},
    11: {"term_id": "baengno", "term_name": "\u767d\u9732", "term_type": JIE_TERM_TYPE},
    12: {"term_id": "chubun", "term_name": "\u79cb\u5206", "term_type": "junggi"},
    13: {"term_id": "hallo", "term_name": "\u5bd2\u9732", "term_type": JIE_TERM_TYPE},
    14: {"term_id": "sanggang", "term_name": "\u971c\u964d", "term_type": "junggi"},
    15: {"term_id": "ipdong", "term_name": "\u7acb\u51ac", "term_type": JIE_TERM_TYPE},
    16: {"term_id": "soseol", "term_name": "\u5c0f\u96ea", "term_type": "junggi"},
    17: {"term_id": "daeseol", "term_name": "\u5927\u96ea", "term_type": JIE_TERM_TYPE},
    18: {"term_id": "dongji", "term_name": "\u51ac\u81f3", "term_type": "junggi"},
    19: {"term_id": "sohan", "term_name": "\u5c0f\u5bd2", "term_type": JIE_TERM_TYPE},
    20: {"term_id": "daehan", "term_name": "\u5927\u5bd2", "term_type": "junggi"},
    21: {"term_id": "ipchun", "term_name": "\u7acb\u6625", "term_type": JIE_TERM_TYPE},
    22: {"term_id": "usu", "term_name": "\u96e8\u6c34", "term_type": "junggi"},
    23: {"term_id": "gyeongchip", "term_name": "\u9a5a\u87c4", "term_type": JIE_TERM_TYPE},
}


@dataclass(frozen=True)
class SolarTermBoundary:
    name: str
    datetime_text: str
    delta_seconds: int
    relation: str
    is_jie: bool
    is_qi: bool
    provider: str
    provider_apis: Sequence[str]
    used_reference: bool
    fallback_reason: Optional[str] = None
    reference: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _ReferenceRow:
    year: int
    term_id: str
    term_name: str
    term_type: str
    solar_term_datetime: str
    source_role: str
    source: Dict[str, Any]

    @property
    def datetime_value(self) -> datetime:
        return datetime.fromisoformat(self.solar_term_datetime).replace(tzinfo=None)


def _parse_input_datetime(value: str) -> Optional[datetime]:
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _solar_to_datetime_text(solar) -> str:
    return datetime(
        solar.getYear(),
        solar.getMonth(),
        solar.getDay(),
        solar.getHour(),
        solar.getMinute(),
        solar.getSecond(),
    ).strftime("%Y-%m-%d %H:%M:%S")


@lru_cache(maxsize=1)
def _reference_metadata() -> Dict[str, Any]:
    if not REFERENCE_META_PATH.exists():
        return {}
    return json.loads(REFERENCE_META_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _reference_rows() -> List[_ReferenceRow]:
    if not REFERENCE_ROWS_PATH.exists():
        return []

    rows: List[_ReferenceRow] = []
    for line in REFERENCE_ROWS_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        rows.append(
            _ReferenceRow(
                year=int(payload["year"]),
                term_id=str(payload["term_id"]),
                term_name=str(payload["term_name"]),
                term_type=str(payload["term_type"]),
                solar_term_datetime=str(payload["solar_term_datetime"]),
                source_role=str(payload.get("source_role", "")),
                source=dict(payload.get("source", {})),
            )
        )
    return rows


@lru_cache(maxsize=1)
def _verified_jie_rows_by_year() -> Dict[int, List[_ReferenceRow]]:
    grouped: Dict[int, List[_ReferenceRow]] = {}
    for row in _reference_rows():
        if row.source_role != VERIFIED_SOURCE_ROLE:
            continue
        if not _is_reference_jie(row):
            continue
        grouped.setdefault(row.year, []).append(row)

    for rows in grouped.values():
        rows.sort(key=lambda item: item.datetime_value)
    return grouped


def _reference_evidence(row: _ReferenceRow) -> Dict[str, Any]:
    meta = _reference_metadata()
    source = row.source
    canonical_term_type = _canonical_reference_term_type(row)
    return {
        "table_id": REFERENCE_TABLE_ID,
        "rows_sha256": meta.get("rows_sha256"),
        "source_role": row.source_role,
        "term_id": row.term_id,
        "term_name": row.term_name,
        "term_type": canonical_term_type,
        "source_term_type": row.term_type,
        "source_provider": source.get("provider"),
        "source_method": source.get("source_method"),
        "source_url": source.get("url"),
        "official_almanac_confirmation": source.get("official_almanac_confirmation"),
    }


def _skyfield_cache_dir() -> Path:
    configured_dir = os.environ.get(SKYFIELD_CACHE_ENV)
    if configured_dir:
        return Path(configured_dir)
    return Path.home() / ".cache" / "saju-skyfield"


def _skyfield_ephemeris_path() -> Path:
    return _skyfield_cache_dir() / SKYFIELD_EPHEMERIS


def _file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _validate_skyfield_ephemeris(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing Skyfield ephemeris: {path}. "
            "Run `python -m app.tools.ensure_skyfield_ephemeris --download --check` before serving requests."
        )

    actual_size = path.stat().st_size
    if actual_size != SKYFIELD_EPHEMERIS_SIZE_BYTES:
        raise ValueError(
            f"Invalid Skyfield ephemeris size for {path}: "
            f"{actual_size} != {SKYFIELD_EPHEMERIS_SIZE_BYTES}"
        )

    actual_hash = _file_sha256(path)
    if actual_hash.lower() != SKYFIELD_EPHEMERIS_SHA256:
        raise ValueError(
            f"Invalid Skyfield ephemeris sha256 for {path}: "
            f"{actual_hash} != {SKYFIELD_EPHEMERIS_SHA256}"
        )


@lru_cache(maxsize=1)
def _skyfield_runtime():
    from skyfield.api import Loader, load_file
    from skyfield import almanac, almanac_east_asia

    ephemeris_path = _skyfield_ephemeris_path()
    _validate_skyfield_ephemeris(ephemeris_path)
    loader = Loader(str(ephemeris_path.parent))
    timescale = loader.timescale()
    ephemeris = load_file(str(ephemeris_path))
    return timescale, ephemeris, almanac, almanac_east_asia


def _relation_for(input_dt: datetime, boundary_dt: datetime) -> str:
    return "after" if input_dt >= boundary_dt else "before"


def _canonical_reference_term_type(row: _ReferenceRow) -> str:
    if row.term_id in JIE_TERM_IDS:
        return JIE_TERM_TYPE
    return "junggi"


def _is_reference_jie(row: _ReferenceRow) -> bool:
    return _canonical_reference_term_type(row) == JIE_TERM_TYPE


def _boundary_from_reference(row: _ReferenceRow, input_dt: datetime, relation: str) -> SolarTermBoundary:
    boundary_dt = row.datetime_value
    is_jie = _is_reference_jie(row)
    return SolarTermBoundary(
        name=row.term_name,
        datetime_text=boundary_dt.strftime("%Y-%m-%d %H:%M:%S"),
        delta_seconds=int(abs((input_dt - boundary_dt).total_seconds())),
        relation=relation,
        is_jie=is_jie,
        is_qi=not is_jie,
        provider="solar_term_reference_table",
        provider_apis=["checked_in_jsonl_reference"],
        used_reference=True,
        reference=_reference_evidence(row),
    )


def _round_to_second(value: datetime) -> datetime:
    if value.microsecond >= 500_000:
        value = value + timedelta(seconds=1)
    return value.replace(microsecond=0)


def _boundary_from_skyfield(
    *,
    term_index: int,
    boundary_dt: datetime,
    input_dt: datetime,
    relation: str,
    timezone_id: str,
    fallback_reason: str,
) -> SolarTermBoundary:
    term = SKYFIELD_TERM_DEFINITIONS[term_index]
    boundary_local = _round_to_second(boundary_dt)
    return SolarTermBoundary(
        name=term["term_name"],
        datetime_text=boundary_local.strftime("%Y-%m-%d %H:%M:%S"),
        delta_seconds=int(abs((input_dt - boundary_local.replace(tzinfo=None)).total_seconds())),
        relation=relation,
        is_jie=term["term_type"] == JIE_TERM_TYPE,
        is_qi=term["term_type"] != JIE_TERM_TYPE,
        provider="skyfield",
        provider_apis=SKYFIELD_PROVIDER_APIS,
        used_reference=False,
        fallback_reason=fallback_reason,
        reference={
            "ephemeris": SKYFIELD_EPHEMERIS,
            "term_id": term["term_id"],
            "term_name": term["term_name"],
            "term_type": term["term_type"],
            "timezone_id": timezone_id,
        },
    )


def _boundary_from_lunar_python(term, input_dt: datetime, relation: str, fallback_reason: str) -> SolarTermBoundary:
    term_datetime_text = _solar_to_datetime_text(term.getSolar())
    term_dt = datetime.strptime(term_datetime_text, "%Y-%m-%d %H:%M:%S")
    term_id = TERM_ID_BY_LUNAR_PYTHON_NAME.get(term.getName(), "")
    return SolarTermBoundary(
        name=term.getName(),
        datetime_text=term_datetime_text,
        delta_seconds=int(abs((input_dt - term_dt).total_seconds())),
        relation=relation,
        is_jie=term.isJie(),
        is_qi=term.isQi(),
        provider="lunar_python",
        provider_apis=["Solar.getLunar", "Lunar.getPrevJie", "Lunar.getNextJie"],
        used_reference=False,
        fallback_reason=fallback_reason,
        reference={
            "term_id": term_id,
            "term_name": term.getName(),
            "term_type": JIE_TERM_TYPE if term_id in JIE_TERM_IDS else "junggi",
        },
    )


def _fallback_reason_for(timezone_id: str, years: Iterable[int]) -> str:
    if timezone_id != REFERENCE_TIMEZONE_ID:
        return "reference_timezone_not_supported"

    available_years = set(_verified_jie_rows_by_year())
    if not any(year in available_years for year in years):
        return "verified_reference_not_available_for_year"
    return "verified_reference_not_available_for_boundary"


def _verified_reference_rows_for_years(years: Iterable[int], timezone_id: str) -> List[_ReferenceRow]:
    if timezone_id != REFERENCE_TIMEZONE_ID:
        return []

    grouped = _verified_jie_rows_by_year()
    rows: List[_ReferenceRow] = []
    for year in years:
        rows.extend(grouped.get(year, []))
    return sorted(rows, key=lambda item: item.datetime_value)


def _has_verified_reference_for_years(years: Iterable[int], timezone_id: str) -> bool:
    if timezone_id != REFERENCE_TIMEZONE_ID:
        return False

    grouped = _verified_jie_rows_by_year()
    return any(year in grouped for year in years)


def _nearest_reference_boundary(input_dt: datetime, timezone_id: str) -> Optional[SolarTermBoundary]:
    rows = _verified_reference_rows_for_years(
        (input_dt.year - 1, input_dt.year, input_dt.year + 1),
        timezone_id,
    )
    if not rows:
        return None

    nearest = min(rows, key=lambda row: abs((input_dt - row.datetime_value).total_seconds()))
    return _boundary_from_reference(
        nearest,
        input_dt,
        _relation_for(input_dt, nearest.datetime_value),
    )


def _skyfield_boundaries_between(
    *,
    start_dt: datetime,
    end_dt: datetime,
    input_dt: datetime,
    timezone_id: str,
    relation: str,
    fallback_reason: str,
) -> List[SolarTermBoundary]:
    zone = ZoneInfo(timezone_id)
    timescale, ephemeris, almanac, almanac_east_asia = _skyfield_runtime()
    aware_start = start_dt.replace(tzinfo=zone)
    aware_end = end_dt.replace(tzinfo=zone)
    times, values = almanac.find_discrete(
        timescale.from_datetime(aware_start.astimezone(timezone.utc)),
        timescale.from_datetime(aware_end.astimezone(timezone.utc)),
        almanac_east_asia.solar_terms(ephemeris),
    )

    boundaries: List[SolarTermBoundary] = []
    for time_value, term_value in zip(times, values):
        term_index = int(term_value)
        term = SKYFIELD_TERM_DEFINITIONS.get(term_index)
        if term is None or term["term_type"] != JIE_TERM_TYPE:
            continue
        boundary_dt = time_value.utc_datetime().astimezone(zone)
        boundaries.append(
            _boundary_from_skyfield(
                term_index=term_index,
                boundary_dt=boundary_dt,
                input_dt=input_dt,
                relation=relation,
                timezone_id=timezone_id,
                fallback_reason=fallback_reason,
            )
        )
    return boundaries


def _nearest_skyfield_boundary(
    input_dt: datetime,
    timezone_id: str,
    fallback_reason: str,
) -> Optional[SolarTermBoundary]:
    try:
        boundaries = _skyfield_boundaries_between(
            start_dt=input_dt - timedelta(days=SKYFIELD_SEARCH_DAYS),
            end_dt=input_dt + timedelta(days=SKYFIELD_SEARCH_DAYS),
            input_dt=input_dt,
            timezone_id=timezone_id,
            relation="nearest",
            fallback_reason=fallback_reason,
        )
    except Exception:
        return None
    if not boundaries:
        return None

    nearest = min(boundaries, key=lambda item: item.delta_seconds)
    boundary_dt = datetime.strptime(nearest.datetime_text, "%Y-%m-%d %H:%M:%S")
    return SolarTermBoundary(
        name=nearest.name,
        datetime_text=nearest.datetime_text,
        delta_seconds=nearest.delta_seconds,
        relation=_relation_for(input_dt, boundary_dt),
        is_jie=nearest.is_jie,
        is_qi=nearest.is_qi,
        provider=nearest.provider,
        provider_apis=nearest.provider_apis,
        used_reference=nearest.used_reference,
        fallback_reason=nearest.fallback_reason,
        reference=nearest.reference,
    )


def _nearest_lunar_python_boundary(input_dt: datetime, fallback_reason: str) -> SolarTermBoundary:
    solar = Solar.fromYmdHms(
        input_dt.year,
        input_dt.month,
        input_dt.day,
        input_dt.hour,
        input_dt.minute,
        input_dt.second,
    )
    lunar = solar.getLunar()
    previous_jie = _boundary_from_lunar_python(lunar.getPrevJie(), input_dt, "after", fallback_reason)
    next_jie = _boundary_from_lunar_python(lunar.getNextJie(), input_dt, "before", fallback_reason)
    return min((previous_jie, next_jie), key=lambda item: item.delta_seconds)


def _term_id_for_boundary(boundary: SolarTermBoundary) -> str:
    return str(boundary.reference.get("term_id", ""))


def _reference_boundary_for_year_term(
    year: int,
    term_id: str,
    timezone_id: str,
) -> Optional[SolarTermBoundary]:
    input_dt = datetime(year, *JIE_TERM_APPROX_DATES[term_id], 12, 0, 0)
    for row in _verified_reference_rows_for_years((year,), timezone_id):
        if row.term_id == term_id:
            return _boundary_from_reference(
                row,
                input_dt,
                _relation_for(input_dt, row.datetime_value),
            )
    return None


def _skyfield_boundary_for_year_term(
    year: int,
    term_id: str,
    timezone_id: str,
    fallback_reason: str,
) -> Optional[SolarTermBoundary]:
    month, day = JIE_TERM_APPROX_DATES[term_id]
    input_dt = datetime(year, month, day, 12, 0, 0)
    try:
        boundaries = _skyfield_boundaries_between(
            start_dt=input_dt - timedelta(days=8),
            end_dt=input_dt + timedelta(days=8),
            input_dt=input_dt,
            timezone_id=timezone_id,
            relation="specific",
            fallback_reason=fallback_reason,
        )
    except Exception:
        return None

    for boundary in boundaries:
        if _term_id_for_boundary(boundary) == term_id:
            return boundary
    return None


def _lunar_python_boundary_for_year_term(
    year: int,
    term_id: str,
    fallback_reason: str,
) -> Optional[SolarTermBoundary]:
    month, day = JIE_TERM_APPROX_DATES[term_id]
    input_dt = datetime(year, month, day, 12, 0, 0)
    solar = Solar.fromYmdHms(year, month, day, 12, 0, 0)
    lunar = solar.getLunar()
    candidates = [
        _boundary_from_lunar_python(lunar.getPrevJie(), input_dt, "specific", fallback_reason),
        _boundary_from_lunar_python(lunar.getNextJie(), input_dt, "specific", fallback_reason),
    ]
    matches = [boundary for boundary in candidates if _term_id_for_boundary(boundary) == term_id]
    if matches:
        return min(matches, key=lambda item: item.delta_seconds)
    return None


def find_jie_boundary_by_term(
    year: int,
    term_id: str,
    *,
    timezone_id: str = REFERENCE_TIMEZONE_ID,
) -> Optional[SolarTermBoundary]:
    """Return a specific Jie boundary for a calendar year."""
    if term_id not in JIE_TERM_IDS:
        raise ValueError(f"Unsupported Jie term id: {term_id}")

    reference_boundary = _reference_boundary_for_year_term(year, term_id, timezone_id)
    if reference_boundary is not None:
        return reference_boundary

    fallback_reason = _fallback_reason_for(timezone_id, (year,))
    skyfield_boundary = _skyfield_boundary_for_year_term(
        year,
        term_id,
        timezone_id,
        fallback_reason,
    )
    if skyfield_boundary is not None:
        return skyfield_boundary

    return _lunar_python_boundary_for_year_term(year, term_id, fallback_reason)


def list_jie_boundaries_for_years(
    years: Iterable[int],
    *,
    timezone_id: str = REFERENCE_TIMEZONE_ID,
) -> List[SolarTermBoundary]:
    """Return month-boundary Jie rows for the requested years."""
    boundaries: List[SolarTermBoundary] = []
    for year in years:
        for term_id in JIE_TERM_IDS_IN_MONTH_ORDER:
            boundary = find_jie_boundary_by_term(year, term_id, timezone_id=timezone_id)
            if boundary is not None:
                boundaries.append(boundary)
    return sorted(
        boundaries,
        key=lambda item: datetime.strptime(item.datetime_text, "%Y-%m-%d %H:%M:%S"),
    )


def nearest_solar_term_boundary(
    input_datetime_text: str,
    *,
    timezone_id: str = REFERENCE_TIMEZONE_ID,
) -> Optional[SolarTermBoundary]:
    """Return the nearest Jie boundary, preferring verified reference rows."""
    input_dt = _parse_input_datetime(input_datetime_text)
    if input_dt is None:
        return None

    reference_boundary = _nearest_reference_boundary(input_dt, timezone_id)
    if reference_boundary is not None:
        return reference_boundary

    fallback_reason = _fallback_reason_for(
        timezone_id,
        (input_dt.year - 1, input_dt.year, input_dt.year + 1),
    )
    skyfield_boundary = _nearest_skyfield_boundary(input_dt, timezone_id, fallback_reason)
    if skyfield_boundary is not None:
        return skyfield_boundary

    return _nearest_lunar_python_boundary(input_dt, fallback_reason)


def nearest_skyfield_solar_term_boundary(
    input_datetime_text: str,
    *,
    timezone_id: str = REFERENCE_TIMEZONE_ID,
) -> Optional[SolarTermBoundary]:
    """Return the nearest Skyfield-derived Jie boundary for reference checks."""
    input_dt = _parse_input_datetime(input_datetime_text)
    if input_dt is None:
        return None
    return _nearest_skyfield_boundary(input_dt, timezone_id, "skyfield_direct_reference_check")


def _reference_boundary_inside_interval(
    start_dt: datetime,
    end_dt: datetime,
    timezone_id: str,
) -> Optional[SolarTermBoundary]:
    rows = _verified_reference_rows_for_years(
        range(start_dt.year, end_dt.year + 1),
        timezone_id,
    )
    boundaries = [
        _boundary_from_reference(row, start_dt, "inside_interval")
        for row in rows
        if start_dt <= row.datetime_value <= end_dt
    ]
    if not boundaries:
        return None

    return min(boundaries, key=lambda item: item.delta_seconds)


def _lunar_python_boundary_inside_interval(
    start_dt: datetime,
    end_dt: datetime,
    fallback_reason: str,
) -> Optional[SolarTermBoundary]:
    solar = Solar.fromYmdHms(
        start_dt.year,
        start_dt.month,
        start_dt.day,
        start_dt.hour,
        start_dt.minute,
        start_dt.second,
    )
    lunar = solar.getLunar()
    candidates = [
        _boundary_from_lunar_python(lunar.getPrevJie(), start_dt, "inside_interval", fallback_reason),
        _boundary_from_lunar_python(lunar.getNextJie(), start_dt, "inside_interval", fallback_reason),
    ]

    boundaries_inside_interval: List[SolarTermBoundary] = []
    for candidate in candidates:
        candidate_dt = datetime.strptime(candidate.datetime_text, "%Y-%m-%d %H:%M:%S")
        if start_dt <= candidate_dt <= end_dt:
            boundaries_inside_interval.append(candidate)

    if not boundaries_inside_interval:
        return None
    return min(boundaries_inside_interval, key=lambda item: item.delta_seconds)


def _skyfield_boundary_inside_interval(
    start_dt: datetime,
    end_dt: datetime,
    timezone_id: str,
    fallback_reason: str,
) -> Optional[SolarTermBoundary]:
    try:
        boundaries = _skyfield_boundaries_between(
            start_dt=start_dt,
            end_dt=end_dt,
            input_dt=start_dt,
            timezone_id=timezone_id,
            relation="inside_interval",
            fallback_reason=fallback_reason,
        )
    except Exception:
        return None

    boundaries_inside_interval: List[SolarTermBoundary] = []
    for candidate in boundaries:
        candidate_dt = datetime.strptime(candidate.datetime_text, "%Y-%m-%d %H:%M:%S")
        if start_dt <= candidate_dt <= end_dt:
            boundaries_inside_interval.append(candidate)

    if not boundaries_inside_interval:
        return None
    return min(boundaries_inside_interval, key=lambda item: item.delta_seconds)


def _adjacent_reference_boundary(
    input_dt: datetime,
    direction: SkyfieldTermDirection,
    timezone_id: str,
) -> Optional[SolarTermBoundary]:
    rows = _verified_reference_rows_for_years(
        (input_dt.year - 1, input_dt.year, input_dt.year + 1),
        timezone_id,
    )
    if not rows:
        return None

    if direction == "forward":
        candidates = [row for row in rows if row.datetime_value > input_dt]
        if not candidates:
            return None
        row = min(candidates, key=lambda item: item.datetime_value)
        relation = "before"
    else:
        candidates = [row for row in rows if row.datetime_value < input_dt]
        if not candidates:
            return None
        row = max(candidates, key=lambda item: item.datetime_value)
        relation = "after"

    return _boundary_from_reference(row, input_dt, relation)


def _adjacent_skyfield_boundary(
    input_dt: datetime,
    direction: SkyfieldTermDirection,
    timezone_id: str,
    fallback_reason: str,
) -> Optional[SolarTermBoundary]:
    if direction == "forward":
        start_dt = input_dt
        end_dt = input_dt + timedelta(days=SKYFIELD_SEARCH_DAYS)
        relation = "before"
    else:
        start_dt = input_dt - timedelta(days=SKYFIELD_SEARCH_DAYS)
        end_dt = input_dt
        relation = "after"

    try:
        boundaries = _skyfield_boundaries_between(
            start_dt=start_dt,
            end_dt=end_dt,
            input_dt=input_dt,
            timezone_id=timezone_id,
            relation=relation,
            fallback_reason=fallback_reason,
        )
    except Exception:
        return None

    if direction == "forward":
        future_boundaries = [
            boundary
            for boundary in boundaries
            if datetime.strptime(boundary.datetime_text, "%Y-%m-%d %H:%M:%S") > input_dt
        ]
        if not future_boundaries:
            return None
        return min(
            future_boundaries,
            key=lambda item: datetime.strptime(item.datetime_text, "%Y-%m-%d %H:%M:%S"),
        )

    previous_boundaries = [
        boundary
        for boundary in boundaries
        if datetime.strptime(boundary.datetime_text, "%Y-%m-%d %H:%M:%S") < input_dt
    ]
    if not previous_boundaries:
        return None
    return max(
        previous_boundaries,
        key=lambda item: datetime.strptime(item.datetime_text, "%Y-%m-%d %H:%M:%S"),
    )


def find_jie_inside_interval(
    start_dt: datetime,
    end_dt: datetime,
    *,
    timezone_id: str = REFERENCE_TIMEZONE_ID,
) -> Optional[SolarTermBoundary]:
    """Return a Jie boundary inside an interval, using reference rows when possible."""
    reference_boundary = _reference_boundary_inside_interval(start_dt, end_dt, timezone_id)
    if reference_boundary is not None:
        return reference_boundary

    years = range(start_dt.year, end_dt.year + 1)
    if _has_verified_reference_for_years(years, timezone_id):
        return None

    fallback_reason = _fallback_reason_for(
        timezone_id,
        years,
    )
    skyfield_boundary = _skyfield_boundary_inside_interval(
        start_dt,
        end_dt,
        timezone_id,
        fallback_reason,
    )
    if skyfield_boundary is not None:
        return skyfield_boundary

    return _lunar_python_boundary_inside_interval(start_dt, end_dt, fallback_reason)


def find_adjacent_jie_boundary(
    input_dt: datetime,
    direction: SkyfieldTermDirection,
    *,
    timezone_id: str = REFERENCE_TIMEZONE_ID,
) -> Optional[SolarTermBoundary]:
    """Return the previous/next Jie boundary for calculation paths."""
    reference_boundary = _adjacent_reference_boundary(input_dt, direction, timezone_id)
    if reference_boundary is not None:
        return reference_boundary

    fallback_reason = _fallback_reason_for(
        timezone_id,
        (input_dt.year - 1, input_dt.year, input_dt.year + 1),
    )
    skyfield_boundary = _adjacent_skyfield_boundary(
        input_dt,
        direction,
        timezone_id,
        fallback_reason,
    )
    if skyfield_boundary is not None:
        return skyfield_boundary

    return None
