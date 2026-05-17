import json
import unittest
from pathlib import Path
from unittest.mock import patch

from app.domain.saju.golden import GoldenKnownAnswerCase, compare_golden_snapshots
from app.domain.saju.pydantic_compat import model_from_json, model_to_dict
from app.domain.saju.services.build_golden_snapshot import build_actual_golden_snapshot


EXPECTED_DIR = Path(__file__).parent / "golden_cases" / "expected"


class GoldenKnownAnswerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._llm_provider_patch = patch(
            "app.domain.saju.services.generate_interpretation.settings.llm_provider",
            "fallback",
        )
        self._llm_provider_patch.start()
        self.addCleanup(self._llm_provider_patch.stop)

    def test_known_answer_cases_match_canonical_snapshot(self) -> None:
        mismatched_reports = []

        for expected_path in sorted(EXPECTED_DIR.glob("*.json")):
            case = model_from_json(GoldenKnownAnswerCase, expected_path.read_text(encoding="utf-8"))
            actual = build_actual_golden_snapshot(case_input=case.input)
            report = compare_golden_snapshots(case=case, actual=actual)
            if not report.success:
                mismatched_reports.append(model_to_dict(report))

        if mismatched_reports:
            self.fail(json.dumps(mismatched_reports, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    unittest.main()
