import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from app.api.routes import create_saju_preview
from app.domain.saju.schemas import SajuPreviewRequest
from app.domain.saju.services.calculate_saju import calculate_saju
from app.domain.saju.services.generate_candidate_charts import generate_candidate_charts
from app.domain.saju.time_correction import (
    apply_regional_solar_correction,
    build_birth_time_context,
    normalize_birth_datetime,
)


def _alias_ids(candidate):
    return {candidate.candidate_id, *candidate.aliases}


def _find_candidate(response, candidate_id):
    for candidate in response.debug_trace.candidate_charts:
        if candidate_id in _alias_ids(candidate):
            return candidate
    raise AssertionError(f"Candidate {candidate_id} not found")


class CandidateChartTests(unittest.TestCase):
    def _preview(self, *, birth_date: str, birth_time: str, region_id: str = "kr-seoul"):
        request = SimpleNamespace(
            state=SimpleNamespace(
                trace_id=f"candidate-{birth_date}-{birth_time}",
                debug_requested=True,
            )
        )
        payload = SajuPreviewRequest(
            calendar_type="solar",
            birth_date=birth_date,
            birth_time=birth_time,
            is_birth_time_estimated=False,
            is_lunar_leap_month=False,
            gender="male",
            region_id=region_id,
            debug=True,
        )
        with patch("app.domain.saju.services.generate_interpretation.settings.llm_provider", "fallback"):
            return create_saju_preview(payload=payload, request=request)

    def test_regular_case_dedupes_equivalent_candidates(self) -> None:
        response = self._preview(birth_date="2024-02-10", birth_time="10:30")

        self.assertEqual(len(response.debug_trace.candidate_charts), 1)
        candidate = response.debug_trace.candidate_charts[0]
        self.assertEqual(candidate.candidate_id, "legacy_corrected")
        self.assertEqual(candidate.differences_from_primary, {})
        self.assertIsNotNone(candidate.luck_cycle_start_age_total_months)
        self.assertEqual(
            set(candidate.aliases),
            {
                "standard_local",
                "mean_solar",
                "sect1_23_changes_day",
                "sect2_00_changes_day",
            },
        )

    def test_late_zi_case_keeps_sect1_and_sect2_day_rule_difference(self) -> None:
        response = self._preview(
            birth_date="1988-11-20",
            birth_time="23:30",
            region_id="kr-seoul-special",
        )

        sect1 = _find_candidate(response, "sect1_23_changes_day")
        sect2 = _find_candidate(response, "sect2_00_changes_day")

        self.assertEqual(sect1.day_pillar_basis_datetime, "1988-11-20 23:30:00")
        self.assertEqual(sect1.iljin_query_date, "1988-11-21")
        self.assertEqual(sect2.input_datetime_to_lunar_python, "1988-11-20 23:30:00")
        self.assertEqual(sect2.day_pillar_basis_datetime, "1988-11-20 23:30:00")
        self.assertEqual(sect2.iljin_query_date, "1988-11-20")
        self.assertNotEqual(sect1.day_pillar, sect2.day_pillar)
        self.assertEqual(sect1.midnight_rule, "sect1_23_changes_day")
        self.assertEqual(sect2.midnight_rule, "sect2_00_changes_day")

    def test_dawn_boundary_standard_local_can_change_hour_pillar(self) -> None:
        response = self._preview(birth_date="2024-02-10", birth_time="01:10")

        legacy = _find_candidate(response, "legacy_corrected")
        standard_local = _find_candidate(response, "standard_local")

        self.assertIn("mean_solar", legacy.aliases)
        self.assertNotEqual(legacy.hour_pillar, standard_local.hour_pillar)
        self.assertIn("hour_pillar", standard_local.differences_from_primary)

    def test_candidate_charts_are_only_exposed_inside_debug_trace(self) -> None:
        request = SimpleNamespace(
            state=SimpleNamespace(
                trace_id="candidate-debug-disabled",
                debug_requested=False,
            )
        )
        payload = SajuPreviewRequest(
            calendar_type="solar",
            birth_date="2024-02-10",
            birth_time="10:30",
            is_birth_time_estimated=False,
            is_lunar_leap_month=False,
            gender="male",
            region_id="kr-seoul",
            debug=False,
        )

        with patch("app.domain.saju.services.generate_interpretation.settings.llm_provider", "fallback"):
            response = create_saju_preview(payload=payload, request=request)

        self.assertIsNone(response.debug_trace)
        self.assertFalse(hasattr(response.result, "candidate_charts"))

    def test_ambiguous_local_time_adds_fold_aliases_when_equivalent(self) -> None:
        time_correction = normalize_birth_datetime(
            birth_date=date(2024, 11, 3),
            birth_time="01:30",
            tzid="America/New_York",
        )
        regional_solar_correction = apply_regional_solar_correction(
            normalized_solar_datetime="2024-11-03 01:30:00",
            longitude=-74.006,
            regional_time_offset_minutes=3.976,
            daylight_saving_offset_minutes=0,
            correction_basis="test-standard-meridian-longitude",
        )
        birth_time_context = build_birth_time_context(
            time_correction=time_correction,
            normalized_solar_datetime="2024-11-03 01:30:00",
            regional_solar_correction=regional_solar_correction,
        )
        primary_calculation = calculate_saju(
            corrected_solar_datetime=regional_solar_correction.corrected_solar_datetime,
            gender="male",
            tzid="America/New_York",
        )

        candidates = generate_candidate_charts(
            birth_time_context=birth_time_context,
            time_correction=time_correction,
            primary_calculation=primary_calculation,
            gender="male",
            tzid="America/New_York",
        )

        aliases = set()
        for candidate in candidates:
            aliases.update(_alias_ids(candidate))
        self.assertIn("fold_0", aliases)
        self.assertIn("fold_1", aliases)


if __name__ == "__main__":
    unittest.main()
