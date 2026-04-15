"""이 파일은 골든 케이스 cases을 비교하는 로직을 담는다."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from math import floor
from pathlib import Path
from typing import Dict, List

from app.domain.saju.adapters.lunar_python_engine import LunarPythonSajuEngine
from app.domain.saju.golden import (
    GoldenKnownAnswerCase,
    compare_golden_snapshots,
    to_korean_gan_zhi,
)
from app.domain.saju.services.calculate_luck_cycles import (
    get_adjacent_month_boundary,
    get_luck_direction,
    LUCK_CYCLE_YEAR_TO_DAY_FACTOR,
    TROPICAL_YEAR_DAYS,
)
from app.domain.saju.services.build_golden_snapshot import build_actual_golden_snapshot
from app.domain.saju.services.region_catalog import find_region_by_id
from app.domain.saju.time_correction import STANDARD_OFFSET_BY_TZ, apply_regional_solar_correction

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
BRANCHES_KO = ["자", "축", "인", "묘", "진", "사", "오", "미", "신", "유", "술", "해"]
SOLAR_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
ENGINE = LunarPythonSajuEngine()


def _group_path(path: str) -> str:
    """경로 관련 값을 반환하거나 처리한다."""
    if "[" in path:
        return path.split("[", 1)[0]
    return path.split(".", 1)[0]


def _field_path(path: str) -> str:
    """경로 관련 값을 반환하거나 처리한다."""
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
    """zhi index 관련 값을 반환하거나 처리한다."""
    try:
        return JIA_ZI_KO.index(value)
    except ValueError:
        return None


def _branch_index(value: str) -> int | None:
    """index 관련 값을 반환하거나 처리한다."""
    try:
        return BRANCHES_KO.index(value)
    except ValueError:
        return None


def _shift_korean_ganzhi(value: str, steps: int) -> str | None:
    """korean ganzhi을 이동한다."""
    index = _gan_zhi_index(value)
    if index is None:
        return None
    return JIA_ZI_KO[(index + steps) % len(JIA_ZI_KO)]


def _analyze_branch_sequence(values: List[str]) -> Dict[str, object]:
    """branch sequence 관련 값을 반환하거나 처리한다."""
    if len(values) < 2:
        return {"tags": [], "invalid_values": [], "deltas": []}

    indexed_values = [(value, _branch_index(value)) for value in values]
    invalid_values = [value for value, index in indexed_values if index is None]
    if invalid_values:
        return {
            "tags": ["branch_sequence_unparseable"],
            "invalid_values": invalid_values,
            "deltas": [],
        }

    indexes = [index for _, index in indexed_values if index is not None]
    deltas = [((indexes[i + 1] - indexes[i]) % 12) for i in range(len(indexes) - 1)]
    unique_deltas = set(deltas)

    if len(unique_deltas) == 1 and unique_deltas.issubset({1, 11}):
        return {"tags": [], "invalid_values": [], "deltas": deltas}

    if len(deltas) >= 2 and len(set(deltas[:-1])) == 1 and deltas[:-1][0] in {1, 11} and deltas[-1] != deltas[:-1][0]:
        return {
            "tags": ["branch_sequence_tail_anomaly"],
            "invalid_values": [],
            "deltas": deltas,
        }

    return {
        "tags": ["branch_sequence_nonstandard"],
        "invalid_values": [],
        "deltas": deltas,
    }


def _analyze_expected_luck_cycle_sequence(expected_cycles: List[str]) -> Dict[str, object]:
    """expected 대운 대운 sequence 관련 값을 반환하거나 처리한다."""
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


def _build_start_age_rule_context(case: GoldenKnownAnswerCase) -> Dict[str, object]:
    """start age rule context을 조립한다."""
    region = find_region_by_id(case.input.region_id)
    normalized_solar_datetime = f"{case.input.birth_date} {case.input.birth_time}:00"
    regional_result = apply_regional_solar_correction(
        normalized_solar_datetime=normalized_solar_datetime,
        longitude=region.longitude,
        regional_time_offset_minutes=region.regional_time_offset_minutes,
        daylight_saving_offset_minutes=0,
        correction_basis=region.correction_basis,
    )
    corrected_dt = datetime.strptime(
        regional_result.corrected_solar_datetime,
        SOLAR_DATETIME_FORMAT,
    )
    calculation = ENGINE.calculate(
        corrected_solar_datetime=regional_result.corrected_solar_datetime,
        gender=case.input.gender,
        tzid=region.tzid,
    )
    direction = get_luck_direction(calculation.pillars["year"].stem, case.input.gender)
    boundary_dt = get_adjacent_month_boundary(
        corrected_dt,
        direction,
        target_standard_offset_minutes=STANDARD_OFFSET_BY_TZ.get(region.tzid),
    )
    delta_days = abs((boundary_dt - corrected_dt).total_seconds()) / 86400
    exact_start_age_years = delta_days / 3.0
    precise_start_age_years = delta_days * LUCK_CYCLE_YEAR_TO_DAY_FACTOR / TROPICAL_YEAR_DAYS
    date_diff = abs((boundary_dt.date() - corrected_dt.date()).days)

    q, r = divmod(date_diff, 3)
    q_exclusive, r_exclusive = divmod(max(date_diff - 1, 0), 3)
    candidate_start_ages = {
        "current_day_count_r2": q + 1 if r == 2 else q,
        "exclude_both_day_count_r2": (
            q_exclusive + 1 if r_exclusive == 2 else q_exclusive
        ),
        "floor_exact": int(exact_start_age_years),
        "ceil_exact": int(-(-exact_start_age_years // 1)),
        "round_exact": floor(exact_start_age_years + 0.5),
        "floor_precise": int(precise_start_age_years),
        "ceil_precise": int(-(-precise_start_age_years // 1)),
        "round_precise": floor(precise_start_age_years + 0.5),
    }
    expected_first_age = case.expected.luck_cycles[0].start_age if case.expected.luck_cycles else None
    matched_rules = [
        rule_name
        for rule_name, candidate_age in candidate_start_ages.items()
        if candidate_age == expected_first_age
    ]

    return {
        "corrected_solar_datetime": regional_result.corrected_solar_datetime,
        "month_boundary_datetime": boundary_dt.strftime(SOLAR_DATETIME_FORMAT),
        "direction": direction,
        "year_pillar": calculation.pillars["year"].gan_zhi,
        "month_pillar": to_korean_gan_zhi(calculation.pillars["month"].gan_zhi),
        "exact_start_age_years": exact_start_age_years,
        "precise_start_age_years": precise_start_age_years,
        "date_diff_days": date_diff,
        "candidate_start_ages": candidate_start_ages,
        "matched_expected_start_age_rules": matched_rules,
    }


def _build_case_diagnostics(*, case: GoldenKnownAnswerCase, actual: object, report: object) -> Dict[str, object]:
    """케이스 진단 로깅을 조립한다."""
    mismatch_paths = [mismatch.path for mismatch in report.mismatches]
    mismatch_path_set = set(mismatch_paths)
    tags: List[str] = []
    recommended_actions: List[str] = []

    expected_cycles = [cycle.gan_zhi for cycle in case.expected.luck_cycles]
    actual_cycles = [cycle.gan_zhi for cycle in actual.luck_cycles]
    expected_branches = [cycle.branch for cycle in case.expected.luck_cycles]
    actual_branches = [cycle.branch for cycle in actual.luck_cycles]
    expected_start_ages = [cycle.start_age for cycle in case.expected.luck_cycles]
    actual_start_ages = [cycle.start_age for cycle in actual.luck_cycles]
    aligned_luck_cycles = list(zip(case.expected.luck_cycles, actual.luck_cycles))
    expected_sequence_analysis = _analyze_expected_luck_cycle_sequence(expected_cycles)
    actual_sequence_analysis = _analyze_expected_luck_cycle_sequence(actual_cycles)
    expected_branch_analysis = _analyze_branch_sequence(expected_branches)
    actual_branch_analysis = _analyze_branch_sequence(actual_branches)
    start_age_rule_context = _build_start_age_rule_context(case)
    expected_sequence_tags = expected_sequence_analysis["tags"]
    invalid_expected_cycles = expected_sequence_analysis["invalid_values"]
    header = case.expected.luck_cycle_header
    header_matches_actual_month_pillar = False
    expected_matches_header_sequence = None
    actual_matches_header_sequence = None
    if header is not None:
        header_matches_actual_month_pillar = (
            header.reference_pillar == start_age_rule_context["month_pillar"]
        )
        direction_step = 1 if start_age_rule_context["direction"] == "forward" else -1
        first_pillar_from_header = _shift_korean_ganzhi(header.reference_pillar, direction_step)
        if first_pillar_from_header is not None:
            expected_matches_header_sequence = True
            actual_matches_header_sequence = True
            for index, value in enumerate(expected_cycles):
                expected_value = _shift_korean_ganzhi(first_pillar_from_header, direction_step * index)
                if expected_value != value:
                    expected_matches_header_sequence = False
                    break
            for index, value in enumerate(actual_cycles):
                expected_value = _shift_korean_ganzhi(first_pillar_from_header, direction_step * index)
                if expected_value != value:
                    actual_matches_header_sequence = False
                    break

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

    if luck_cycle_paths and all(path.endswith(".start_age") for path in luck_cycle_paths):
        tags.append("luck_cycle_start_age_only_mismatch")
        recommended_actions.append(
            "Review DaYun start-age rounding/truncation rules; gan-zhi progression matches while the displayed start ages are offset."
        )

    if any(path.endswith(".start_age") for path in luck_cycle_paths):
        tags.append("luck_cycle_start_age_mismatch_present")
        recommended_actions.append(
            "Review DaYun start-age display rules separately from gan-zhi progression; the current output differs on one or more displayed start ages."
        )
        matched_rules = start_age_rule_context["matched_expected_start_age_rules"]
        if matched_rules:
            tags.append("expected_start_age_matches_alternative_rule")
            recommended_actions.append(
                "Compare the answer sheet against alternative displayed-age conventions; "
                f"the expected first age matches: {', '.join(matched_rules)}."
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
        start_age_mismatch_count = sum(
            expected_cycle.start_age != actual_cycle.start_age
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
        start_age_mismatch_count = 0

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

    if "branch_sequence_nonstandard" in expected_branch_analysis["tags"]:
        tags.append("expected_luck_cycle_branch_nonstandard")
        recommended_actions.append(
            "Verify the answer sheet DaYun branch sequence; the branch column does not follow a standard consecutive forward/reverse progression."
        )
    if "branch_sequence_tail_anomaly" in expected_branch_analysis["tags"]:
        tags.append("expected_luck_cycle_branch_tail_anomaly")
        recommended_actions.append(
            "Verify the answer sheet DaYun branch tail; the branch column is consecutive until the last row and then breaks."
        )
    if "branch_sequence_unparseable" in expected_branch_analysis["tags"]:
        tags.append("expected_luck_cycle_branch_unparseable")
        recommended_actions.append(
            "Verify the answer sheet DaYun branch labels; at least one branch value could not be parsed."
        )

    if (
        stem_mismatch_count == 0
        and not actual_sequence_analysis["tags"]
        and not actual_branch_analysis["tags"]
        and (
            "expected_luck_cycle_unparseable" in expected_sequence_tags
            or "expected_luck_cycle_nonconsecutive" in expected_sequence_tags
            or "expected_luck_cycle_tail_anomaly" in expected_sequence_tags
            or "branch_sequence_nonstandard" in expected_branch_analysis["tags"]
            or "branch_sequence_tail_anomaly" in expected_branch_analysis["tags"]
            or "branch_sequence_unparseable" in expected_branch_analysis["tags"]
        )
    ):
        tags.append("expected_answer_sheet_suspect")
        recommended_actions.append(
            "Verify the answer sheet before changing the engine; the expected DaYun rows look non-standard while the engine output remains consecutive."
        )

    if (
        header is not None
        and header_matches_actual_month_pillar
        and actual_matches_header_sequence is True
        and expected_matches_header_sequence is False
    ):
        tags.append("expected_luck_cycle_inconsistent_with_header")
        recommended_actions.append(
            "The answer-sheet DaYun rows do not follow the sequence implied by its own header month-pillar reference."
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
            "expected_luck_cycle_start_ages": expected_start_ages,
            "actual_luck_cycle_start_ages": actual_start_ages,
            "invalid_expected_luck_cycles": invalid_expected_cycles,
            "expected_luck_cycle_sequence_tags": expected_sequence_analysis["tags"],
            "actual_luck_cycle_sequence_tags": actual_sequence_analysis["tags"],
            "expected_luck_cycle_branches": expected_branches,
            "actual_luck_cycle_branches": actual_branches,
            "expected_branch_sequence_tags": expected_branch_analysis["tags"],
            "expected_branch_deltas": expected_branch_analysis["deltas"],
            "actual_branch_sequence_tags": actual_branch_analysis["tags"],
            "actual_branch_deltas": actual_branch_analysis["deltas"],
            "luck_cycle_stem_mismatch_count": stem_mismatch_count,
            "luck_cycle_branch_mismatch_count": branch_mismatch_count,
            "luck_cycle_gan_zhi_mismatch_count": gan_zhi_mismatch_count,
            "luck_cycle_start_age_mismatch_count": start_age_mismatch_count,
            "actual_luck_cycle_direction": start_age_rule_context["direction"],
            "actual_month_boundary_datetime": start_age_rule_context["month_boundary_datetime"],
            "actual_exact_start_age_years": start_age_rule_context["exact_start_age_years"],
            "actual_precise_start_age_years": start_age_rule_context["precise_start_age_years"],
            "actual_year_pillar": start_age_rule_context["year_pillar"],
            "actual_month_pillar": start_age_rule_context["month_pillar"],
            "start_age_rule_date_diff_days": start_age_rule_context["date_diff_days"],
            "candidate_start_ages": start_age_rule_context["candidate_start_ages"],
            "matched_expected_start_age_rules": start_age_rule_context[
                "matched_expected_start_age_rules"
            ],
            "luck_cycle_header_reference_pillar": (
                header.reference_pillar if header is not None else None
            ),
            "luck_cycle_header_start_age": header.start_age if header is not None else None,
            "luck_cycle_header_matches_actual_month_pillar": header_matches_actual_month_pillar,
            "expected_matches_header_sequence": expected_matches_header_sequence,
            "actual_matches_header_sequence": actual_matches_header_sequence,
        },
    }


def _classify_case_status(*, report: object, diagnostics: Dict[str, object]) -> str:
    """케이스 상태 관련 값을 반환하거나 처리한다."""
    if report.success:
        return "match"

    mismatch_paths = [mismatch.path for mismatch in report.mismatches]
    reviewable_answer_sheet_paths = (
        "luck_cycles",
        "luck_cycle_header",
    )
    if (
        "expected_answer_sheet_suspect" in diagnostics["tags"]
        and mismatch_paths
        and all(
            path.startswith(reviewable_answer_sheet_paths)
            for path in mismatch_paths
        )
    ):
        return "answer_sheet_review"

    return "engine_review"


def build_parser() -> argparse.ArgumentParser:
    """이 도구에 필요한 CLI 인자 파서를 구성한다."""
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
    """주어진 golden case 디렉터리를 순회하면서 기대값과 실제 결과를 비교한다."""
    actual_dir = report_dir / "actual"
    diff_dir = report_dir / "diff"
    actual_dir.mkdir(parents=True, exist_ok=True)
    diff_dir.mkdir(parents=True, exist_ok=True)

    total_cases = 0
    total_mismatches = 0
    case_summaries: List[Dict[str, object]] = []
    global_field_counts: Counter[str] = Counter()
    diagnosis_counts: Counter[str] = Counter()
    case_status_counts: Counter[str] = Counter()

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
        case_status = _classify_case_status(report=report, diagnostics=diagnostics)
        case_status_counts.update([case_status])

        case_summary = {
            "case_id": report.case_id,
            "source_name": report.source_name,
            "success": report.success,
            "case_status": case_status,
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
        "case_status_counts": dict(case_status_counts),
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
    """이 모듈의 CLI 진입점을 실행한다."""
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
