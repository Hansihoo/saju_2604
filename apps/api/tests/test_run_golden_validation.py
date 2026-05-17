import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.domain.saju.services import generate_interpretation
from app.tools import run_golden_validation


class RunGoldenValidationTests(unittest.TestCase):
    def test_cli_forces_fallback_provider_by_default(self) -> None:
        observed_provider = {}

        def fake_compare_golden_cases(**_kwargs):
            observed_provider["value"] = generate_interpretation.settings.llm_provider
            return {"total_mismatches": 0}

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "source"
            expected_dir = root / "expected"
            report_dir = root / "report"
            source_dir.mkdir()

            with patch.object(
                sys,
                "argv",
                [
                    "run_golden_validation",
                    "--source-dir",
                    str(source_dir),
                    "--expected-dir",
                    str(expected_dir),
                    "--report-dir",
                    str(report_dir),
                ],
            ), patch(
                "app.tools.run_golden_validation.import_golden_cases",
            ), patch(
                "app.tools.run_golden_validation.compare_golden_cases",
                side_effect=fake_compare_golden_cases,
            ), patch(
                "app.domain.saju.services.generate_interpretation.settings.llm_provider",
                "openai",
            ):
                exit_code = run_golden_validation.main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(observed_provider["value"], "fallback")


if __name__ == "__main__":
    unittest.main()
