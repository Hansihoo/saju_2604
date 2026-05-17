"""Build a mixed-source extended solar-term reference table.

This maintenance tool creates reference data only. It does not change the
primary saju calculation path.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.tools import build_solar_term_reference_table as common


REPO_ROOT = Path(__file__).resolve().parents[4]
API_ROOT = REPO_ROOT / "apps" / "api"
REFERENCE_DIR = API_ROOT / "app" / "domain" / "saju" / "data" / "solar_terms_reference"
TABLE_ID = "solar_terms_extended_1946_2027"
ROWS_PATH = REFERENCE_DIR / f"{TABLE_ID}.jsonl"
META_PATH = REFERENCE_DIR / f"{TABLE_ID}.meta.json"
LOG_PATH = REFERENCE_DIR / f"{TABLE_ID}.collection.log.jsonl"

BEBEYAM_SEED_URL = (
    "https://bebeyam.com/%EC%82%AC%EC%A3%BC-%EB%A7%8C%EC%84%B8%EB%A0%A5-1946%EB%85%84-"
    "%EB%B3%91%EC%88%A0%EB%85%84-24%EC%A0%88%EA%B8%B0-%EC%A0%88%EC%9E%85%EC%8B%9C%EA%B0%84-"
    "%EC%9E%85%EC%B6%98/"
)
UNCLE_TOOLS_URL_TEMPLATE = "https://uncle.tools/manse/solar-terms/{year}"
TARGET_YEARS = list(range(1946, 2028))
BEBEYAM_YEARS = list(range(1946, 2012))
COMMON_TABLE_YEARS = list(range(2012, 2028))

YEAR_MARKER = "\ub144"
MONTH_MARKER = "\uc6d4"
DAY_MARKER = "\uc77c"
HOUR_MARKER = "\uc2dc"
MINUTE_MARKER = "\ubd84"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _request_text(url: str, *, timeout_seconds: int = 20) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "saju-extended-solar-term-builder/1.0"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8", "replace")


def _strip_html(value: str) -> str:
    text = re.sub(r"<script\b.*?</script>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text)


def _append_log(event: Dict[str, Any]) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ts": _utc_now(), **event}
    with LOG_PATH.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def _term_maps() -> Tuple[Dict[str, Tuple[str, int, str]], List[str]]:
    by_name = {
        name: (term_id, term_index, term_type)
        for term_id, name, term_index, term_type in common.SOLAR_TERMS
    }
    ordered_names = [name for _term_id, name, _index, _type in common.SOLAR_TERMS]
    return by_name, ordered_names


def _normalize_datetime(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    normalized_month, normalized_day, normalized_hour, normalized_minute = common._normalize_clock_fields(
        year,
        month,
        day,
        hour,
        minute,
    )
    return datetime(year, normalized_month, normalized_day, normalized_hour, normalized_minute)


def discover_bebeyam_year_links() -> Dict[int, str]:
    seed_html = _request_text(BEBEYAM_SEED_URL)
    links: Dict[int, str] = {1946: BEBEYAM_SEED_URL}
    year_pattern = re.compile(r"([0-9]{4})" + YEAR_MARKER)
    for match in re.finditer(r'<a[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<body>.*?)</a>', seed_html, re.DOTALL):
        body = _strip_html(match.group("body"))
        year_match = year_pattern.search(body)
        if not year_match or "24" not in body:
            continue
        year = int(year_match.group(1))
        if 1946 <= year <= 2023:
            links[year] = urllib.parse.urljoin(BEBEYAM_SEED_URL, match.group("href"))
    return links


def parse_bebeyam_year(year: int, url: str) -> Dict[str, Dict[str, Any]]:
    by_name, ordered_names = _term_maps()
    plain_text = _strip_html(_request_text(url))
    rows: Dict[str, Dict[str, Any]] = {}
    for name in ordered_names:
        pattern = re.compile(
            re.escape(name)
            + r"\s+[0-9]{1,3}\s+"
            + r"(?P<month>[0-9]{1,2})\s+"
            + r"(?P<day>[0-9]{1,2})\s+"
            + r"(?P<hour>[0-9]{1,2})\s+"
            + r"(?P<minute>[0-9]{1,2})"
        )
        matches = list(pattern.finditer(plain_text))
        if not matches:
            continue
        match = matches[-1]
        dt = _normalize_datetime(
            year,
            int(match.group("month")),
            int(match.group("day")),
            int(match.group("hour")),
            int(match.group("minute")),
        )
        term_id, term_index, term_type = by_name[name]
        rows[term_id] = {
            "year": year,
            "term_id": term_id,
            "term_name": name,
            "term_index": term_index,
            "term_type": term_type,
            "month": dt.month,
            "day": dt.day,
            "hour": dt.hour,
            "minute": dt.minute,
            "timezone_id": "Asia/Seoul",
            "utc_offset_minutes": 540,
            "solar_term_datetime": f"{dt:%Y-%m-%dT%H:%M}:00+09:00",
            "source": {
                "type": "secondary_almanac_transcription",
                "name": "Bebeyam KASI almanac transcription",
                "provider": "Bebeyam",
                "url": url,
                "source_method": "bebeyam_html_transcription",
                "official_almanac_confirmation": "pending_kasi_image_or_pdf_cross_check",
            },
        }
    return rows


def parse_uncle_tools_year(year: int) -> Dict[str, str]:
    by_name, ordered_names = _term_maps()
    plain_text = _strip_html(_request_text(UNCLE_TOOLS_URL_TEMPLATE.format(year=year)))
    rows: Dict[str, str] = {}
    for name in ordered_names:
        pattern = re.compile(
            re.escape(name)
            + r"\s*(?P<month>[0-9]{1,2})\s*"
            + MONTH_MARKER
            + r"\s*(?P<day>[0-9]{1,2})\s*"
            + DAY_MARKER
            + r"\s*(?P<hour>[0-9]{1,2})\s*"
            + HOUR_MARKER
            + r"\s*(?P<minute>[0-9]{1,2})\s*"
            + MINUTE_MARKER
        )
        candidates: List[datetime] = []
        for match in pattern.finditer(plain_text):
            month = int(match.group("month"))
            day = int(match.group("day"))
            if month == 0 or day == 0:
                continue
            try:
                candidates.append(
                    _normalize_datetime(
                        year,
                        month,
                        day,
                        int(match.group("hour")),
                        int(match.group("minute")),
                    )
                )
            except ValueError:
                continue
        if candidates:
            term_id, _term_index, _term_type = by_name[name]
            rows[term_id] = f"{candidates[-1]:%Y-%m-%dT%H:%M}:00+09:00"
    return rows


def _datetime_from_text(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z").replace(tzinfo=None)


def _validation_against_uncle(term_datetime: str, uncle_datetime: Optional[str]) -> Dict[str, Any]:
    if not uncle_datetime:
        return {
            "comparison_source": "uncle_tools_nasa_de441",
            "status": "not_available",
            "delta_minutes": None,
            "comparison_datetime": None,
        }
    delta = abs((_datetime_from_text(term_datetime) - _datetime_from_text(uncle_datetime)).total_seconds()) / 60
    if delta <= 1:
        status = "matches_within_1_minute"
    elif delta <= 2:
        status = "near_match_within_2_minutes"
    else:
        status = "differs_possible_dst_or_transcription_risk"
    return {
        "comparison_source": "uncle_tools_nasa_de441",
        "status": status,
        "delta_minutes": round(delta, 3),
        "comparison_datetime": uncle_datetime,
    }


def _read_common_rows() -> Dict[Tuple[int, str], Dict[str, Any]]:
    return {
        (int(row["year"]), row["term_id"]): row
        for row in common._read_rows(common.DEFAULT_ROWS_PATH)
    }


def _copy_common_row(row: Dict[str, Any]) -> Dict[str, Any]:
    copied = json.loads(json.dumps(row, ensure_ascii=False))
    copied["source_role"] = "official_reference_table"
    return copied


def build_extended_rows() -> List[Dict[str, Any]]:
    common_rows = _read_common_rows()
    bebeyam_links = discover_bebeyam_year_links()
    rows: List[Dict[str, Any]] = []
    source_gaps: Dict[int, List[str]] = {}
    validation_summary: Dict[str, int] = {}

    for year in BEBEYAM_YEARS:
        if year not in bebeyam_links:
            source_gaps[year] = [term_id for term_id, _name, _index, _type in common.SOLAR_TERMS]
            continue
        bebeyam_rows = parse_bebeyam_year(year, bebeyam_links[year])
        try:
            uncle_rows = parse_uncle_tools_year(year)
        except Exception as exc:
            uncle_rows = {}
            _append_log(
                {
                    "event": "uncle_tools_validation_failed",
                    "year": year,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )

        missing = []
        for term_id, _name, _index, _type in common.SOLAR_TERMS:
            row = bebeyam_rows.get(term_id)
            if row is None:
                missing.append(term_id)
                continue
            validation = _validation_against_uncle(row["solar_term_datetime"], uncle_rows.get(term_id))
            row["source"]["validation"] = validation
            row["source_role"] = "extended_secondary_reference"
            validation_summary[validation["status"]] = validation_summary.get(validation["status"], 0) + 1
            rows.append(row)
        if missing:
            source_gaps[year] = missing

    for year in COMMON_TABLE_YEARS:
        for term_id, _name, _index, _type in common.SOLAR_TERMS:
            row = common_rows.get((year, term_id))
            if row is None:
                source_gaps.setdefault(year, []).append(term_id)
                continue
            rows.append(_copy_common_row(row))

    _append_log(
        {
            "event": "extended_rows_built",
            "row_count": len(rows),
            "source_gap_year_count": len(source_gaps),
            "validation_summary": validation_summary,
        }
    )
    return sorted(rows, key=lambda item: (int(item["year"]), int(item["term_index"])))


def _row_bytes(rows: Sequence[Dict[str, Any]]) -> List[bytes]:
    return [
        (json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        for row in rows
    ]


def _validate_rows(rows: Sequence[Dict[str, Any]]) -> Dict[int, List[str]]:
    by_year: Dict[int, List[Dict[str, Any]]] = {}
    for row in rows:
        by_year.setdefault(int(row["year"]), []).append(row)

    gaps: Dict[int, List[str]] = {}
    expected_order = [term_id for term_id, _name, _index, _type in common.SOLAR_TERMS]
    for year in TARGET_YEARS:
        year_rows = sorted(by_year.get(year, []), key=lambda item: int(item["term_index"]))
        actual_order = [row["term_id"] for row in year_rows]
        missing = [term_id for term_id in expected_order if term_id not in actual_order]
        if missing:
            gaps[year] = missing
        if [term_id for term_id in expected_order if term_id in actual_order] != actual_order:
            raise ValueError(f"Unexpected solar-term order for {year}: {actual_order}")
        for row in year_rows:
            prefix = f"{year:04d}-{int(row['month']):02d}-{int(row['day']):02d}T"
            if not row["solar_term_datetime"].startswith(prefix):
                raise ValueError(f"Datetime does not match date fields: {row}")
    return gaps


def _build_metadata(rows: Sequence[Dict[str, Any]], gaps: Dict[int, List[str]]) -> Dict[str, Any]:
    rows_digest = hashlib.sha256(b"".join(_row_bytes(rows))).hexdigest()
    years = sorted({int(row["year"]) for row in rows})
    complete_years = [year for year in TARGET_YEARS if year not in gaps]
    partial_years = [year for year in TARGET_YEARS if year in gaps and any(int(row["year"]) == year for row in rows)]
    source_role_counts: Dict[str, int] = {}
    secondary_validation_counts: Dict[str, int] = {}
    for row in rows:
        source_role = row.get("source_role", "unknown")
        source_role_counts[source_role] = source_role_counts.get(source_role, 0) + 1
        validation_status = row.get("source", {}).get("validation", {}).get("status")
        if validation_status:
            secondary_validation_counts[validation_status] = secondary_validation_counts.get(validation_status, 0) + 1
    generated_at = _utc_now()
    return {
        "schema_version": 1,
        "table_id": TABLE_ID,
        "description": "Mixed-source extended solar-term reference candidate table for age-80 coverage.",
        "timezone_id": "Asia/Seoul",
        "range": {
            "target_years": TARGET_YEARS,
            "start_year": TARGET_YEARS[0],
            "end_year": TARGET_YEARS[-1],
            "complete_years": complete_years,
            "partial_years": partial_years,
            "missing_terms_by_year": {str(year): terms for year, terms in gaps.items()},
        },
        "terms_per_complete_year": 24,
        "row_count": len(rows),
        "rows_sha256": rows_digest,
        "source_role_counts": source_role_counts,
        "secondary_validation_counts": secondary_validation_counts,
        "generated_at": generated_at,
        "retrieved_at": generated_at,
        "generated_by": "python -m app.tools.build_extended_solar_term_reference_table",
        "source_policy": [
            "2012-2027 rows are copied from the existing KASI-oriented reference table.",
            "1946-2011 rows use Bebeyam's KASI-almanac transcription as a secondary source.",
            "Secondary rows keep Uncle Tools comparison metadata when available.",
            "Rows with secondary sources are not approved for primary calculation until official KASI images/PDFs are cross-checked.",
        ],
        "known_limits": [
            "KASI almanac archive HTML for 2011 appears to expose stale 2004-like solar-term rows, so 2011 is sourced from secondary transcription with independent comparison metadata.",
            "KASI official 1946-2010 year pages are image-only in the discovered interface, so full machine extraction remains pending.",
            "1946 is partial in the secondary transcription: sohan and daehan are missing.",
        ],
        "log_path": str(LOG_PATH.relative_to(REPO_ROOT)),
    }


def build_table() -> Dict[str, Any]:
    rows = build_extended_rows()
    gaps = _validate_rows(rows)
    metadata = _build_metadata(rows, gaps)
    _atomic_write_text(ROWS_PATH, b"".join(_row_bytes(rows)).decode("utf-8"))
    _atomic_write_text(META_PATH, json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _append_log(
        {
            "event": "extended_table_written",
            "rows_path": str(ROWS_PATH.relative_to(REPO_ROOT)),
            "meta_path": str(META_PATH.relative_to(REPO_ROOT)),
            "row_count": len(rows),
            "rows_sha256": metadata["rows_sha256"],
        }
    )
    return {
        "table_id": TABLE_ID,
        "row_count": len(rows),
        "complete_years": metadata["range"]["complete_years"],
        "partial_years": metadata["range"]["partial_years"],
        "missing_terms_by_year": metadata["range"]["missing_terms_by_year"],
        "rows_sha256": metadata["rows_sha256"],
    }


def check_table() -> Dict[str, Any]:
    metadata = json.loads(META_PATH.read_text(encoding="utf-8"))
    rows_text = ROWS_PATH.read_text(encoding="utf-8")
    rows = [json.loads(line) for line in rows_text.splitlines() if line.strip()]
    gaps = _validate_rows(rows)
    file_hash = hashlib.sha256(rows_text.encode("utf-8")).hexdigest()
    result = {
        "table_id": metadata.get("table_id"),
        "row_count": len(rows),
        "metadata_row_count": metadata.get("row_count"),
        "file_hash": file_hash,
        "metadata_hash": metadata.get("rows_sha256"),
        "hash_matches_metadata": file_hash == metadata.get("rows_sha256"),
        "complete_years": metadata.get("range", {}).get("complete_years", []),
        "partial_years": metadata.get("range", {}).get("partial_years", []),
        "missing_terms_by_year": {str(year): terms for year, terms in gaps.items()},
    }
    if not all(
        [
            result["table_id"] == TABLE_ID,
            result["row_count"] == result["metadata_row_count"],
            result["hash_matches_metadata"],
            result["missing_terms_by_year"] == metadata.get("range", {}).get("missing_terms_by_year", {}),
        ]
    ):
        raise SystemExit(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or verify mixed-source extended solar-term references.")
    parser.add_argument("--check", action="store_true", help="Verify the checked-in table without network access.")
    args = parser.parse_args()

    if args.check:
        payload = check_table()
    else:
        payload = build_table()
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
