"""Generate a canonical year/month shadow diff report."""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import patch

from app.domain.saju.schemas import RegionSuggestion, SajuPreviewRequest
from app.domain.saju.services.solar_term_boundaries import nearest_solar_term_boundary
from app.domain.saju.services.preview_orchestrator import create_saju_preview_response


TESTS_DIR = Path(__file__).resolve().parent
API_ROOT = TESTS_DIR.parent
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

try:
    from tests.generate_accuracy_mode_diff_report import (
        REFERENCE_FIXTURE_DIR,
        REPORT_PATH as ACCURACY_REPORT_PATH,
        ReportCase,
        _base_preview_request,
        _load_json,
        _region_patch_context,
        _zero_correction_region,
        load_report_cases,
    )
except ModuleNotFoundError:
    from generate_accuracy_mode_diff_report import (
        REFERENCE_FIXTURE_DIR,
        REPORT_PATH as ACCURACY_REPORT_PATH,
        ReportCase,
        _base_preview_request,
        _load_json,
        _region_patch_context,
        _zero_correction_region,
        load_report_cases,
    )

REPORT_PATH = TESTS_DIR / "reports" / "canonical_year_month_diff_report.md"
BOUNDARY_EXPLANATION_MINUTES = 24 * 60


def _solar_term_boundary_cases() -> List[ReportCase]:
    fixture = _load_json(REFERENCE_FIXTURE_DIR / "solar_term_reference_cases.json")
    cases: List[ReportCase] = []
    for case in fixture["cases"]:
        expected = case.get("expected", {})
        solar_term_datetime = expected.get("solar_term_datetime")
        if not solar_term_datetime:
            continue
        dt = datetime.fromisoformat(solar_term_datetime)
        region_id = "reference-canonical-asia-seoul"
        cases.append(
            ReportCase(
                case_id=f"solar-term:{case['case_id']}",
                source="reference:solar_term_reference_cases.json",
                description=case["description"],
                request=_base_preview_request(
                    calendar_type="solar",
                    birth_date=dt.date().isoformat(),
                    birth_time=dt.strftime("%H:%M"),
                    region_id=region_id,
                ),
                region_override=_zero_correction_region(region_id=region_id, tzid="Asia/Seoul"),
                notes="Solar-term hard reference adapted as an exact-boundary birth chart for shadow comparison.",
            )
        )
    return cases


def load_canonical_report_cases() -> List[ReportCase]:
    cases, _unprocessed = load_report_cases()
    return [*cases, *_solar_term_boundary_cases()]


def _preview(case: ReportCase):
    request_data = dict(case.request)
    request_data["accuracy_mode"] = "legacy"
    request_data["debug"] = True
    payload = SajuPreviewRequest(**request_data)

    with patch("app.domain.saju.services.generate_interpretation.settings.llm_provider", "fallback"):
        with patch(
            "app.domain.saju.services.preview_orchestrator.settings.use_canonical_year_month_pillars",
            False,
        ):
            with _region_patch_context(case):
                return create_saju_preview_response(
                    payload=payload,
                    trace_id=f"canonical-year-month-diff-{case.case_id}",
                    debug_requested=True,
                    service_name="canonical-year-month-diff-report",
                )


def _parse_local_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def _delta_minutes(a: Optional[datetime], b: Optional[datetime]) -> Optional[float]:
    if a is None or b is None:
        return None
    return abs((a - b).total_seconds()) / 60


def _reason_for(context: Dict[str, Any]) -> str:
    selected = _parse_local_datetime(str(context.get("selected_basis_datetime", "")))
    year_boundary = _parse_local_datetime(str(context.get("year_boundary_datetime", "")))
    month_boundary = _parse_local_datetime(str(context.get("month_boundary_datetime", "")))
    year_delta = _delta_minutes(selected, year_boundary)
    month_delta = _delta_minutes(selected, month_boundary)

    if context.get("year_pillar_changed") and year_delta is not None:
        if year_delta <= BOUNDARY_EXPLANATION_MINUTES:
            return "near_lichun_boundary"
    if context.get("month_pillar_changed") and month_delta is not None:
        if month_delta <= BOUNDARY_EXPLANATION_MINUTES:
            return "near_month_jie_boundary"
    if context.get("year_pillar_changed") or context.get("month_pillar_changed"):
        nearest = nearest_solar_term_boundary(
            str(context.get("selected_basis_datetime", "")),
            timezone_id=str(context.get("timezone_id", "Asia/Seoul")),
        )
        if nearest and nearest.delta_seconds <= BOUNDARY_EXPLANATION_MINUTES * 60:
            term_id = str(nearest.reference.get("term_id", ""))
            if term_id == "ipchun" and context.get("year_pillar_changed"):
                return "near_lichun_boundary"
            return "near_month_jie_boundary"
    if context.get("year_pillar_changed") or context.get("month_pillar_changed"):
        return "provider_difference"
    return "unchanged"


def _snapshot(case: ReportCase, response) -> Dict[str, Any]:
    context = dict(response.debug_trace.year_month_boundary_context)
    reason = _reason_for(context)
    return {
        "case_id": case.case_id,
        "source": case.source,
        "description": case.description,
        "selected_basis_datetime": context.get("selected_basis_datetime"),
        "legacy_year_pillar": context.get("legacy_year_pillar"),
        "canonical_year_pillar": context.get("canonical_year_pillar"),
        "legacy_month_pillar": context.get("legacy_month_pillar"),
        "canonical_month_pillar": context.get("canonical_month_pillar"),
        "year_pillar_changed": bool(context.get("year_pillar_changed")),
        "month_pillar_changed": bool(context.get("month_pillar_changed")),
        "year_boundary_term": context.get("year_boundary_term"),
        "year_boundary_datetime": context.get("year_boundary_datetime"),
        "month_boundary_term": context.get("month_boundary_term"),
        "month_boundary_datetime": context.get("month_boundary_datetime"),
        "solar_term_provider_source": context.get("solar_term_provider_source"),
        "year_boundary_provider_source": context.get("year_boundary_provider_source"),
        "month_boundary_provider_source": context.get("month_boundary_provider_source"),
        "reason": reason,
        "applied_to_primary": bool(context.get("applied_to_primary")),
        "notes": case.notes,
    }


def collect_canonical_year_month_diff_data(limit: Optional[int] = None) -> Dict[str, Any]:
    cases = load_canonical_report_cases()
    if limit is not None:
        cases = cases[:limit]

    rows: List[Dict[str, Any]] = []
    for case in cases:
        response = _preview(case)
        if case.region_override is not None:
            RegionSuggestion(**case.region_override)
        rows.append(_snapshot(case, response))

    reason_counts = Counter(row["reason"] for row in rows)
    provider_counts = Counter(str(row["solar_term_provider_source"]) for row in rows)
    changed_rows = [
        row for row in rows if row["year_pillar_changed"] or row["month_pillar_changed"]
    ]
    explained_by_boundary = [
        row
        for row in changed_rows
        if row["reason"] in {"near_lichun_boundary", "near_month_jie_boundary"}
    ]
    stats = {
        "total_case_count": len(rows),
        "year_pillar_changed_count": sum(row["year_pillar_changed"] for row in rows),
        "month_pillar_changed_count": sum(row["month_pillar_changed"] for row in rows),
        "changed_case_count": len(changed_rows),
        "applied_to_primary_count": sum(row["applied_to_primary"] for row in rows),
        "boundary_explained_changed_count": len(explained_by_boundary),
        "boundary_explained_changed_ratio": (
            len(explained_by_boundary) / len(changed_rows) if changed_rows else 1.0
        ),
        "reason_counts": dict(reason_counts),
        "provider_counts": dict(provider_counts),
    }
    return {
        "generated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "source_report": str(ACCURACY_REPORT_PATH),
        "stats": stats,
        "rows": rows,
    }


def build_markdown_report(data: Dict[str, Any]) -> str:
    stats = data["stats"]
    lines = [
        "# Canonical Year/Month Pillar Shadow Diff Report",
        "",
        f"Generated at: `{data['generated_at']}`",
        "",
        "Conclusion: Manual review required. The default primary remains legacy.",
        "",
        "## Summary",
        "",
        f"| Total cases | {stats['total_case_count']} |",
        f"| Changed cases | {stats['changed_case_count']} |",
        f"| Year pillar changed | {stats['year_pillar_changed_count']} |",
        f"| Month pillar changed | {stats['month_pillar_changed_count']} |",
        f"| Applied to primary | {stats['applied_to_primary_count']} |",
        f"| Boundary-explained changed cases | {stats['boundary_explained_changed_count']} |",
        f"| Boundary-explained ratio | {stats['boundary_explained_changed_ratio']:.2%} |",
        "",
        "## Reason Counts",
        "",
    ]
    for reason, count in sorted(stats["reason_counts"].items()):
        lines.append(f"- `{reason}`: {count}")
    lines.extend(["", "## Provider Counts", ""])
    for provider, count in sorted(stats["provider_counts"].items()):
        lines.append(f"- `{provider}`: {count}")
    lines.extend(
        [
            "",
            "## Changed Rows",
            "",
            "| Case | Basis | Legacy Y/M | Canonical Y/M | Boundary | Reason |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    changed_rows = [
        row
        for row in data["rows"]
        if row["year_pillar_changed"] or row["month_pillar_changed"]
    ]
    for row in changed_rows:
        lines.append(
            "| "
            f"{row['case_id']} | "
            f"{row['selected_basis_datetime']} | "
            f"{row['legacy_year_pillar']} / {row['legacy_month_pillar']} | "
            f"{row['canonical_year_pillar']} / {row['canonical_month_pillar']} | "
            f"{row['month_boundary_term']} {row['month_boundary_datetime']} | "
            f"{row['reason']} |"
        )
    if not changed_rows:
        lines.append("| none | - | - | - | - | - |")
    lines.extend(
        [
            "",
            "## Regenerate",
            "",
            "```powershell",
            "cd apps/api",
            "python tests/generate_canonical_year_month_diff_report.py",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def write_report(data: Dict[str, Any]) -> Path:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(build_markdown_report(data), encoding="utf-8")
    return REPORT_PATH


def main() -> None:
    data = collect_canonical_year_month_diff_data()
    path = write_report(data)
    print(json.dumps(data["stats"], ensure_ascii=False, indent=2))
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
