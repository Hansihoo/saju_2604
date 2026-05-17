"""Collect KASI solar-term timestamp references in resumable batches.

This maintenance tool only builds checked-in reference data. It does not change
the primary saju calculation path.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[4]
API_ROOT = REPO_ROOT / "apps" / "api"
REFERENCE_DIR = API_ROOT / "app" / "domain" / "saju" / "data" / "solar_terms_reference"
TABLE_ID = "kasi_solar_terms_common_years"
DEFAULT_ROWS_PATH = REFERENCE_DIR / f"{TABLE_ID}.jsonl"
DEFAULT_META_PATH = REFERENCE_DIR / f"{TABLE_ID}.meta.json"
DEFAULT_MANIFEST_PATH = REFERENCE_DIR / f"{TABLE_ID}.manifest.json"
DEFAULT_LOG_PATH = REFERENCE_DIR / f"{TABLE_ID}.collection.log.jsonl"
DEFAULT_CALENDAR_DATA_URL = "https://astro.kasi.re.kr/life/post/calendarData"
DEFAULT_FILE_DOWNLOAD_URL = "https://astro.kasi.re.kr/web-front/comm/fileDownload"
DEFAULT_ALMANAC_ARCHIVE_URL = "https://astro.kasi.re.kr/almanac/pageView/1"
DEFAULT_KASI_PUBLICATION_URL = "https://www.kasi.re.kr/kor/publication/post/publication"
DEFAULT_KASI_PUBLICATION_FILE_DOWNLOAD_URL = "https://www.kasi.re.kr/web-front/comm/fileDownload"
DEFAULT_COMMON_YEARS = list(range(2021, 2028))
PDF_ALMANAC_URLS = {
    2020: "https://astro.kasi.re.kr/file/astro_almanac_pdf/20200624134708539.pdf",
}
PUBLICATION_PDF_ALMANACS = {
    2018: {
        "stored_name": "1508828511874_1.pdf",
        "display_name": "2018역서_PDF.pdf",
        "page_url": f"{DEFAULT_KASI_PUBLICATION_URL}?cPage=2&clsf_cd=pub005",
    },
    2019: {
        "stored_name": "1542677022204_1.pdf",
        "display_name": "역서2019.pdf",
        "page_url": f"{DEFAULT_KASI_PUBLICATION_URL}?cPage=1&clsf_cd=pub005",
    },
}

SOURCE = {
    "type": "official_kasi_sources",
    "name": "KASI solar-term timestamp reference sources",
    "provider": "Korea Astronomy and Space Science Institute",
    "calendar_data_url": DEFAULT_CALENDAR_DATA_URL,
    "almanac_archive_url": DEFAULT_ALMANAC_ARCHIVE_URL,
    "publication_url": DEFAULT_KASI_PUBLICATION_URL,
    "official_almanac_url": "https://astro.kasi.re.kr/life/post/almanac",
}

SOLAR_TERMS: List[Tuple[str, str, int, str]] = [
    ("sohan", "소한", 0, "junggi"),
    ("daehan", "대한", 1, "junggi"),
    ("ipchun", "입춘", 2, "jeolgi"),
    ("usu", "우수", 3, "junggi"),
    ("gyeongchip", "경칩", 4, "jeolgi"),
    ("chunbun", "춘분", 5, "junggi"),
    ("cheongmyeong", "청명", 6, "jeolgi"),
    ("gogu", "곡우", 7, "junggi"),
    ("ipha", "입하", 8, "jeolgi"),
    ("soman", "소만", 9, "junggi"),
    ("mangjong", "망종", 10, "jeolgi"),
    ("haji", "하지", 11, "junggi"),
    ("soseo", "소서", 12, "jeolgi"),
    ("daeseo", "대서", 13, "junggi"),
    ("ipchu", "입추", 14, "jeolgi"),
    ("cheoseo", "처서", 15, "junggi"),
    ("baengno", "백로", 16, "jeolgi"),
    ("chubun", "추분", 17, "junggi"),
    ("hallo", "한로", 18, "jeolgi"),
    ("sanggang", "상강", 19, "junggi"),
    ("ipdong", "입동", 20, "jeolgi"),
    ("soseol", "소설", 21, "junggi"),
    ("daeseol", "대설", 22, "jeolgi"),
    ("dongji", "동지", 23, "junggi"),
]
TERM_BY_NAME = {name: (term_id, index, term_type) for term_id, name, index, term_type in SOLAR_TERMS}
TERM_NAMES_PATTERN = "|".join(re.escape(name) for _term_id, name, _index, _type in SOLAR_TERMS)
TERM_ROW_PATTERN = re.compile(
    rf"(?P<name>{TERM_NAMES_PATTERN})\s+"
    r"(?P<month>\d{1,2})\s+"
    r"(?P<day>\d{1,2})\s+"
    r"(?P<hour>\d{1,2})\s+"
    r"(?P<minute>\d{1,2})"
)
ARCHIVE_TERM_ROW_PATTERN = re.compile(
    rf"(?P<name>{TERM_NAMES_PATTERN})\s+"
    r"(?P<longitude>\d{1,3})\s+"
    r"(?P<month>\d{1,2})월(?P<day>\d{1,2})일\s+"
    r"(?P<hour>\d{1,2})시\s*(?P<minute>\d{1,2})분"
)
PDF_TABLE_TERM_ROW_PATTERN = re.compile(
    rf"(?P<name>{TERM_NAMES_PATTERN})\s+"
    r"(?P<longitude>\d{1,3})\s+"
    r"(?P<month>\d{1,2})\s+"
    r"(?P<day>\d{1,2})\s+"
    r"(?P<hour>\d{1,2})\s+"
    r"(?P<minute>\d{1,2})"
)
DOWNLOAD_LINK_PATTERN = re.compile(
    r"downLocation\('(?P<stored>[^']+)'\s*,\s*'(?P<display>[^']+)'(?:\s*,\s*'(?P<folder>[^']*)')?\)"
)
GENERATED_AT_PATTERN = re.compile(
    r"자료생성\(V(?P<version>[^)]*)\):\s*"
    r"(?P<year>\d{4})년\s*(?P<month>\d{1,2})월\s*(?P<day>\d{1,2})일\s*"
    r"(?P<hour>\d{1,2})시\s*(?P<minute>\d{1,2})분"
)


@dataclass(frozen=True)
class SourcePayload:
    year: int
    text: str
    page_url: str
    source_method: str
    download_stored_name: Optional[str] = None
    download_display_name: Optional[str] = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _request_text(url: str, *, timeout_seconds: int = 20) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "saju-kasi-solar-term-builder/1.0"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8")


def _post_file_download(
    *,
    stored_name: str,
    display_name: str,
    folder: Optional[str],
    timeout_seconds: int = 20,
) -> str:
    body = urllib.parse.urlencode(
        {
            "file1": display_name,
            "file2": stored_name,
            "path": folder or "/file",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        DEFAULT_FILE_DOWNLOAD_URL,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "saju-kasi-solar-term-builder/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8")


def _post_binary_file_download(
    *,
    download_url: str,
    stored_name: str,
    display_name: str,
    folder: Optional[str],
    timeout_seconds: int = 60,
) -> bytes:
    body = urllib.parse.urlencode(
        {
            "file1": display_name,
            "file2": stored_name,
            "path": folder or "/file",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        download_url,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "saju-kasi-solar-term-builder/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return response.read()


def _strip_html(value: str) -> str:
    text = re.sub(r"<script\b.*?</script>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text)


def _extract_calendar_data_generated_at(text: str) -> Optional[str]:
    match = GENERATED_AT_PATTERN.search(text)
    if not match:
        return None
    return (
        f"{int(match.group('year')):04d}-{int(match.group('month')):02d}-{int(match.group('day')):02d}"
        f"T{int(match.group('hour')):02d}:{int(match.group('minute')):02d}:00+09:00"
    )


def fetch_kasi_calendar_data_year(year: int, *, timeout_seconds: int = 20) -> SourcePayload:
    page_url = f"{DEFAULT_CALENDAR_DATA_URL}?year={year}"
    html_text = _request_text(page_url, timeout_seconds=timeout_seconds)
    download = DOWNLOAD_LINK_PATTERN.search(html_text)
    if download:
        stored_name = download.group("stored")
        display_name = download.group("display")
        folder = download.group("folder")
        return SourcePayload(
            year=year,
            text=_post_file_download(
                stored_name=stored_name,
                display_name=display_name,
                folder=folder,
                timeout_seconds=timeout_seconds,
            ),
            page_url=page_url,
            source_method="calendar_data_download_txt",
            download_stored_name=stored_name,
            download_display_name=display_name,
        )
    return SourcePayload(
        year=year,
        text=_strip_html(html_text),
        page_url=page_url,
        source_method="calendar_data_html",
    )


def fetch_kasi_almanac_archive_year(year: int, *, timeout_seconds: int = 20) -> SourcePayload:
    html_text = _request_text(DEFAULT_ALMANAC_ARCHIVE_URL, timeout_seconds=timeout_seconds)
    text = _strip_html(html_text)
    section_start = text.find(f"{year}년도 일력자료")
    if section_start < 0:
        raise ValueError(f"KASI almanac archive page does not contain {year}")
    next_section = re.search(r"20\d{2}년도 일력자료", text[section_start + 1 :])
    section_end = section_start + 1 + next_section.start() if next_section else len(text)
    section = text[section_start:section_end]
    if "24절기와 잡절" not in section:
        raise ValueError(f"KASI almanac archive section for {year} has no solar-term table")
    return SourcePayload(
        year=year,
        text=section,
        page_url=DEFAULT_ALMANAC_ARCHIVE_URL,
        source_method="almanac_archive_html",
    )


def fetch_kasi_pdf_almanac_year(year: int, *, timeout_seconds: int = 60) -> SourcePayload:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("pypdf is required to extract KASI almanac PDF solar-term tables") from exc

    direct_url = PDF_ALMANAC_URLS.get(year)
    publication_pdf = PUBLICATION_PDF_ALMANACS.get(year)
    if not direct_url and not publication_pdf:
        raise ValueError(f"No configured KASI almanac PDF URL for {year}")
    if direct_url:
        page_url = direct_url
        stored_name = None
        display_name = f"{year} KASI astronomical almanac PDF"
        request = urllib.request.Request(direct_url, headers={"User-Agent": "saju-kasi-solar-term-builder/1.0"})
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            pdf_bytes = response.read()
    else:
        page_url = str(publication_pdf["page_url"])
        stored_name = str(publication_pdf["stored_name"])
        display_name = str(publication_pdf["display_name"])
        pdf_bytes = _post_binary_file_download(
            download_url=DEFAULT_KASI_PUBLICATION_FILE_DOWNLOAD_URL,
            stored_name=stored_name,
            display_name=display_name,
            folder="/file",
            timeout_seconds=timeout_seconds,
        )
    reader = PdfReader(BytesIO(pdf_bytes))
    page_texts = []
    for page in reader.pages[:20]:
        text = page.extract_text() or ""
        if text:
            page_texts.append(text)
    return SourcePayload(
        year=year,
        text="\n".join(page_texts),
        page_url=page_url,
        source_method="almanac_pdf",
        download_stored_name=stored_name,
        download_display_name=display_name,
    )


def fetch_kasi_solar_terms_year(year: int) -> SourcePayload:
    if 2011 <= year <= 2017:
        return fetch_kasi_almanac_archive_year(year)
    if year in PDF_ALMANAC_URLS or year in PUBLICATION_PDF_ALMANACS:
        return fetch_kasi_pdf_almanac_year(year)
    return fetch_kasi_calendar_data_year(year)


def _row_source(payload: SourcePayload, normalized_text: str) -> Dict[str, Any]:
    if payload.source_method == "almanac_archive_html":
        return {
            "type": "kasi_almanac_archive",
            "name": "KASI almanac archive solar terms",
            "provider": SOURCE["provider"],
            "url": payload.page_url,
            "source_method": payload.source_method,
            "download_stored_name": payload.download_stored_name,
            "download_display_name": None,
            "calendar_data_generated_at": None,
            "official_almanac_url": payload.page_url,
            "official_almanac_confirmation": "source",
        }
    if payload.source_method == "almanac_pdf":
        return {
            "type": "kasi_almanac_pdf",
            "name": "KASI astronomical almanac PDF solar terms",
            "provider": SOURCE["provider"],
            "url": payload.page_url,
            "source_method": payload.source_method,
            "download_stored_name": None,
            "download_display_name": payload.download_display_name,
            "calendar_data_generated_at": None,
            "official_almanac_url": payload.page_url,
            "official_almanac_confirmation": "source",
        }
    return {
        "type": "kasi_calendar_data",
        "name": "KASI calendarData solar terms",
        "provider": SOURCE["provider"],
        "url": payload.page_url,
        "source_method": payload.source_method,
        "download_stored_name": payload.download_stored_name,
        "download_display_name": payload.download_display_name,
        "calendar_data_generated_at": _extract_calendar_data_generated_at(normalized_text),
        "official_almanac_url": f"{SOURCE['official_almanac_url']}?year={payload.year}",
        "official_almanac_confirmation": "pending",
    }


def _normalize_term_name_spacing(value: str) -> str:
    normalized = value
    for _term_id, name, _index, _term_type in SOLAR_TERMS:
        spaced_name = r"\s*".join(re.escape(char) for char in name)
        normalized = re.sub(spaced_name, name, normalized)
    return normalized


def _normalize_clock_fields(year: int, month: int, day: int, hour: int, minute: int) -> Tuple[int, int, int, int]:
    if not 0 <= hour <= 24:
        raise ValueError(f"Invalid solar-term hour for {year}: {hour}")
    if not 0 <= minute <= 60:
        raise ValueError(f"Invalid solar-term minute for {year}: {minute}")

    extra_days = 1 if hour == 24 else 0
    base_hour = 0 if hour == 24 else hour
    normalized_minute = 0 if minute == 60 else minute
    extra_hours = 1 if minute == 60 else 0
    normalized = datetime(year, month, day, base_hour, normalized_minute) + timedelta(
        days=extra_days,
        hours=extra_hours,
    )
    return normalized.month, normalized.day, normalized.hour, normalized.minute


def parse_solar_terms_from_text(payload: SourcePayload) -> List[Dict[str, Any]]:
    normalized_text = _strip_html(payload.text) if "<" in payload.text and ">" in payload.text else payload.text
    normalized_text = html.unescape(normalized_text)
    normalized_text = re.sub(r"\s+", " ", normalized_text)
    normalized_text = _normalize_term_name_spacing(normalized_text)
    matches = list(ARCHIVE_TERM_ROW_PATTERN.finditer(normalized_text))
    if len(matches) < 24:
        matches = list(PDF_TABLE_TERM_ROW_PATTERN.finditer(normalized_text))
    if len(matches) < 24:
        matches = list(TERM_ROW_PATTERN.finditer(normalized_text))
    if len(matches) < 24:
        raise ValueError(f"Expected at least 24 solar-term rows for {payload.year}, got {len(matches)}")

    rows_by_name: Dict[str, Dict[str, Any]] = {}
    for match in matches:
        name = match.group("name")
        if name in rows_by_name:
            continue
        term_id, term_index, term_type = TERM_BY_NAME[name]
        month = int(match.group("month"))
        day = int(match.group("day"))
        hour = int(match.group("hour"))
        minute = int(match.group("minute"))
        month, day, hour, minute = _normalize_clock_fields(payload.year, month, day, hour, minute)
        rows_by_name[name] = {
            "year": payload.year,
            "term_id": term_id,
            "term_name": name,
            "term_index": term_index,
            "term_type": term_type,
            "month": month,
            "day": day,
            "hour": hour,
            "minute": minute,
            "timezone_id": "Asia/Seoul",
            "utc_offset_minutes": 540,
            "solar_term_datetime": (
                f"{payload.year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:00+09:00"
            ),
            "source": _row_source(payload, normalized_text),
        }

    ordered_rows = [rows_by_name[name] for _term_id, name, _index, _type in SOLAR_TERMS if name in rows_by_name]
    if len(ordered_rows) != 24:
        missing = [name for _term_id, name, _index, _type in SOLAR_TERMS if name not in rows_by_name]
        raise ValueError(f"Solar-term rows for {payload.year} are incomplete: missing={missing}")
    return ordered_rows


def _row_bytes(rows: Sequence[Dict[str, Any]]) -> List[bytes]:
    return [
        (json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        for row in rows
    ]


def _read_rows(rows_path: Path) -> List[Dict[str, Any]]:
    if not rows_path.exists():
        return []
    return [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _read_manifest_statuses(manifest_path: Path) -> Dict[str, Any]:
    if not manifest_path.exists():
        return {}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    statuses = manifest.get("year_status", {})
    return statuses if isinstance(statuses, dict) else {}


def _append_log(log_path: Path, event: Dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ts": _utc_now(), **event}
    with log_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def parse_years(value: Optional[str]) -> List[int]:
    if not value:
        return DEFAULT_COMMON_YEARS[:]
    years: List[int] = []
    for part in value.split(","):
        stripped = part.strip()
        if not stripped:
            continue
        if "-" in stripped:
            start_text, end_text = stripped.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            if end < start:
                raise ValueError(f"Invalid year range: {stripped}")
            years.extend(range(start, end + 1))
        else:
            years.append(int(stripped))
    return sorted(dict.fromkeys(years))


def _validate_rows(rows: Sequence[Dict[str, Any]]) -> None:
    by_year: Dict[int, List[Dict[str, Any]]] = {}
    for row in rows:
        by_year.setdefault(int(row["year"]), []).append(row)

    for year, year_rows in by_year.items():
        if len(year_rows) != 24:
            raise ValueError(f"Expected 24 rows for {year}, got {len(year_rows)}")
        actual_order = [row["term_id"] for row in sorted(year_rows, key=lambda item: item["term_index"])]
        expected_order = [term_id for term_id, _name, _index, _type in SOLAR_TERMS]
        if actual_order != expected_order:
            raise ValueError(f"Unexpected solar-term order for {year}")
        for row in year_rows:
            expected_prefix = f"{year:04d}-{int(row['month']):02d}-{int(row['day']):02d}T"
            if not row["solar_term_datetime"].startswith(expected_prefix):
                raise ValueError(f"Datetime does not match date fields: {row}")


def _build_metadata(rows: Sequence[Dict[str, Any]], *, manifest_path: Path, log_path: Path) -> Dict[str, Any]:
    rows_digest = hashlib.sha256(b"".join(_row_bytes(rows))).hexdigest()
    years = sorted({int(row["year"]) for row in rows})
    generated_at = _utc_now()
    return {
        "schema_version": 1,
        "table_id": TABLE_ID,
        "description": "KASI-published solar-term timestamp reference table for high-traffic/common years.",
        "source": SOURCE,
        "timezone_id": "Asia/Seoul",
        "range": {
            "years": years,
            "start_year": years[0] if years else None,
            "end_year": years[-1] if years else None,
        },
        "terms_per_year": 24,
        "row_count": len(rows),
        "rows_sha256": rows_digest,
        "generated_at": generated_at,
        "retrieved_at": generated_at,
        "generated_by": "python -m app.tools.build_solar_term_reference_table",
        "manifest_path": _display_path(manifest_path),
        "log_path": _display_path(log_path),
        "notes": [
            "This table is reference data only and is not used by the primary calculation path yet.",
            "Rows are collected incrementally from KASI almanac archive HTML, annual almanac PDFs, and calendarData pages/downloads.",
            "official_almanac_confirmation remains pending for calendarData rows until the matching 월력요항/관보 source is parsed.",
            "Use --limit to collect a small batch and rerun later; completed years are skipped unless --refresh is set.",
        ],
    }


def _write_table_files(
    *,
    rows: Sequence[Dict[str, Any]],
    rows_path: Path,
    meta_path: Path,
    manifest_path: Path,
    log_path: Path,
) -> Dict[str, Any]:
    sorted_rows = sorted(rows, key=lambda item: (int(item["year"]), int(item["term_index"])))
    _validate_rows(sorted_rows)
    metadata = _build_metadata(sorted_rows, manifest_path=manifest_path, log_path=log_path)
    _atomic_write_text(rows_path, b"".join(_row_bytes(sorted_rows)).decode("utf-8"))
    _atomic_write_text(
        meta_path,
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return metadata


def _write_manifest(
    *,
    manifest_path: Path,
    rows: Sequence[Dict[str, Any]],
    requested_years: Sequence[int],
    statuses: Dict[str, Any],
    log_path: Path,
) -> Dict[str, Any]:
    year_counts: Dict[int, int] = {}
    for row in rows:
        year_counts[int(row["year"])] = year_counts.get(int(row["year"]), 0) + 1
    completed_years = sorted(year for year, count in year_counts.items() if count == 24)
    failed_years = sorted(int(year) for year, status in statuses.items() if status.get("status") == "failed")
    pending_years = [year for year in requested_years if year not in completed_years and year not in failed_years]
    manifest = {
        "schema_version": 1,
        "table_id": TABLE_ID,
        "last_run_at": _utc_now(),
        "requested_years": list(requested_years),
        "completed_years": completed_years,
        "pending_years": pending_years,
        "failed_years": failed_years,
        "year_status": statuses,
        "log_path": _display_path(log_path),
        "resume_note": "Rerun the build command; complete years are skipped unless --refresh is set.",
    }
    _atomic_write_text(
        manifest_path,
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return manifest


def _merge_year_rows(existing_rows: Sequence[Dict[str, Any]], new_rows: Sequence[Dict[str, Any]], year: int) -> List[Dict[str, Any]]:
    return [row for row in existing_rows if int(row["year"]) != year] + list(new_rows)


def collect_years(
    *,
    years: Sequence[int],
    limit: Optional[int] = None,
    refresh: bool = False,
    rows_path: Path = DEFAULT_ROWS_PATH,
    meta_path: Path = DEFAULT_META_PATH,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    log_path: Path = DEFAULT_LOG_PATH,
    fetcher: Callable[[int], SourcePayload] = fetch_kasi_solar_terms_year,
) -> Dict[str, Any]:
    requested_years = sorted(dict.fromkeys(int(year) for year in years))
    rows = _read_rows(rows_path)
    year_counts: Dict[int, int] = {}
    for row in rows:
        year_counts[int(row["year"])] = year_counts.get(int(row["year"]), 0) + 1
    completed = {year for year, count in year_counts.items() if count == 24}
    pending = [year for year in requested_years if refresh or year not in completed]
    if limit is not None:
        pending = pending[:limit]

    statuses: Dict[str, Any] = _read_manifest_statuses(manifest_path)
    for year in requested_years:
        if not refresh and year in completed:
            statuses.setdefault(str(year), {"status": "complete", "action": "existing_before_run"})
            statuses[str(year)]["last_action"] = "skipped_existing"
            _append_log(log_path, {"event": "year_skipped", "year": year, "reason": "already_complete"})

    for year in pending:
        _append_log(log_path, {"event": "year_start", "year": year})
        try:
            payload = fetcher(year)
            year_rows = parse_solar_terms_from_text(payload)
            rows = _merge_year_rows(rows, year_rows, year)
            metadata = _write_table_files(
                rows=rows,
                rows_path=rows_path,
                meta_path=meta_path,
                manifest_path=manifest_path,
                log_path=log_path,
            )
            statuses[str(year)] = {
                "status": "complete",
                "action": "fetched",
                "row_count": len(year_rows),
                "source_method": payload.source_method,
                "retrieved_at": _utc_now(),
                "rows_sha256": metadata["rows_sha256"],
            }
            _append_log(
                log_path,
                {
                    "event": "year_success",
                    "year": year,
                    "row_count": len(year_rows),
                    "source_method": payload.source_method,
                },
            )
        except Exception as exc:
            statuses[str(year)] = {
                "status": "failed",
                "error": str(exc),
                "error_type": type(exc).__name__,
            }
            _append_log(
                log_path,
                {
                    "event": "year_failed",
                    "year": year,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
            )
            break
        time.sleep(0.2)

    manifest = _write_manifest(
        manifest_path=manifest_path,
        rows=rows,
        requested_years=requested_years,
        statuses=statuses,
        log_path=log_path,
    )
    return {
        "rows_path": str(rows_path),
        "meta_path": str(meta_path),
        "manifest_path": str(manifest_path),
        "log_path": str(log_path),
        "completed_years": manifest["completed_years"],
        "pending_years": manifest["pending_years"],
        "failed_years": manifest["failed_years"],
        "row_count": len(rows),
    }


def check_table(
    *,
    rows_path: Path = DEFAULT_ROWS_PATH,
    meta_path: Path = DEFAULT_META_PATH,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> Dict[str, Any]:
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    rows_text = rows_path.read_text(encoding="utf-8")
    rows = [json.loads(line) for line in rows_text.splitlines() if line.strip()]
    _validate_rows(rows)
    file_hash = hashlib.sha256(rows_text.encode("utf-8")).hexdigest()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    result = {
        "table_id": metadata.get("table_id"),
        "row_count": len(rows),
        "metadata_row_count": metadata.get("row_count"),
        "file_hash": file_hash,
        "metadata_hash": metadata.get("rows_sha256"),
        "hash_matches_metadata": file_hash == metadata.get("rows_sha256"),
        "completed_years": manifest.get("completed_years", []),
        "pending_years": manifest.get("pending_years", []),
    }
    if not all(
        [
            result["table_id"] == TABLE_ID,
            result["row_count"] == result["metadata_row_count"],
            result["hash_matches_metadata"],
        ]
    ):
        raise SystemExit(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or verify KASI solar-term timestamp references.")
    parser.add_argument("--years", default=None, help="Comma/range list, e.g. 2024,2025-2027. Defaults to common recent years.")
    parser.add_argument("--limit", type=int, default=None, help="Collect only the first N pending years this run.")
    parser.add_argument("--refresh", action="store_true", help="Refetch years even if they already exist.")
    parser.add_argument("--check", action="store_true", help="Verify the checked-in table without network access.")
    args = parser.parse_args()

    if args.check:
        payload = check_table()
    else:
        payload = collect_years(
            years=parse_years(args.years),
            limit=args.limit,
            refresh=args.refresh,
        )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
