import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.api.routes import create_saju_preview
from app.domain.saju.schemas import SajuPreviewRequest


def _alias_ids(candidate):
    return {candidate.candidate_id, *candidate.aliases}


def _find_candidate(response, candidate_id):
    for candidate in response.debug_trace.candidate_charts:
        if candidate_id in _alias_ids(candidate):
            return candidate
    raise AssertionError(f"Candidate {candidate_id} not found")


def _pillar_snapshot(response):
    return {
        "year": response.manse.pillars.year.gan_zhi,
        "month": response.manse.pillars.month.gan_zhi,
        "day": response.manse.pillars.day.gan_zhi,
        "time": response.manse.pillars.time.gan_zhi,
    }


def _candidate_snapshot(candidate):
    return {
        "year": candidate.year_pillar,
        "month": candidate.month_pillar,
        "day": candidate.day_pillar,
        "time": candidate.hour_pillar,
    }


def _first_luck_snapshot(response):
    first = response.manse.luck_cycles[0] if response.manse.luck_cycles else None
    if first is None:
        return None
    return {
        "gan_zhi": first.gan_zhi,
        "start_age": first.start_age,
    }


class AccuracyModeTests(unittest.TestCase):
    def _preview(
        self,
        *,
        accuracy_mode=None,
        birth_date: str = "2024-02-10",
        birth_time: str = "01:10",
        debug: bool = True,
    ):
        request = SimpleNamespace(
            state=SimpleNamespace(
                trace_id=f"accuracy-{accuracy_mode or 'omitted'}",
                debug_requested=debug,
            )
        )
        payload_data = {
            "calendar_type": "solar",
            "birth_date": birth_date,
            "birth_time": birth_time,
            "is_birth_time_estimated": False,
            "is_lunar_leap_month": False,
            "gender": "male",
            "region_id": "kr-seoul",
            "debug": debug,
        }
        if accuracy_mode is not None:
            payload_data["accuracy_mode"] = accuracy_mode
        payload = SajuPreviewRequest(**payload_data)
        with patch("app.domain.saju.services.generate_interpretation.settings.llm_provider", "fallback"):
            return create_saju_preview(payload=payload, request=request)

    def test_omitted_accuracy_mode_defaults_to_legacy(self) -> None:
        response = self._preview(accuracy_mode=None)

        self.assertEqual(response.result.calculation_basis.accuracy_mode, "legacy")
        self.assertEqual(response.result.calculation_basis.primary_candidate_id, "legacy_corrected")
        self.assertEqual(
            response.result.calculation_basis.primary_input_datetime_to_lunar_python,
            response.regional_solar_correction.corrected_solar_datetime,
        )
        self.assertEqual(
            response.result.calculation_basis.primary_day_pillar_basis_datetime,
            response.calendar_normalization.normalized_solar_datetime,
        )

    def test_legacy_mode_matches_omitted_mode(self) -> None:
        omitted = self._preview(accuracy_mode=None)
        legacy = self._preview(accuracy_mode="legacy")

        self.assertEqual(_pillar_snapshot(legacy), _pillar_snapshot(omitted))
        self.assertEqual(_first_luck_snapshot(legacy), _first_luck_snapshot(omitted))
        self.assertEqual(
            legacy.regional_solar_correction.corrected_solar_datetime,
            omitted.regional_solar_correction.corrected_solar_datetime,
        )

    def test_standard_time_uses_standard_local_candidate_as_primary(self) -> None:
        response = self._preview(accuracy_mode="standard_time")
        standard_candidate = _find_candidate(response, "standard_local")

        self.assertEqual(response.result.calculation_basis.accuracy_mode, "standard_time")
        self.assertEqual(response.result.calculation_basis.primary_candidate_id, "standard_local")
        self.assertEqual(
            response.result.calculation_basis.primary_day_pillar_basis_datetime,
            standard_candidate.day_pillar_basis_datetime,
        )
        self.assertEqual(_pillar_snapshot(response), _candidate_snapshot(standard_candidate))
        self.assertEqual(response.manse.luck_cycles[0].start_age, standard_candidate.luck_cycle_start_age)
        self.assertEqual(response.manse.luck_cycles[0].gan_zhi, standard_candidate.luck_cycle_first_ganzhi)
        self.assertEqual(standard_candidate.differences_from_primary, {})

    def test_mean_solar_time_uses_mean_solar_candidate_as_primary(self) -> None:
        response = self._preview(accuracy_mode="mean_solar_time")
        mean_candidate = _find_candidate(response, "mean_solar")

        self.assertEqual(response.result.calculation_basis.accuracy_mode, "mean_solar_time")
        self.assertEqual(response.result.calculation_basis.primary_candidate_id, "mean_solar")
        self.assertEqual(
            response.result.calculation_basis.primary_input_datetime_to_lunar_python,
            mean_candidate.input_datetime_to_lunar_python,
        )
        if mean_candidate.candidate_id == "mean_solar":
            self.assertEqual(
                response.result.calculation_basis.primary_day_pillar_basis_datetime,
                mean_candidate.day_pillar_basis_datetime,
            )
        self.assertEqual(_pillar_snapshot(response), _candidate_snapshot(mean_candidate))
        self.assertEqual(response.manse.luck_cycles[0].start_age, mean_candidate.luck_cycle_start_age)
        self.assertEqual(response.manse.luck_cycles[0].gan_zhi, mean_candidate.luck_cycle_first_ganzhi)
        self.assertEqual(mean_candidate.differences_from_primary, {})

    def test_compare_mode_keeps_legacy_primary_and_exposes_candidates_in_debug(self) -> None:
        compare = self._preview(accuracy_mode="compare")
        legacy = self._preview(accuracy_mode="legacy")

        self.assertEqual(_pillar_snapshot(compare), _pillar_snapshot(legacy))
        self.assertEqual(_first_luck_snapshot(compare), _first_luck_snapshot(legacy))
        self.assertEqual(compare.result.calculation_basis.accuracy_mode, "compare")
        self.assertEqual(compare.result.calculation_basis.primary_candidate_id, "legacy_corrected")
        self.assertTrue(compare.result.calculation_basis.compare_candidates_enabled)
        self.assertTrue(compare.debug_trace.candidate_charts)
        self.assertTrue(compare.debug_trace.uncertainty_flags)

    def test_existing_payload_without_accuracy_mode_still_parses(self) -> None:
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

        self.assertEqual(payload.accuracy_mode, "legacy")


if __name__ == "__main__":
    unittest.main()
