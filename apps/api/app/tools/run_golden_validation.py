from __future__ import annotations

import argparse
from pathlib import Path

from app.tools.compare_golden_cases import compare_golden_cases
from app.tools.import_golden_cases import import_golden_cases


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Refresh canonical golden fixtures from source answers and compare them against current output."
    )
    parser.add_argument(
        "--source-dir",
        default=str(Path("tests/golden_cases/source")),
        help="Directory containing source txt answer files.",
    )
    parser.add_argument(
        "--expected-dir",
        default=str(Path("tests/golden_cases/expected")),
        help="Directory where canonical JSON fixtures will be written.",
    )
    parser.add_argument(
        "--report-dir",
        default=str(Path("tests/golden_reports/latest")),
        help="Directory where actual snapshots and diff reports will be written.",
    )
    parser.add_argument(
        "--fail-on-mismatch",
        action="store_true",
        help="Return a non-zero exit code if any case mismatches.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    source_dir = Path(args.source_dir)
    expected_dir = Path(args.expected_dir)
    report_dir = Path(args.report_dir)

    import_golden_cases(source_dir=source_dir, output_dir=expected_dir)
    summary = compare_golden_cases(
        expected_dir=expected_dir,
        report_dir=report_dir,
        summary_file=report_dir / "summary.json",
    )

    if args.fail_on_mismatch and int(summary["total_mismatches"]) > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
