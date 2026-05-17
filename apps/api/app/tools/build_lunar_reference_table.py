"""Build or verify the versioned KASI lunar/solar reference table.

The checked-in table is data-only and production code reads it locally. Network
access to KASI is limited to explicit maintenance commands.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[4]
API_ROOT = REPO_ROOT / "apps" / "api"
REFERENCE_DIR = API_ROOT / "app" / "domain" / "saju" / "data" / "lunar_reference"
TABLE_ID = "kasi_lunar_calendar_1900_2050"
DEFAULT_START_DATE = "1900-01-01"
DEFAULT_END_DATE = "2050-12-31"
DEFAULT_ROWS_PATH = REFERENCE_DIR / f"{TABLE_ID}.jsonl"
DEFAULT_META_PATH = REFERENCE_DIR / f"{TABLE_ID}.meta.json"
DEFAULT_ENDPOINT = "https://apis.data.go.kr/B090041/openapi/service/LrsrCldInfoService/getLunCalInfo"
DEFAULT_MAX_WORKERS = 8
SOURCE = {
    "type": "official_open_api",
    "name": "KASI lunisolar calendar API",
    "provider": "Korea Astronomy and Space Science Institute",
    "endpoint": DEFAULT_ENDPOINT,
    "data_go_kr_url": "https://www.data.go.kr/data/15012679/openapi.do",
}
ILJIN_PATTERN = re.compile(r"^(?P<korean>.+)\((?P<hanja>.+)\)$")


@dataclass(frozen=True)
class KasiMonthRequest:
    year: int
    month: int


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _iter_dates(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _iter_month_requests(start: date, end: date) -> Iterable[KasiMonthRequest]:
    year = start.year
    month = start.month
    while (year, month) <= (end.year, end.month):
        yield KasiMonthRequest(year=year, month=month)
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1


def _read_env_file(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() not in {"KASI_SERVICE_KEY", "KASI_DECODING_SERVICE_KEY"}:
            continue
        value = value.strip().strip('"').strip("'")
        if value:
            return value
    return None


def _read_windows_user_env(name: str) -> Optional[str]:
    if os.name != "nt":
        return None
    try:
        value = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"[Environment]::GetEnvironmentVariable('{name}','User')",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None
    return value or None


def load_service_key(explicit_service_key: Optional[str] = None) -> str:
    candidates = [
        explicit_service_key,
        os.environ.get("KASI_SERVICE_KEY"),
        os.environ.get("KASI_DECODING_SERVICE_KEY"),
        _read_env_file(API_ROOT / ".env.local"),
        _read_env_file(REPO_ROOT / ".env.local"),
        _read_windows_user_env("KASI_SERVICE_KEY"),
        _read_windows_user_env("KASI_DECODING_SERVICE_KEY"),
    ]
    for candidate in candidates:
        if candidate:
            return candidate
    raise RuntimeError(
        "KASI_SERVICE_KEY was not found. Set it as an environment variable or in apps/api/.env.local."
    )


def _service_key_query_value(service_key: str) -> str:
    # data.go.kr often shows both decoding and encoding keys. Encoded keys must
    # be passed through as-is, while decoded keys need URL encoding.
    if "%" in service_key:
        return service_key
    return urllib.parse.quote(service_key, safe="")


def _request_url(*, endpoint: str, service_key: str, params: Dict[str, str]) -> str:
    encoded_params = urllib.parse.urlencode(params)
    return f"{endpoint}?ServiceKey={_service_key_query_value(service_key)}&{encoded_params}"


def _find_text(root: ET.Element, name: str) -> Optional[str]:
    node = root.find(f".//{name}")
    return node.text.strip() if node is not None and node.text is not None else None


def _find_item_text(item: ET.Element, name: str) -> str:
    node = item.find(name)
    if node is None or node.text is None:
        raise ValueError(f"KASI response item is missing {name}")
    return node.text.strip()


def _parse_iljin(value: str) -> Tuple[str, str]:
    match = ILJIN_PATTERN.match(value.strip())
    if not match:
        raise ValueError(f"Unexpected KASI iljin format: {value!r}")
    return match.group("korean"), match.group("hanja")


def _parse_kasi_item(item: ET.Element) -> Dict[str, Any]:
    sol_year = int(_find_item_text(item, "solYear"))
    sol_month = int(_find_item_text(item, "solMonth"))
    sol_day = int(_find_item_text(item, "solDay"))
    lunar_year = int(_find_item_text(item, "lunYear"))
    lunar_month = int(_find_item_text(item, "lunMonth"))
    lunar_day = int(_find_item_text(item, "lunDay"))
    iljin_korean, iljin_hanja = _parse_iljin(_find_item_text(item, "lunIljin"))
    leap_value = _find_item_text(item, "lunLeapmonth")
    julian_day_text = _find_text(item, "solJd")

    return {
        "solar_date": f"{sol_year:04d}-{sol_month:02d}-{sol_day:02d}",
        "solar_year": sol_year,
        "solar_month": sol_month,
        "solar_day": sol_day,
        "lunar_date": f"{lunar_year:04d}-{lunar_month:02d}-{lunar_day:02d}",
        "lunar_year": lunar_year,
        "lunar_month": lunar_month,
        "lunar_day": lunar_day,
        "is_lunar_leap_month": leap_value == "\uc724",
        "day_ganzhi_korean": iljin_korean,
        "day_ganzhi_hanja": iljin_hanja,
        "julian_day": int(julian_day_text) if julian_day_text else None,
    }


def fetch_kasi_month(
    request: KasiMonthRequest,
    *,
    service_key: str,
    endpoint: str = DEFAULT_ENDPOINT,
    timeout_seconds: int = 20,
    retry_count: int = 3,
) -> List[Dict[str, Any]]:
    params = {
        "solYear": f"{request.year:04d}",
        "solMonth": f"{request.month:02d}",
        "numOfRows": "40",
        "pageNo": "1",
    }
    url = _request_url(endpoint=endpoint, service_key=service_key, params=params)
    last_error: Optional[BaseException] = None
    for attempt in range(1, retry_count + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "saju-kasi-reference-builder/1.0"})
            with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
                xml_text = response.read().decode("utf-8")
            root = ET.fromstring(xml_text)
            result_code = _find_text(root, "resultCode")
            if result_code != "00":
                result_msg = _find_text(root, "resultMsg")
                raise RuntimeError(
                    f"KASI API returned resultCode={result_code!r}, resultMsg={result_msg!r}"
                )
            return [_parse_kasi_item(item) for item in root.findall(".//item")]
        except (urllib.error.URLError, urllib.error.HTTPError, ET.ParseError, RuntimeError, ValueError) as exc:
            last_error = exc
            if attempt >= retry_count:
                break
            time.sleep(0.5 * attempt)
    raise RuntimeError(
        f"Failed to fetch KASI lunar calendar {request.year:04d}-{request.month:02d}"
    ) from last_error


def _filter_and_sort_rows(
    rows: Iterable[Dict[str, Any]],
    *,
    start: date,
    end: date,
) -> List[Dict[str, Any]]:
    filtered = [
        row
        for row in rows
        if start <= _parse_date(row["solar_date"]) <= end
    ]
    filtered.sort(key=lambda item: item["solar_date"])
    expected_dates = [day.isoformat() for day in _iter_dates(start, end)]
    actual_dates = [row["solar_date"] for row in filtered]
    if actual_dates != expected_dates:
        missing = sorted(set(expected_dates) - set(actual_dates))
        extra = sorted(set(actual_dates) - set(expected_dates))
        raise ValueError(
            "KASI reference rows are not contiguous: "
            f"missing={missing[:10]}, extra={extra[:10]}"
        )
    return filtered


def build_rows(
    *,
    start_date: str,
    end_date: str,
    service_key: Optional[str] = None,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> Tuple[List[bytes], Dict[str, Any]]:
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if end < start:
        raise ValueError("end_date must be greater than or equal to start_date")

    key = load_service_key(service_key)
    month_requests = list(_iter_month_requests(start, end))
    fetched_rows: List[Dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(fetch_kasi_month, request, service_key=key)
            for request in month_requests
        ]
        for future in concurrent.futures.as_completed(futures):
            fetched_rows.extend(future.result())

    records = _filter_and_sort_rows(fetched_rows, start=start, end=end)
    row_bytes = [
        (json.dumps(record, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        for record in records
    ]
    rows_sha256 = hashlib.sha256(b"".join(row_bytes)).hexdigest()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    metadata = {
        "schema_version": 2,
        "table_id": TABLE_ID,
        "description": "KASI official solar-date keyed Korean lunar/solar reference table.",
        "source": SOURCE,
        "range": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
        "row_count": len(row_bytes),
        "rows_sha256": rows_sha256,
        "generated_at": generated_at,
        "retrieved_at": generated_at,
        "generated_by": "python -m app.tools.build_lunar_reference_table",
        "notes": [
            "This table is generated from the official KASI data.go.kr lunisolar calendar API.",
            "Tests verify the checked-in file hash and structure without calling KASI.",
            "Regeneration is an explicit maintenance action and requires KASI_SERVICE_KEY.",
        ],
    }
    return row_bytes, metadata


def write_table(
    *,
    rows_path: Path = DEFAULT_ROWS_PATH,
    meta_path: Path = DEFAULT_META_PATH,
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
    service_key: Optional[str] = None,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> Dict[str, Any]:
    rows, metadata = build_rows(
        start_date=start_date,
        end_date=end_date,
        service_key=service_key,
        max_workers=max_workers,
    )
    rows_path.parent.mkdir(parents=True, exist_ok=True)
    rows_path.write_bytes(b"".join(rows))
    meta_path.write_text(
        json.dumps(metadata, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return metadata


def _validate_checked_in_rows(rows: List[Dict[str, Any]], metadata: Dict[str, Any]) -> None:
    expected_count = int(metadata["row_count"])
    if len(rows) != expected_count:
        raise ValueError(f"Expected {expected_count} rows, got {len(rows)}")

    start = _parse_date(metadata["range"]["start_date"])
    end = _parse_date(metadata["range"]["end_date"])
    expected_dates = [day.isoformat() for day in _iter_dates(start, end)]
    actual_dates = [row["solar_date"] for row in rows]
    if actual_dates != expected_dates:
        raise ValueError("Checked-in lunar reference table is not contiguous by solar date")

    lunar_keys = {
        (
            row["lunar_year"],
            row["lunar_month"],
            row["lunar_day"],
            row["is_lunar_leap_month"],
        )
        for row in rows
    }
    if len(lunar_keys) != expected_count:
        raise ValueError("Checked-in lunar reference table contains duplicate lunar keys")


def check_table(
    *,
    rows_path: Path = DEFAULT_ROWS_PATH,
    meta_path: Path = DEFAULT_META_PATH,
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
) -> Dict[str, Any]:
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    rows_bytes = rows_path.read_bytes()
    file_hash = hashlib.sha256(rows_bytes).hexdigest()
    rows = [json.loads(line.decode("utf-8")) for line in rows_bytes.splitlines()]
    _validate_checked_in_rows(rows, metadata)

    result = {
        "table_id": metadata.get("table_id"),
        "row_count": metadata.get("row_count"),
        "metadata_hash": metadata.get("rows_sha256"),
        "file_hash": file_hash,
        "hash_matches_metadata": file_hash == metadata.get("rows_sha256"),
        "row_count_matches_range": metadata.get("row_count")
        == (_parse_date(end_date) - _parse_date(start_date)).days + 1,
        "range_matches_expected": metadata.get("range")
        == {"start_date": start_date, "end_date": end_date},
        "source_name": metadata.get("source", {}).get("name"),
    }
    if not all(
        [
            result["hash_matches_metadata"],
            result["row_count_matches_range"],
            result["range_matches_expected"],
            result["table_id"] == TABLE_ID,
        ]
    ):
        raise SystemExit(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result


def verify_table_with_kasi(
    *,
    rows_path: Path = DEFAULT_ROWS_PATH,
    start_date: str,
    end_date: str,
    service_key: Optional[str] = None,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> Dict[str, Any]:
    generated_rows, _metadata = build_rows(
        start_date=start_date,
        end_date=end_date,
        service_key=service_key,
        max_workers=max_workers,
    )
    generated = {
        json.loads(line.decode("utf-8"))["solar_date"]: json.loads(line.decode("utf-8"))
        for line in generated_rows
    }
    checked_in_rows = [
        json.loads(line.decode("utf-8"))
        for line in rows_path.read_bytes().splitlines()
    ]
    checked_in = {
        row["solar_date"]: row
        for row in checked_in_rows
        if start_date <= row["solar_date"] <= end_date
    }
    mismatches = []
    for solar_date, expected in generated.items():
        actual = checked_in.get(solar_date)
        if actual != expected:
            mismatches.append(
                {
                    "solar_date": solar_date,
                    "checked_in": actual,
                    "kasi": expected,
                }
            )
    return {
        "start_date": start_date,
        "end_date": end_date,
        "compared": len(generated),
        "mismatch_count": len(mismatches),
        "mismatch_samples": mismatches[:20],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or verify the KASI lunar reference table.")
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", default=DEFAULT_END_DATE)
    parser.add_argument("--service-key", default=None, help="KASI service key. Prefer environment variables.")
    parser.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS)
    parser.add_argument("--check", action="store_true", help="Verify the checked-in table without network access.")
    parser.add_argument(
        "--verify-with-kasi",
        action="store_true",
        help="Compare the checked-in rows for the selected date range against live KASI API data.",
    )
    args = parser.parse_args()

    if args.check:
        payload = check_table(start_date=args.start_date, end_date=args.end_date)
    elif args.verify_with_kasi:
        payload = verify_table_with_kasi(
            start_date=args.start_date,
            end_date=args.end_date,
            service_key=args.service_key,
            max_workers=args.max_workers,
        )
    else:
        metadata = write_table(
            start_date=args.start_date,
            end_date=args.end_date,
            service_key=args.service_key,
            max_workers=args.max_workers,
        )
        payload = {
            "rows_path": str(DEFAULT_ROWS_PATH),
            "meta_path": str(DEFAULT_META_PATH),
            "row_count": metadata["row_count"],
            "rows_sha256": metadata["rows_sha256"],
            "source_name": metadata["source"]["name"],
        }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
