import json
import os
import unittest
from pathlib import Path

from app.domain.saju.golden import GoldenKnownAnswerCase, compare_golden_snapshots
from app.domain.saju.services.build_golden_snapshot import build_actual_golden_snapshot


EXPECTED_DIR = Path(__file__).parent / "golden_cases" / "expected"


@unittest.skipUnless(
    os.environ.get("SAJU_RUN_GOLDEN_ASSERT") == "1",
    "Set SAJU_RUN_GOLDEN_ASSERT=1 to run strict golden-answer comparisons.",
)
class GoldenKnownAnswerTests(unittest.TestCase):
    def test_known_answer_cases_match_canonical_snapshot(self) -> None:
        mismatched_reports = []

        for expected_path in sorted(EXPECTED_DIR.glob("*.json")):
            case = GoldenKnownAnswerCase.model_validate_json(expected_path.read_text(encoding="utf-8"))
            actual = build_actual_golden_snapshot(case_input=case.input)
            report = compare_golden_snapshots(case=case, actual=actual)
            if not report.success:
                mismatched_reports.append(report.model_dump())

        if mismatched_reports:
            self.fail(json.dumps(mismatched_reports, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    unittest.main()
