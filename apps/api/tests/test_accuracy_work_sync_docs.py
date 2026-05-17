from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
ROADMAP_PATH = REPO_ROOT / "docs" / "planning" / "027-saju-accuracy-improvement-roadmap.md"
SYNC_PATH = REPO_ROOT / "docs" / "planning" / "028-accuracy-work-sync.md"
LUNAR_TABLE_STRATEGY_PATH = REPO_ROOT / "docs" / "planning" / "031-lunar-reference-table-strategy.md"
SOLAR_TERM_TABLE_STRATEGY_PATH = REPO_ROOT / "docs" / "planning" / "032-solar-term-reference-table-strategy.md"


class AccuracyWorkSyncDocsTests(unittest.TestCase):
    def test_roadmap_and_sync_docs_exist(self) -> None:
        self.assertTrue(ROADMAP_PATH.exists())
        self.assertTrue(SYNC_PATH.exists())
        self.assertTrue(LUNAR_TABLE_STRATEGY_PATH.exists())
        self.assertTrue(SOLAR_TERM_TABLE_STRATEGY_PATH.exists())

    def test_roadmap_tracks_all_accuracy_item_ids(self) -> None:
        content = ROADMAP_PATH.read_text(encoding="utf-8")

        for index in range(1, 21):
            self.assertIn(f"A{index:02d}", content)

        self.assertIn("accuracy_mode=legacy", content)
        self.assertIn("corrected_solar_datetime", content)
        self.assertIn("KASI", content)

    def test_sync_doc_source_of_truth_paths_exist(self) -> None:
        content = SYNC_PATH.read_text(encoding="utf-8")
        expected_paths = [
            "docs/planning/027-saju-accuracy-improvement-roadmap.md",
            "docs/planning/029-saju-calculation-source-map.md",
            "docs/planning/030-golden-reference-coverage.md",
            "docs/planning/031-lunar-reference-table-strategy.md",
            "docs/planning/032-solar-term-reference-table-strategy.md",
            "docs/planning/016-golden-answer-validation-system.md",
            "docs/planning/017-daeun-formula-validation-update.md",
            "apps/api/tests/reports/accuracy_mode_diff_report.md",
            "apps/api/tests/reports/canonical_year_month_diff_report.md",
            "apps/api/tests/reports/lunar_reference_diff_report.md",
            "apps/api/tests/fixtures/reference_cases/",
            "apps/api/app/domain/saju/data/lunar_reference/",
            "apps/api/app/domain/saju/data/solar_terms_reference/",
        ]

        for relative_path in expected_paths:
            with self.subTest(relative_path=relative_path):
                self.assertIn(relative_path, content)
                self.assertTrue((REPO_ROOT / relative_path).exists())

    def test_sync_doc_keeps_next_checklist_and_validation_commands(self) -> None:
        content = SYNC_PATH.read_text(encoding="utf-8")

        self.assertIn("## Next Checklist", content)
        self.assertIn("pnpm test:api", content)
        self.assertIn("python -m app.tools.build_lunar_reference_table --check", content)
        self.assertIn("python -m app.tools.build_solar_term_reference_table --check", content)
        self.assertIn("python -m app.tools.run_golden_validation", content)
        self.assertIn("python tests/generate_accuracy_mode_diff_report.py", content)
        self.assertIn("python tests/generate_canonical_year_month_diff_report.py", content)
        self.assertIn("scripts/accuracy-safety-check.ps1", content)

    def test_lunar_reference_strategy_records_runtime_boundary(self) -> None:
        content = LUNAR_TABLE_STRATEGY_PATH.read_text(encoding="utf-8")

        self.assertIn("kasi_lunar_calendar_1900_2050", content)
        self.assertIn("55152", content)
        self.assertIn("normalize_calendar()", content)
        self.assertIn("accuracy_mode=legacy", content)
        self.assertIn("corrected_solar_datetime", content)

    def test_solar_term_reference_strategy_records_resume_boundary(self) -> None:
        content = SOLAR_TERM_TABLE_STRATEGY_PATH.read_text(encoding="utf-8")

        self.assertIn("kasi_solar_terms_common_years", content)
        self.assertIn("2011-2027", content)
        self.assertIn("408", content)
        self.assertIn("collection.log.jsonl", content)
        self.assertIn("--limit", content)
        self.assertIn("primary calculation path", content)


if __name__ == "__main__":
    unittest.main()
