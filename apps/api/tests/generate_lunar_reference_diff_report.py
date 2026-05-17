"""Generate a lunar/solar reference diff report for accuracy review."""

from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from lunar_python import Solar

from app.domain.saju.reference_calendar import lookup_lunar_reference_by_solar_date


TESTS_DIR = Path(__file__).resolve().parent
REPORT_PATH = TESTS_DIR / "reports" / "lunar_reference_diff_report.md"
DEFAULT_REVIEW_RANGES: Tuple[Tuple[str, str], ...] = (
    ("1914-06-20", "1914-07-25"),
    ("1956-12-25", "1957-01-05"),
    ("2023-03-20", "2023-04-10"),
    ("2024-02-01", "2024-02-15"),
    ("1988-05-15", "1988-05-25"),
)
COMPARE_FIELDS = (
    "lunar_year",
    "lunar_month",
    "lunar_day",
    "is_lunar_leap_month",
    "day_ganzhi_hanja",
)


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _iter_dates(start_date: date, end_date: date) -> Iterable[date]:
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def _reference_table_snapshot(day: date) -> Optional[Dict[str, Any]]:
    record = lookup_lunar_reference_by_solar_date(day)
    if record is None:
        return None

    return {
        "lunar_year": record.lunar_year,
        "lunar_month": record.lunar_month,
        "lunar_day": record.lunar_day,
        "is_lunar_leap_month": record.is_lunar_leap_month,
        "day_ganzhi_hanja": record.day_ganzhi_hanja,
    }


def _lunar_python_snapshot(day: date) -> Dict[str, Any]:
    lunar = Solar.fromYmd(day.year, day.month, day.day).getLunar()
    lunar_month = lunar.getMonth()
    return {
        "lunar_year": lunar.getYear(),
        "lunar_month": abs(lunar_month),
        "lunar_day": lunar.getDay(),
        "is_lunar_leap_month": lunar_month < 0,
        "day_ganzhi_hanja": lunar.getDayInGanZhi(),
    }


def _changed_fields(
    reference: Dict[str, Any],
    candidate: Dict[str, Any],
) -> List[str]:
    return [
        field_name
        for field_name in COMPARE_FIELDS
        if reference.get(field_name) != candidate.get(field_name)
    ]


def _format_snapshot(snapshot: Dict[str, Any]) -> str:
    leap = "leap" if snapshot["is_lunar_leap_month"] else "regular"
    return (
        f"{snapshot['lunar_year']:04d}-{snapshot['lunar_month']:02d}-"
        f"{snapshot['lunar_day']:02d} {leap} {snapshot['day_ganzhi_hanja']}"
    )


def _build_mismatch_ranges(samples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    lunar_date_samples = [
        item
        for item in samples
        if any(
            field_name in item["changed_fields"]
            for field_name in ("lunar_year", "lunar_month", "lunar_day", "is_lunar_leap_month")
        )
    ]
    ranges: List[Dict[str, Any]] = []
    current_range: Optional[Dict[str, Any]] = None
    previous_day: Optional[date] = None

    for item in lunar_date_samples:
        current_day = _parse_date(item["solar_date"])
        if current_range is None or previous_day is None or current_day != previous_day + timedelta(days=1):
            current_range = {
                "start": item["solar_date"],
                "end": item["solar_date"],
                "count": 1,
            }
            ranges.append(current_range)
        else:
            current_range["end"] = item["solar_date"]
            current_range["count"] += 1
        previous_day = current_day

    return ranges


def collect_lunar_reference_diff_data(
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    sample_limit: int = 40,
) -> Dict[str, Any]:
    if (start_date is None) != (end_date is None):
        raise ValueError("start_date and end_date must be provided together")

    if start_date is not None and end_date is not None:
        ranges = [(_parse_date(start_date), _parse_date(end_date))]
    else:
        ranges = [(_parse_date(start), _parse_date(end)) for start, end in DEFAULT_REVIEW_RANGES]

    for start, end in ranges:
        if end < start:
            raise ValueError("end_date must be greater than or equal to start_date")

    total_compared = 0
    skipped_dates: List[str] = []
    field_counts: Counter[str] = Counter()
    mismatch_samples: List[Dict[str, Any]] = []

    for start, end in ranges:
        for day in _iter_dates(start, end):
            reference = _reference_table_snapshot(day)
            if reference is None:
                skipped_dates.append(day.isoformat())
                continue

            candidate = _lunar_python_snapshot(day)
            total_compared += 1
            changed = _changed_fields(reference, candidate)
            if not changed:
                continue

            field_counts.update(changed)
            mismatch_samples.append(
                {
                    "solar_date": day.isoformat(),
                    "changed_fields": changed,
                    "reference_table": reference,
                    "lunar_python": candidate,
                }
            )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ranges": [
            {"start_date": start.isoformat(), "end_date": end.isoformat()}
            for start, end in ranges
        ],
        "source_of_truth_candidate": "checked-in kasi_lunar_calendar_1900_2050 table",
        "compared_candidate": "lunar_python",
        "total_compared": total_compared,
        "skipped_dates": skipped_dates,
        "mismatch_count": len(mismatch_samples),
        "field_mismatch_counts": dict(sorted(field_counts.items())),
        "mismatch_ranges": _build_mismatch_ranges(mismatch_samples),
        "mismatch_samples": mismatch_samples[:sample_limit],
    }


def build_markdown_report(data: Dict[str, Any]) -> str:
    lines = [
        "# Lunar Reference Diff Report",
        "",
        f"- Generated at: `{data['generated_at']}`",
        "- Ranges: "
        + ", ".join(
            f"`{item['start_date']}` to `{item['end_date']}`"
            for item in data["ranges"]
        ),
        "- Reference candidate: checked-in `kasi_lunar_calendar_1900_2050` table",
        "- Compared candidate: `lunar_python`",
        "- Purpose: diagnostic only. This report does not change production primary pillars.",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
        f"| Total compared dates | {data['total_compared']} |",
        f"| Mismatch dates | {data['mismatch_count']} |",
        f"| Skipped dates | {len(data['skipped_dates'])} |",
        "",
        "## Field Mismatches",
        "",
        "| Field | Count |",
        "| --- | ---: |",
    ]
    for field_name, count in data["field_mismatch_counts"].items():
        lines.append(f"| {field_name} | {count} |")
    if not data["field_mismatch_counts"]:
        lines.append("| none | 0 |")

    lines.extend(["", "## Lunar Date Mismatch Ranges", ""])
    if data["mismatch_ranges"]:
        lines.extend(["| Start | End | Days |", "| --- | --- | ---: |"])
        for item in data["mismatch_ranges"][:80]:
            lines.append(f"| {item['start']} | {item['end']} | {item['count']} |")
        if len(data["mismatch_ranges"]) > 80:
            lines.append(f"| ... | ... | {len(data['mismatch_ranges']) - 80} more ranges |")
    else:
        lines.append("None.")

    lines.extend(["", "## Sample Mismatches", ""])
    if data["mismatch_samples"]:
        lines.extend(
            [
                "| Solar date | Changed fields | reference table | lunar_python |",
                "| --- | --- | --- | --- |",
            ]
        )
        for item in data["mismatch_samples"]:
            lines.append(
                "| "
                + " | ".join(
                    [
                        item["solar_date"],
                        ", ".join(item["changed_fields"]),
                        _format_snapshot(item["reference_table"]),
                        _format_snapshot(item["lunar_python"]),
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
            "- Use this report to decide where official KASI fixtures are needed first.",
            "- If KASI agrees with the checked-in table, promote those fields to hard reference cases.",
            "- Do not use this report by itself to replace year/month/hour pillar logic.",
            "",
            "## Regenerate",
            "",
            "```powershell",
            "cd apps/api",
            "python tests/generate_lunar_reference_diff_report.py",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(path: Path = REPORT_PATH) -> Dict[str, Any]:
    data = collect_lunar_reference_diff_data()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_markdown_report(data), encoding="utf-8")
    return data


def main() -> None:
    data = write_report()
    print(
        json.dumps(
            {
                "report_path": str(REPORT_PATH),
                "total_compared": data["total_compared"],
                "mismatch_count": data["mismatch_count"],
                "field_mismatch_counts": data["field_mismatch_counts"],
                "mismatch_range_count": len(data["mismatch_ranges"]),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
