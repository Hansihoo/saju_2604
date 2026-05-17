"""이 파일은 골든 케이스 validation을 실행하는 로직을 담는다."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.domain.saju.services import generate_interpretation
from app.tools.compare_golden_cases import compare_golden_cases
from app.tools.import_golden_cases import import_golden_cases


def build_parser() -> argparse.ArgumentParser:
    """이 도구에 필요한 CLI 인자 파서를 구성한다."""
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
    parser.add_argument(
        "--use-configured-llm",
        action="store_true",
        help="Use the configured LLM provider. Defaults to fallback to keep validation deterministic.",
    )
    return parser


def main() -> int:
    """이 모듈의 CLI 진입점을 실행한다."""
    args = build_parser().parse_args()
    source_dir = Path(args.source_dir)
    expected_dir = Path(args.expected_dir)
    report_dir = Path(args.report_dir)

    original_provider = generate_interpretation.settings.llm_provider
    if not args.use_configured_llm:
        generate_interpretation.settings.llm_provider = "fallback"
    try:
        import_golden_cases(source_dir=source_dir, output_dir=expected_dir)
        summary = compare_golden_cases(
            expected_dir=expected_dir,
            report_dir=report_dir,
            summary_file=report_dir / "summary.json",
        )
    finally:
        generate_interpretation.settings.llm_provider = original_provider

    if args.fail_on_mismatch and int(summary["total_mismatches"]) > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
