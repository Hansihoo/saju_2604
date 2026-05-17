"""Generate a full KASI iljin/day-pillar comparison report.

This is a maintenance diagnostic. It compares the checked-in KASI lunar
reference table against lunar_python for every solar date in the selected
range. The production day-pillar gan-zhi uses the KASI table when the
requested date is covered, so this report verifies that promotion boundary.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from lunar_python import Solar

from app.domain.saju.reference_calendar import load_lunar_reference_table


TESTS_DIR = Path(__file__).resolve().parent
REPORT_PATH = TESTS_DIR / "reports" / "iljin_reference_diff_report.md"
DEFAULT_SAMPLE_LIMIT = 40


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _iter_reference_rows(
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Iterable[tuple[str, Any]]:
    table = load_lunar_reference_table()
    start = _parse_date(start_date) if start_date else None
    end = _parse_date(end_date) if end_date else None
    if start and end and end < start:
        raise ValueError("end_date must be greater than or equal to start_date")

    for solar_date, record in sorted(table.by_solar_date.items()):
        current = _parse_date(solar_date)
        if start and current < start:
            continue
        if end and current > end:
            continue
        yield solar_date, record


def _lunar_python_day_ganzhi(solar_date: str) -> str:
    year, month, day = [int(part) for part in solar_date.split("-")]
    return Solar.fromYmd(year, month, day).getLunar().getDayInGanZhi()


def collect_iljin_reference_diff_data(
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    sample_limit: int = DEFAULT_SAMPLE_LIMIT,
) -> Dict[str, Any]:
    total_compared = 0
    mismatch_samples: List[Dict[str, Any]] = []
    year_counts: Counter[str] = Counter()
    mismatch_year_counts: Counter[str] = Counter()

    for solar_date, record in _iter_reference_rows(start_date=start_date, end_date=end_date):
        total_compared += 1
        year_counts[solar_date[:4]] += 1
        lunar_python_day = _lunar_python_day_ganzhi(solar_date)
        if lunar_python_day == record.day_ganzhi_hanja:
            continue

        mismatch_year_counts[solar_date[:4]] += 1
        mismatch_samples.append(
            {
                "solar_date": solar_date,
                "kasi_day_ganzhi_hanja": record.day_ganzhi_hanja,
                "lunar_python_day_ganzhi": lunar_python_day,
                "kasi_lunar_date": record.lunar_date,
                "is_lunar_leap_month": record.is_lunar_leap_month,
            }
        )

    compared_years = sorted(year_counts.keys())
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "range": {
            "start_date": start_date or (f"{compared_years[0]}-01-01" if compared_years else None),
            "end_date": end_date or (f"{compared_years[-1]}-12-31" if compared_years else None),
        },
        "source_of_truth_candidate": "checked-in KASI lunisolar table day_ganzhi_hanja",
        "compared_candidate": "lunar_python Lunar.getDayInGanZhi",
        "total_compared": total_compared,
        "mismatch_count": len(mismatch_samples),
        "mismatch_year_counts": dict(sorted(mismatch_year_counts.items())),
        "mismatch_samples": mismatch_samples[:sample_limit],
    }


def build_markdown_report(data: Dict[str, Any]) -> str:
    lines = [
        "# KASI Iljin Reference Diff Report",
        "",
        f"- Generated at: `{data['generated_at']}`",
        f"- Range: `{data['range']['start_date']}` to `{data['range']['end_date']}`",
        "- Reference candidate: checked-in KASI `day_ganzhi_hanja` values",
        "- Compared candidate: `lunar_python` `Lunar.getDayInGanZhi()`",
        "- Purpose: verify the table-backed primary day-pillar gan-zhi source.",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
        f"| Total compared dates | {data['total_compared']} |",
        f"| Mismatch dates | {data['mismatch_count']} |",
        "",
        "## Mismatches By Year",
        "",
    ]
    if data["mismatch_year_counts"]:
        lines.extend(["| Year | Count |", "| --- | ---: |"])
        for year, count in data["mismatch_year_counts"].items():
            lines.append(f"| {year} | {count} |")
    else:
        lines.append("None.")

    lines.extend(["", "## Sample Mismatches", ""])
    if data["mismatch_samples"]:
        lines.extend(
            [
                "| Solar date | KASI iljin | lunar_python day pillar | KASI lunar date | Leap month |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for item in data["mismatch_samples"]:
            lines.append(
                "| "
                + " | ".join(
                    [
                        item["solar_date"],
                        item["kasi_day_ganzhi_hanja"],
                        item["lunar_python_day_ganzhi"],
                        item["kasi_lunar_date"],
                        "yes" if item["is_lunar_leap_month"] else "no",
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
            "- If mismatches appear, inspect them before extending or changing the day-pillar provider.",
            "- This report intentionally compares only the day ganzhi/iljin field.",
            "- Lunar/solar conversion drift is covered separately by `lunar_reference_diff_report.md`.",
            "",
            "## Regenerate",
            "",
            "```powershell",
            "cd apps/api",
            "python tests/generate_iljin_reference_diff_report.py",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(path: Path = REPORT_PATH, *, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
    data = collect_iljin_reference_diff_data(start_date=start_date, end_date=end_date)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_markdown_report(data), encoding="utf-8")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a KASI iljin/day-pillar diff report.")
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    args = parser.parse_args()

    data = write_report(start_date=args.start_date, end_date=args.end_date)
    print(
        json.dumps(
            {
                "report_path": str(REPORT_PATH),
                "total_compared": data["total_compared"],
                "mismatch_count": data["mismatch_count"],
                "mismatch_year_count": len(data["mismatch_year_counts"]),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
