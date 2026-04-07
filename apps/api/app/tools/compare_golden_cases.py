from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Dict, List

from app.domain.saju.golden import GoldenKnownAnswerCase, compare_golden_snapshots
from app.domain.saju.services.build_golden_snapshot import build_actual_golden_snapshot

JIA_ZI_KO = [
    "갑자",
    "을축",
    "병인",
    "정묘",
    "무진",
    "기사",
    "경오",
    "신미",
    "임신",
    "계유",
    "갑술",
    "을해",
    "병자",
    "정축",
    "무인",
    "기묘",
    "경진",
    "신사",
    "임오",
    "계미",
    "갑신",
    "을유",
    "병술",
    "정해",
    "무자",
    "기축",
    "경인",
    "신묘",
    "임진",
    "계사",
    "갑오",
    "을미",
    "병신",
    "정유",
    "무술",
    "기해",
    "경자",
    "신축",
    "임인",
    "계묘",
    "갑진",
    "을사",
    "병오",
    "정미",
    "무신",
    "기유",
    "경술",
    "신해",
    "임자",
    "계축",
    "갑인",
    "을묘",
    "병진",
    "정사",
    "무오",
    "기미",
    "경신",
    "신유",
    "임술",
    "계해",
]


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


def _gan_zhi_index(value: str) -> int | None:
    try:
        return JIA_ZI_KO.index(value)
    except ValueError:
        return None


def _analyze_expected_luck_cycle_sequence(expected_cycles: List[str]) -> Dict[str, object]:
    if len(expected_cycles) < 2:
        return {"tags": [], "invalid_values": []}

    indexed_cycles = [(value, _gan_zhi_index(value)) for value in expected_cycles]
    invalid_values = [value for value, index in indexed_cycles if index is None]
    if invalid_values:
        return {
            "tags": ["expected_luck_cycle_unparseable"],
            "invalid_values": invalid_values,
        }

    indexes = [index for _, index in indexed_cycles if index is not None]

    deltas = [((indexes[i + 1] - indexes[i]) % 60) for i in range(len(indexes) - 1)]
    unique_deltas = set(deltas)

    if len(unique_deltas) == 1 and unique_deltas.issubset({1, 59}):
        return {"tags": [], "invalid_values": []}

    if len(deltas) >= 2 and len(set(deltas[:-1])) == 1 and deltas[:-1][0] in {1, 59} and deltas[-1] != deltas[:-1][0]:
        return {"tags": ["expected_luck_cycle_tail_anomaly"], "invalid_values": []}

    return {"tags": ["expected_luck_cycle_nonconsecutive"], "invalid_values": []}


def _build_case_diagnostics(*, case: GoldenKnownAnswerCase, actual: object, report: object) -> Dict[str, object]:
    mismatch_paths = [mismatch.path for mismatch in report.mismatches]
    mismatch_path_set = set(mismatch_paths)
    tags: List[str] = []
    recommended_actions: List[str] = []

    expected_cycles = [cycle.gan_zhi for cycle in case.expected.luck_cycles]
    actual_cycles = [cycle.gan_zhi for cycle in actual.luck_cycles]
    aligned_luck_cycles = list(zip(case.expected.luck_cycles, actual.luck_cycles))
    expected_sequence_analysis = _analyze_expected_luck_cycle_sequence(expected_cycles)
    expected_sequence_tags = expected_sequence_analysis["tags"]
    invalid_expected_cycles = expected_sequence_analysis["invalid_values"]

    luck_cycle_paths = [path for path in mismatch_paths if path.startswith("luck_cycles")]
    basic_info_paths = [path for path in mismatch_paths if path.startswith("basic_info")]

    if basic_info_paths and set(basic_info_paths).issubset(
        {"basic_info.corrected_datetime", "basic_info.regional_time_offset_minutes"}
    ):
        tags.append("regional_display_rounding_mismatch")
        recommended_actions.append(
            "Review corrected_datetime/regional_time_offset_minutes display rounding against answer sheet conventions."
        )

    if (
        len(luck_cycle_paths) == 1
        and luck_cycle_paths[0].startswith(f"luck_cycles[{len(actual_cycles)}]")
        and any(mismatch.kind == "missing_actual" for mismatch in report.mismatches)
    ):
        tags.append("luck_cycle_tail_missing_only")
        recommended_actions.append(
            "Review displayed DaYun count; the current export stops one cycle earlier than the answer sheet."
        )

    if any(path.endswith(".gan_zhi") for path in luck_cycle_paths) and any(
        path.endswith(".branch") for path in luck_cycle_paths
    ):
        tags.append("luck_cycle_progression_rule_mismatch")
        recommended_actions.append(
            "Investigate DaYun progression rules or source differences; current lunar-python month-pillar progression diverges from the answer sheet."
        )

    if aligned_luck_cycles:
        stem_mismatch_count = sum(
            expected_cycle.stem != actual_cycle.stem
            for expected_cycle, actual_cycle in aligned_luck_cycles
        )
        branch_mismatch_count = sum(
            expected_cycle.branch != actual_cycle.branch
            for expected_cycle, actual_cycle in aligned_luck_cycles
        )
        gan_zhi_mismatch_count = sum(
            expected_cycle.gan_zhi != actual_cycle.gan_zhi
            for expected_cycle, actual_cycle in aligned_luck_cycles
        )
        if stem_mismatch_count == 0 and branch_mismatch_count > 0 and gan_zhi_mismatch_count == branch_mismatch_count:
            tags.append("luck_cycle_branch_only_mismatch")
            recommended_actions.append(
                "Compare DaYun branch progression rules separately; stems already align while branches diverge."
            )
    else:
        stem_mismatch_count = 0
        branch_mismatch_count = 0
        gan_zhi_mismatch_count = 0

    for tag in expected_sequence_tags:
        if tag not in tags:
            tags.append(tag)
    if "expected_luck_cycle_tail_anomaly" in expected_sequence_tags:
        recommended_actions.append(
            "Verify the answer sheet tail row; the expected DaYun sequence is consecutive until the last step and then breaks."
        )
    if "expected_luck_cycle_nonconsecutive" in expected_sequence_tags:
        recommended_actions.append(
            "Verify the answer sheet DaYun sequence; the expected rows themselves do not follow a consecutive 60-cycle progression."
        )
    if "expected_luck_cycle_unparseable" in expected_sequence_tags:
        recommended_actions.append(
            "Verify the answer sheet DaYun labels; at least one expected gan-zhi row could not be parsed into the standard 60-cycle."
        )

    if not tags and mismatch_path_set:
        tags.append("unclassified_mismatch")

    return {
        "tags": tags,
        "recommended_actions": recommended_actions,
        "context": {
            "expected_luck_cycle_count": len(expected_cycles),
            "actual_luck_cycle_count": len(actual_cycles),
            "expected_luck_cycles": expected_cycles,
            "actual_luck_cycles": actual_cycles,
            "invalid_expected_luck_cycles": invalid_expected_cycles,
            "luck_cycle_stem_mismatch_count": stem_mismatch_count,
            "luck_cycle_branch_mismatch_count": branch_mismatch_count,
            "luck_cycle_gan_zhi_mismatch_count": gan_zhi_mismatch_count,
        },
    }


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
    diagnosis_counts: Counter[str] = Counter()

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
        diagnostics = _build_case_diagnostics(case=case, actual=actual, report=report)
        diagnosis_counts.update(diagnostics["tags"])

        case_summary = {
            "case_id": report.case_id,
            "source_name": report.source_name,
            "success": report.success,
            "compared_leaf_count": report.compared_leaf_count,
            "mismatch_count": report.mismatch_count,
            "mismatch_groups": dict(group_counts),
            "mismatch_fields": dict(field_counts),
            "diagnosis_tags": diagnostics["tags"],
            "recommended_actions": diagnostics["recommended_actions"],
            "diagnostic_context": diagnostics["context"],
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
        "diagnosis_counts": dict(diagnosis_counts),
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
