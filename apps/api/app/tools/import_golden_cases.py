from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

from app.domain.saju.services.parse_golden_answer_text import load_golden_answer_text


CASE_NAME_BY_FILE = {
    "pororo.txt": "뽀로로",
    "aru.txt": "아르",
    "okji.txt": "옥지",
    "lee-hyeonjin.txt": "이현진",
    "gomaebi.txt": "곰애비",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert golden saju answer texts into canonical JSON fixtures.")
    parser.add_argument(
        "--source-dir",
        default=str(Path("tests/golden_cases/source")),
        help="Directory containing source txt files.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path("tests/golden_cases/expected")),
        help="Directory where canonical JSON fixtures will be written.",
    )
    return parser


def import_golden_cases(*, source_dir: Path, output_dir: Path) -> List[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_paths: List[Path] = []

    for source_path in sorted(source_dir.glob("*.txt")):
        source_name = CASE_NAME_BY_FILE.get(source_path.name, source_path.stem)
        case = load_golden_answer_text(
            source_path,
            case_id=source_path.stem,
            source_name=source_name,
        )
        output_path = output_dir / f"{source_path.stem}.json"
        output_path.write_text(
            json.dumps(case.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        generated_paths.append(output_path)
        print(f"generated {output_path}")

    return generated_paths


def main() -> int:
    args = build_parser().parse_args()
    source_dir = Path(args.source_dir)
    output_dir = Path(args.output_dir)
    import_golden_cases(source_dir=source_dir, output_dir=output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
