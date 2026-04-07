from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Dict, List

from app.domain.saju.golden import GoldenKnownAnswerCase, compare_golden_snapshots
from app.domain.saju.services.build_golden_snapshot import build_actual_golden_snapshot


def _group_path(path: str) -> str:
    if "[" in path:
        return path.split("[", 1)[0]
    return path.split(".", 1)[0]


def _field_path(path: str) -> str:
    if path.startswith("luck_cycles["):
        if "." in path:
            return "luck_cycles." + path.split(".", 1)[1]
        return "luck_cycles"
    if path.startswith("pillar_table."):
        parts = path.split(".")
        if len(parts) >= 3:
            return f"pillar_table.{parts[2]}"
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare canonical golden fixtures against current saju output."
    )
    parser.add_argument(
        "--expected-dir",
        default=str(Path("tests/golden_cases/expected")),
        help="Directory containing expected canonical JSON fixtures.",
    )
    parser.add_argument(
        "--report-dir",
        default=str(Path("tests/golden_reports/latest")),
        help="Directory where actual snapshots and diff reports will be written.",
    )
    parser.add_argument(
        "--summary-file",
        default=None,
        help="Optional summary JSON output path. Defaults to <report-dir>/summary.json.",
    )
    parser.add_argument(
        "--fail-on-mismatch",
        action="store_true",
        help="Return a non-zero exit code if any case mismatches.",
    )
    return parser


def compare_golden_cases(*, expected_dir: Path, report_dir: Path, summary_file: Path) -> Dict[str, object]:
    actual_dir = report_dir / "actual"
    diff_dir = report_dir / "diff"
    actual_dir.mkdir(parents=True, exist_ok=True)
    diff_dir.mkdir(parents=True, exist_ok=True)

    total_cases = 0
    total_mismatches = 0
    case_summaries: List[Dict[str, object]] = []
    global_field_counts: Counter[str] = Counter()

    for expected_path in sorted(expected_dir.glob("*.json")):
        case = GoldenKnownAnswerCase.model_validate_json(expected_path.read_text(encoding="utf-8"))
        actual = build_actual_golden_snapshot(case_input=case.input)
        report = compare_golden_snapshots(case=case, actual=actual)

        actual_path = actual_dir / f"{case.input.case_id}.actual.json"
        diff_path = diff_dir / f"{case.input.case_id}.report.json"
        actual_path.write_text(
            json.dumps(actual.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        diff_path.write_text(
            json.dumps(report.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        total_cases += 1
        total_mismatches += report.mismatch_count
        group_counts = Counter(_group_path(mismatch.path) for mismatch in report.mismatches)
        field_counts = Counter(_field_path(mismatch.path) for mismatch in report.mismatches)
        global_field_counts.update(field_counts)

        case_summary = {
            "case_id": report.case_id,
            "source_name": report.source_name,
            "success": report.success,
            "compared_leaf_count": report.compared_leaf_count,
            "mismatch_count": report.mismatch_count,
            "mismatch_groups": dict(group_counts),
            "mismatch_fields": dict(field_counts),
            "report_path": str(diff_path),
            "actual_path": str(actual_path),
        }
        case_summaries.append(case_summary)
        print(json.dumps(case_summary, ensure_ascii=False))

    summary: Dict[str, object] = {
        "total_cases": total_cases,
        "total_mismatches": total_mismatches,
        "report_dir": str(report_dir),
        "summary_file": str(summary_file),
        "mismatch_fields": dict(global_field_counts),
        "cases": case_summaries,
    }
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    summary_file.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))
    return summary


def main() -> int:
    args = build_parser().parse_args()
    expected_dir = Path(args.expected_dir)
    report_dir = Path(args.report_dir)
    summary_file = Path(args.summary_file) if args.summary_file else report_dir / "summary.json"
    summary = compare_golden_cases(
        expected_dir=expected_dir,
        report_dir=report_dir,
        summary_file=summary_file,
    )

    if args.fail_on_mismatch and int(summary["total_mismatches"]) > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
