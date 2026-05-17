"""Generate an accuracy-mode diff report without changing primary behavior."""

from __future__ import annotations

import json
from collections import Counter
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence
from unittest.mock import patch

from app.domain.saju.schemas import RegionSuggestion, SajuPreviewRequest
from app.domain.saju.services.preview_orchestrator import create_saju_preview_response


TESTS_DIR = Path(__file__).resolve().parent
GOLDEN_FIXTURE_PATH = TESTS_DIR / "fixtures" / "saju_preview_golden_cases.json"
REFERENCE_FIXTURE_DIR = TESTS_DIR / "fixtures" / "reference_cases"
REPORT_PATH = TESTS_DIR / "reports" / "accuracy_mode_diff_report.md"
ACCURACY_MODES = ("legacy", "standard_time", "mean_solar_time", "compare")
PILLAR_FIELDS = ("year_pillar", "month_pillar", "day_pillar", "hour_pillar")
COMPARE_FIELDS = (
    *PILLAR_FIELDS,
    "first_luck_cycle_start_age",
    "first_luck_cycle_start_age_total_months",
)


@dataclass(frozen=True)
class ReportCase:
    case_id: str
    source: str
    description: str
    request: Dict[str, Any]
    region_override: Optional[Dict[str, Any]] = None
    notes: str = ""


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _zero_correction_region(*, region_id: str, tzid: str) -> Dict[str, Any]:
    return {
        "id": region_id,
        "display_name": f"Reference zero correction ({tzid})",
        "country": "Reference",
        "province": "Reference",
        "city": region_id,
        "tzid": tzid,
        "longitude": 135.0 if tzid == "Asia/Seoul" else 0.0,
        "regional_time_offset_minutes": 0.0,
        "correction_basis": "reference-zero-correction",
        "aliases": [region_id],
    }


def _base_preview_request(
    *,
    calendar_type: str,
    birth_date: str,
    birth_time: str,
    gender: str = "male",
    region_id: str = "kr-seoul",
    is_birth_time_estimated: bool = False,
    is_lunar_leap_month: bool = False,
) -> Dict[str, Any]:
    return {
        "calendar_type": calendar_type,
        "birth_date": birth_date,
        "birth_time": birth_time,
        "is_birth_time_estimated": is_birth_time_estimated,
        "is_lunar_leap_month": is_lunar_leap_month,
        "gender": gender,
        "region_id": region_id,
        "debug": True,
    }


def load_golden_report_cases() -> List[ReportCase]:
    fixture = _load_json(GOLDEN_FIXTURE_PATH)
    cases: List[ReportCase] = []
    for case in fixture["cases"]:
        request = dict(case["request"])
        request["debug"] = True
        cases.append(
            ReportCase(
                case_id=f"golden:{case['id']}",
                source="golden:saju_preview_golden_cases.json",
                description=case["description"],
                request=request,
                region_override=case.get("region_override"),
                notes="Golden baseline case; compared here only for accuracy-mode drift.",
            )
        )
    return cases


def _reference_lunar_solar_cases(fixture: Dict[str, Any]) -> List[ReportCase]:
    cases: List[ReportCase] = []
    for case in fixture["cases"]:
        input_data = case["input"]
        cases.append(
            ReportCase(
                case_id=f"reference:{case['case_id']}",
                source="reference:lunar_solar_reference_cases.json",
                description=case["description"],
                request=_base_preview_request(
                    calendar_type=input_data["calendar_type"],
                    birth_date=input_data["birth_date"],
                    birth_time=input_data["birth_time"],
                    is_lunar_leap_month=input_data.get("is_lunar_leap_month", False),
                ),
                notes="Pending KASI reference case; included to observe mode drift before official expected values are filled.",
            )
        )
    return cases


def _reference_timezone_cases(fixture: Dict[str, Any], unprocessed: List[Dict[str, str]]) -> List[ReportCase]:
    cases: List[ReportCase] = []
    for case in fixture["cases"]:
        input_data = case["input"]
        if "error_code" in case["expected"]:
            unprocessed.append(
                {
                    "case_id": f"reference:{case['case_id']}",
                    "source": "reference:timezone_dst_reference_cases.json",
                    "reason": "nonexistent local time hard reference is not a preview-comparable birth chart",
                }
            )
            continue

        tzid = input_data["tzid"]
        region_id = f"reference-{tzid.lower().replace('/', '-')}"
        cases.append(
            ReportCase(
                case_id=f"reference:{case['case_id']}",
                source="reference:timezone_dst_reference_cases.json",
                description=case["description"],
                request=_base_preview_request(
                    calendar_type="solar",
                    birth_date=input_data["birth_date"],
                    birth_time=input_data["birth_time"],
                    region_id=region_id,
                ),
                region_override=_zero_correction_region(region_id=region_id, tzid=tzid),
                notes="Timezone/DST hard reference adapted with zero regional solar correction for mode comparison.",
            )
        )
    return cases


def _reference_midnight_cases(fixture: Dict[str, Any]) -> List[ReportCase]:
    cases: List[ReportCase] = []
    for case in fixture["cases"]:
        input_data = case["input"]
        dt = datetime.strptime(input_data["corrected_solar_datetime"], "%Y-%m-%d %H:%M:%S")
        tzid = input_data.get("tzid", "Asia/Seoul")
        region_id = f"reference-midnight-{tzid.lower().replace('/', '-')}"
        cases.append(
            ReportCase(
                case_id=f"reference:{case['case_id']}",
                source="reference:midnight_boundary_cases.json",
                description=case["description"],
                request=_base_preview_request(
                    calendar_type="solar",
                    birth_date=dt.date().isoformat(),
                    birth_time=dt.strftime("%H:%M"),
                    gender=input_data["gender"],
                    region_id=region_id,
                ),
                region_override=_zero_correction_region(region_id=region_id, tzid=tzid),
                notes="Midnight boundary hard reference adapted with zero correction so legacy input matches the fixture datetime.",
            )
        )
    return cases


def load_reference_report_cases() -> tuple[List[ReportCase], List[Dict[str, str]]]:
    cases: List[ReportCase] = []
    unprocessed: List[Dict[str, str]] = []

    lunar_solar = _load_json(REFERENCE_FIXTURE_DIR / "lunar_solar_reference_cases.json")
    cases.extend(_reference_lunar_solar_cases(lunar_solar))

    timezone_dst = _load_json(REFERENCE_FIXTURE_DIR / "timezone_dst_reference_cases.json")
    cases.extend(_reference_timezone_cases(timezone_dst, unprocessed))

    midnight = _load_json(REFERENCE_FIXTURE_DIR / "midnight_boundary_cases.json")
    cases.extend(_reference_midnight_cases(midnight))

    solar_terms = _load_json(REFERENCE_FIXTURE_DIR / "solar_term_reference_cases.json")
    for case in solar_terms["cases"]:
        unprocessed.append(
            {
                "case_id": f"reference:{case['case_id']}",
                "source": "reference:solar_term_reference_cases.json",
                "reason": "solar-term reference lacks a concrete birth_time/input_datetime for accuracy-mode preview comparison",
            }
        )

    return cases, unprocessed


def load_report_cases() -> tuple[List[ReportCase], List[Dict[str, str]]]:
    reference_cases, unprocessed = load_reference_report_cases()
    return [*load_golden_report_cases(), *reference_cases], unprocessed


def _region_patch_context(case: ReportCase):
    if case.region_override is None:
        return nullcontext()

    return patch(
        "app.domain.saju.services.preview_orchestrator.find_region_by_id",
        return_value=RegionSuggestion(**case.region_override),
    )


def _preview_for_mode(case: ReportCase, mode: str):
    request_data = dict(case.request)
    request_data["accuracy_mode"] = mode
    request_data["debug"] = True
    payload = SajuPreviewRequest(**request_data)

    with patch("app.domain.saju.services.generate_interpretation.settings.llm_provider", "fallback"):
        with _region_patch_context(case):
            return create_saju_preview_response(
                payload=payload,
                trace_id=f"accuracy-mode-diff-{case.case_id}-{mode}",
                debug_requested=True,
                service_name="accuracy-mode-diff-report",
            )


def _snapshot_response(response) -> Dict[str, Any]:
    first_luck = response.manse.luck_cycles[0] if response.manse.luck_cycles else None
    uncertainty_flags = response.debug_trace.uncertainty_flags if response.debug_trace else []
    flag_codes = [flag.code for flag in uncertainty_flags]
    critical_flag_codes = [flag.code for flag in uncertainty_flags if flag.severity == "critical"]

    return {
        "year_pillar": response.manse.pillars.year.gan_zhi,
        "month_pillar": response.manse.pillars.month.gan_zhi,
        "day_pillar": response.manse.pillars.day.gan_zhi,
        "hour_pillar": response.manse.pillars.time.gan_zhi,
        "first_luck_cycle_start_age": first_luck.start_age if first_luck else None,
        "first_luck_cycle_start_age_years": first_luck.start_age_years if first_luck else None,
        "first_luck_cycle_start_age_months": first_luck.start_age_months if first_luck else None,
        "first_luck_cycle_start_age_total_months": (
            first_luck.start_age_total_months if first_luck else None
        ),
        "uncertainty_flags": flag_codes,
        "critical_flags": critical_flag_codes,
        "primary_input_datetime_to_lunar_python": (
            response.result.calculation_basis.primary_input_datetime_to_lunar_python
        ),
    }


def _changed_fields_from_legacy(mode_snapshots: Dict[str, Dict[str, Any]]) -> List[str]:
    legacy = mode_snapshots["legacy"]
    changed: List[str] = []
    for field_name in COMPARE_FIELDS:
        if any(mode_snapshots[mode][field_name] != legacy[field_name] for mode in ACCURACY_MODES if mode != "legacy"):
            changed.append(field_name)
    return changed


def collect_accuracy_mode_diff_data(limit: Optional[int] = None) -> Dict[str, Any]:
    cases, unprocessed = load_report_cases()
    if limit is not None:
        cases = cases[:limit]

    rows: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    for case in cases:
        mode_snapshots: Dict[str, Dict[str, Any]] = {}
        try:
            for mode in ACCURACY_MODES:
                mode_snapshots[mode] = _snapshot_response(_preview_for_mode(case, mode))
        except Exception as exc:  # pragma: no cover - report should preserve unexpected collection failures
            errors.append(
                {
                    "case_id": case.case_id,
                    "source": case.source,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue

        rows.append(
            {
                "case_id": case.case_id,
                "source": case.source,
                "description": case.description,
                "notes": case.notes,
                "modes": mode_snapshots,
                "changed_fields": _changed_fields_from_legacy(mode_snapshots),
            }
        )

    stats = _build_stats(rows, source_case_count=len(cases), unprocessed_count=len(unprocessed), error_count=len(errors))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": stats,
        "rows": rows,
        "unprocessed_cases": unprocessed,
        "errors": errors,
    }


def _build_stats(
    rows: Sequence[Dict[str, Any]],
    *,
    source_case_count: int,
    unprocessed_count: int,
    error_count: int,
) -> Dict[str, Any]:
    flag_code_counts: Counter[str] = Counter()
    critical_flag_code_counts: Counter[str] = Counter()
    for row in rows:
        for mode_snapshot in row["modes"].values():
            flag_code_counts.update(mode_snapshot["uncertainty_flags"])
            critical_flag_code_counts.update(mode_snapshot["critical_flags"])

    return {
        "source_case_count": source_case_count,
        "total_case_count": len(rows),
        "unprocessed_reference_case_count": unprocessed_count,
        "error_case_count": error_count,
        "standard_time_changed_case_count": sum(
            any(
                row["modes"]["standard_time"][field_name] != row["modes"]["legacy"][field_name]
                for field_name in COMPARE_FIELDS
            )
            for row in rows
        ),
        "mean_solar_time_changed_case_count": sum(
            any(
                row["modes"]["mean_solar_time"][field_name] != row["modes"]["legacy"][field_name]
                for field_name in COMPARE_FIELDS
            )
            for row in rows
        ),
        "compare_changed_case_count": sum(
            any(
                row["modes"]["compare"][field_name] != row["modes"]["legacy"][field_name]
                for field_name in COMPARE_FIELDS
            )
            for row in rows
        ),
        "hour_pillar_change_count": sum("hour_pillar" in row["changed_fields"] for row in rows),
        "day_pillar_change_count": sum("day_pillar" in row["changed_fields"] for row in rows),
        "month_pillar_change_count": sum("month_pillar" in row["changed_fields"] for row in rows),
        "year_pillar_change_count": sum("year_pillar" in row["changed_fields"] for row in rows),
        "first_luck_cycle_start_age_change_count": sum(
            "first_luck_cycle_start_age" in row["changed_fields"] for row in rows
        ),
        "first_luck_cycle_start_age_month_change_count": sum(
            "first_luck_cycle_start_age_total_months" in row["changed_fields"] for row in rows
        ),
        "critical_flag_count": sum(
            len(mode_snapshot["critical_flags"])
            for row in rows
            for mode_snapshot in row["modes"].values()
        ),
        "flag_code_counts": dict(sorted(flag_code_counts.items())),
        "critical_flag_code_counts": dict(sorted(critical_flag_code_counts.items())),
    }


def _format_snapshot(snapshot: Dict[str, Any]) -> str:
    flags = ",".join(snapshot["uncertainty_flags"]) or "-"
    return (
        f"{snapshot['year_pillar']}/{snapshot['month_pillar']}/"
        f"{snapshot['day_pillar']}/{snapshot['hour_pillar']} "
        f"luck={snapshot['first_luck_cycle_start_age']}y/"
        f"{snapshot['first_luck_cycle_start_age_total_months']}m_total flags={flags}"
    )


def build_markdown_report(data: Dict[str, Any]) -> str:
    stats = data["stats"]
    lines = [
        "# Accuracy Mode Diff Report",
        "",
        f"- Generated at: `{data['generated_at']}`",
        "- Conclusion: Manual review required. This report does not change the default primary mode.",
        "- Default primary remains: `legacy`.",
        "- Compared modes: `legacy`, `standard_time`, `mean_solar_time`, `compare`.",
        "",
        "## Statistics",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
        f"| Source cases prepared for comparison | {stats['source_case_count']} |",
        f"| Total compared cases | {stats['total_case_count']} |",
        f"| Unprocessed reference cases | {stats['unprocessed_reference_case_count']} |",
        f"| Error cases | {stats['error_case_count']} |",
        f"| Standard-time mode changed cases | {stats['standard_time_changed_case_count']} |",
        f"| Mean-solar-time mode changed cases | {stats['mean_solar_time_changed_case_count']} |",
        f"| Compare mode changed cases | {stats['compare_changed_case_count']} |",
        f"| Hour pillar changed | {stats['hour_pillar_change_count']} |",
        f"| Day pillar changed | {stats['day_pillar_change_count']} |",
        f"| Month pillar changed | {stats['month_pillar_change_count']} |",
        f"| Year pillar changed | {stats['year_pillar_change_count']} |",
        f"| First luck-cycle start age changed | {stats['first_luck_cycle_start_age_change_count']} |",
        f"| First luck-cycle start age month precision changed | {stats['first_luck_cycle_start_age_month_change_count']} |",
        f"| Critical flag occurrences across all modes | {stats['critical_flag_count']} |",
        "",
        "## Flag Counts",
        "",
        "| Flag code | Count | Critical count |",
        "| --- | ---: | ---: |",
    ]
    flag_codes = sorted(
        set(stats["flag_code_counts"].keys())
        | set(stats["critical_flag_code_counts"].keys())
    )
    if flag_codes:
        for code in flag_codes:
            lines.append(
                f"| {code} | {stats['flag_code_counts'].get(code, 0)} | "
                f"{stats['critical_flag_code_counts'].get(code, 0)} |"
            )
    else:
        lines.append("| none | 0 | 0 |")

    lines.extend(
        [
            "",
            "## Case Diffs",
            "",
            "| Case | Source | Changed fields vs legacy | Legacy | Standard time | Mean solar time | Compare |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )

    for row in data["rows"]:
        changed_fields = ", ".join(row["changed_fields"]) or "-"
        lines.append(
            "| "
            + " | ".join(
                [
                    row["case_id"],
                    row["source"],
                    changed_fields,
                    _format_snapshot(row["modes"]["legacy"]),
                    _format_snapshot(row["modes"]["standard_time"]),
                    _format_snapshot(row["modes"]["mean_solar_time"]),
                    _format_snapshot(row["modes"]["compare"]),
                ]
            )
            + " |"
        )

    lines.extend(["", "## Unprocessed Reference Cases", ""])
    if data["unprocessed_cases"]:
        lines.extend(["| Case | Source | Reason |", "| --- | --- | --- |"])
        for item in data["unprocessed_cases"]:
            lines.append(f"| {item['case_id']} | {item['source']} | {item['reason']} |")
    else:
        lines.append("None.")

    lines.extend(["", "## Errors", ""])
    if data["errors"]:
        lines.extend(["| Case | Source | Error |", "| --- | --- | --- |"])
        for item in data["errors"]:
            lines.append(f"| {item['case_id']} | {item['source']} | {item['error']} |")
    else:
        lines.append("None.")

    lines.extend(
        [
            "",
            "## Regenerate",
            "",
            "```powershell",
            "cd apps/api",
            "python tests/generate_accuracy_mode_diff_report.py",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(path: Path = REPORT_PATH) -> Dict[str, Any]:
    data = collect_accuracy_mode_diff_data()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_markdown_report(data), encoding="utf-8-sig")
    return data


def main() -> None:
    data = write_report()
    stats = data["stats"]
    print(
        json.dumps(
            {
                "report_path": str(REPORT_PATH),
                "total_case_count": stats["total_case_count"],
                "hour_pillar_change_count": stats["hour_pillar_change_count"],
                "day_pillar_change_count": stats["day_pillar_change_count"],
                "month_pillar_change_count": stats["month_pillar_change_count"],
                "year_pillar_change_count": stats["year_pillar_change_count"],
                "first_luck_cycle_start_age_change_count": stats[
                    "first_luck_cycle_start_age_change_count"
                ],
                "critical_flag_count": stats["critical_flag_count"],
                "flag_code_counts": stats["flag_code_counts"],
                "conclusion": "manual_review_required",
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
