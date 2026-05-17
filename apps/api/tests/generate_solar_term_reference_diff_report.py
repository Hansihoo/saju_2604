"""Generate a KASI solar-term vs lunar_python timestamp diff report.

This report is diagnostic only. It compares checked-in reference timestamps
against lunar_python's solar-term table and does not promote any provider.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from lunar_python import Solar


TESTS_DIR = Path(__file__).resolve().parent
API_ROOT = TESTS_DIR.parent
REPORT_PATH = TESTS_DIR / "reports" / "solar_term_reference_diff_report.md"
COMMON_ROWS_PATH = (
    API_ROOT
    / "app"
    / "domain"
    / "saju"
    / "data"
    / "solar_terms_reference"
    / "kasi_solar_terms_common_years.jsonl"
)
DEFAULT_SAMPLE_LIMIT = 40


def _load_reference_rows(rows_path: Path = COMMON_ROWS_PATH) -> List[Dict[str, Any]]:
    return [
        json.loads(line)
        for line in rows_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _parse_reference_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=None)


def _solar_to_datetime(value: Any) -> datetime:
    return datetime(
        value.getYear(),
        value.getMonth(),
        value.getDay(),
        value.getHour(),
        value.getMinute(),
        value.getSecond(),
    )


def _nearest_lunar_python_solar_term(reference_dt: datetime) -> datetime:
    lunar = Solar.fromYmd(reference_dt.year, reference_dt.month, reference_dt.day).getLunar()
    candidates = [
        _solar_to_datetime(solar)
        for solar in lunar.getJieQiTable().values()
    ]
    return min(candidates, key=lambda item: abs((item - reference_dt).total_seconds()))


def _filter_rows(
    rows: Iterable[Dict[str, Any]],
    *,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    jeolgi_only: bool = False,
) -> Iterable[Dict[str, Any]]:
    for row in rows:
        year = int(row["year"])
        if start_year is not None and year < start_year:
            continue
        if end_year is not None and year > end_year:
            continue
        if jeolgi_only and row.get("term_type") != "jeolgi":
            continue
        yield row


def _bucket_abs_delta(abs_seconds: int) -> str:
    if abs_seconds <= 60:
        return "<=1m"
    if abs_seconds <= 30 * 60:
        return "<=30m"
    if abs_seconds <= 60 * 60:
        return "<=1h"
    if abs_seconds <= 2 * 60 * 60:
        return "<=2h"
    return ">2h"


def collect_solar_term_reference_diff_data(
    *,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    jeolgi_only: bool = False,
    sample_limit: int = DEFAULT_SAMPLE_LIMIT,
) -> Dict[str, Any]:
    rows = list(
        _filter_rows(
            _load_reference_rows(),
            start_year=start_year,
            end_year=end_year,
            jeolgi_only=jeolgi_only,
        )
    )
    deltas: List[Dict[str, Any]] = []
    bucket_counts: Counter[str] = Counter()
    term_counts: Counter[str] = Counter()
    term_abs_delta_totals: Counter[str] = Counter()

    for row in rows:
        reference_dt = _parse_reference_datetime(row["solar_term_datetime"])
        lunar_python_dt = _nearest_lunar_python_solar_term(reference_dt)
        delta_seconds = int((lunar_python_dt - reference_dt).total_seconds())
        abs_delta_seconds = abs(delta_seconds)
        bucket_counts[_bucket_abs_delta(abs_delta_seconds)] += 1
        term_counts[row["term_id"]] += 1
        term_abs_delta_totals[row["term_id"]] += abs_delta_seconds
        deltas.append(
            {
                "year": int(row["year"]),
                "term_id": row["term_id"],
                "term_type": row["term_type"],
                "reference_datetime": row["solar_term_datetime"],
                "lunar_python_datetime": lunar_python_dt.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
                "delta_seconds": delta_seconds,
                "abs_delta_seconds": abs_delta_seconds,
                "source_method": row.get("source", {}).get("source_method"),
            }
        )

    max_abs_delta = max((item["abs_delta_seconds"] for item in deltas), default=0)
    average_abs_delta = (
        sum(item["abs_delta_seconds"] for item in deltas) / len(deltas)
        if deltas
        else 0.0
    )
    by_largest_delta = sorted(deltas, key=lambda item: item["abs_delta_seconds"], reverse=True)
    average_by_term = {
        term_id: round(term_abs_delta_totals[term_id] / term_counts[term_id], 2)
        for term_id in sorted(term_counts)
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "range": {
            "start_year": start_year,
            "end_year": end_year,
        },
        "jeolgi_only": jeolgi_only,
        "reference_candidate": "checked-in KASI solar-term common-years table",
        "compared_candidate": "lunar_python JieQi table nearest timestamp",
        "total_compared": len(deltas),
        "max_abs_delta_seconds": max_abs_delta,
        "average_abs_delta_seconds": round(average_abs_delta, 2),
        "delta_bucket_counts": dict(sorted(bucket_counts.items())),
        "average_abs_delta_seconds_by_term": average_by_term,
        "largest_delta_samples": by_largest_delta[:sample_limit],
    }


def _format_seconds(seconds: int) -> str:
    sign = "-" if seconds < 0 else ""
    abs_seconds = abs(seconds)
    minutes, second = divmod(abs_seconds, 60)
    hours, minute = divmod(minutes, 60)
    if hours:
        return f"{sign}{hours}h {minute}m {second}s"
    if minute:
        return f"{sign}{minute}m {second}s"
    return f"{sign}{second}s"


def build_markdown_report(data: Dict[str, Any]) -> str:
    start_year = data["range"]["start_year"] or "first"
    end_year = data["range"]["end_year"] or "last"
    lines = [
        "# Solar-Term Reference Diff Report",
        "",
        f"- Generated at: `{data['generated_at']}`",
        f"- Year range: `{start_year}` to `{end_year}`",
        f"- Jeolgi only: `{data['jeolgi_only']}`",
        "- Reference candidate: checked-in KASI solar-term table",
        "- Compared candidate: nearest `lunar_python` JieQi timestamp",
        "- Purpose: diagnostic only. This report does not change primary pillars or luck-cycle boundaries.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Total compared rows | {data['total_compared']} |",
        f"| Max absolute delta | {_format_seconds(data['max_abs_delta_seconds'])} |",
        f"| Average absolute delta seconds | {data['average_abs_delta_seconds']} |",
        "",
        "## Delta Buckets",
        "",
        "| Bucket | Count |",
        "| --- | ---: |",
    ]
    for bucket, count in data["delta_bucket_counts"].items():
        lines.append(f"| {bucket} | {count} |")
    if not data["delta_bucket_counts"]:
        lines.append("| none | 0 |")

    lines.extend(["", "## Average Absolute Delta By Term", ""])
    if data["average_abs_delta_seconds_by_term"]:
        lines.extend(["| Term | Average absolute delta seconds |", "| --- | ---: |"])
        for term_id, seconds in data["average_abs_delta_seconds_by_term"].items():
            lines.append(f"| {term_id} | {seconds} |")
    else:
        lines.append("None.")

    lines.extend(["", "## Largest Delta Samples", ""])
    if data["largest_delta_samples"]:
        lines.extend(
            [
                "| Year | Term | Type | KASI reference | lunar_python | Delta | Source |",
                "| ---: | --- | --- | --- | --- | ---: | --- |",
            ]
        )
        for item in data["largest_delta_samples"]:
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(item["year"]),
                        item["term_id"],
                        item["term_type"],
                        item["reference_datetime"],
                        item["lunar_python_datetime"],
                        _format_seconds(item["delta_seconds"]),
                        str(item["source_method"]),
                    ]
                )
                + " |"
            )
    else:
        lines.append("None.")

    lines.extend(
        [
            "",
            "## Review Notes",
            "",
            "- Review this before promoting a solar-term reference provider into primary calculation.",
            "- Large consistent offsets should be classified as timezone/provider convention differences first.",
            "- This report intentionally uses nearest timestamp matching so garbled term-name encoding cannot hide timestamp drift.",
            "",
            "## Regenerate",
            "",
            "```powershell",
            "cd apps/api",
            "python tests/generate_solar_term_reference_diff_report.py",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(path: Path = REPORT_PATH, *, start_year: Optional[int] = None, end_year: Optional[int] = None, jeolgi_only: bool = False) -> Dict[str, Any]:
    data = collect_solar_term_reference_diff_data(
        start_year=start_year,
        end_year=end_year,
        jeolgi_only=jeolgi_only,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_markdown_report(data), encoding="utf-8")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a solar-term reference diff report.")
    parser.add_argument("--start-year", type=int, default=None)
    parser.add_argument("--end-year", type=int, default=None)
    parser.add_argument("--jeolgi-only", action="store_true")
    args = parser.parse_args()

    data = write_report(
        start_year=args.start_year,
        end_year=args.end_year,
        jeolgi_only=args.jeolgi_only,
    )
    print(
        json.dumps(
            {
                "report_path": str(REPORT_PATH),
                "total_compared": data["total_compared"],
                "max_abs_delta_seconds": data["max_abs_delta_seconds"],
                "average_abs_delta_seconds": data["average_abs_delta_seconds"],
                "delta_bucket_counts": data["delta_bucket_counts"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
