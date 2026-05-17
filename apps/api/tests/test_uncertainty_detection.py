import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.api.routes import create_saju_preview
from app.domain.saju.schemas import RegionSuggestion, SajuPreviewRequest
from app.domain.saju.services.build_interpretation_payload import build_interpretation_payload


NEW_YORK_REGION = {
    "id": "test-new-york",
    "display_name": "New York, United States",
    "country": "United States",
    "province": "New York",
    "city": "New York",
    "tzid": "America/New_York",
    "longitude": -74.006,
    "regional_time_offset_minutes": 3.976,
    "correction_basis": "test-standard-meridian-longitude",
    "aliases": ["New York", "NYC"],
}

ZERO_CORRECTION_REGION = {
    "id": "test-zero-correction",
    "display_name": "Zero correction, South Korea",
    "country": "South Korea",
    "province": "Test",
    "city": "Zero correction",
    "tzid": "Asia/Seoul",
    "longitude": 135.0,
    "regional_time_offset_minutes": 0.0,
    "correction_basis": "test-no-regional-correction",
    "aliases": ["Zero correction"],
}


def _flag_codes(flags):
    return {flag.code for flag in flags}


class UncertaintyDetectionTests(unittest.TestCase):
    def _preview(
        self,
        *,
        birth_date: str,
        birth_time: str,
        calendar_type: str = "solar",
        is_lunar_leap_month: bool = False,
        is_birth_time_estimated: bool = False,
        gender: str = "male",
        region_id: str = "kr-seoul",
        region_override=None,
        debug: bool = True,
    ):
        request = SimpleNamespace(
            state=SimpleNamespace(
                trace_id=f"uncertainty-{birth_date}-{birth_time}",
                debug_requested=debug,
            )
        )
        payload = SajuPreviewRequest(
            calendar_type=calendar_type,
            birth_date=birth_date,
            birth_time=birth_time,
            is_birth_time_estimated=is_birth_time_estimated,
            is_lunar_leap_month=is_lunar_leap_month,
            gender=gender,
            region_id=region_id,
            debug=debug,
        )
        patches = [
            patch("app.domain.saju.services.generate_interpretation.settings.llm_provider", "fallback"),
        ]
        if region_override is not None:
            patches.append(
                patch(
                    "app.domain.saju.services.preview_orchestrator.find_region_by_id",
                    return_value=RegionSuggestion(**region_override),
                )
            )
        started = []
        try:
            for item in patches:
                started.append(item.start())
            return create_saju_preview(payload=payload, request=request), payload
        finally:
            for item in reversed(patches):
                item.stop()

    def test_birth_time_unknown_flag(self) -> None:
        response, _payload = self._preview(
            birth_date="1994-10-13",
            birth_time="08:30",
            is_birth_time_estimated=True,
        )

        codes = _flag_codes(response.debug_trace.uncertainty_flags)
        self.assertIn("birth_time_unknown", codes)
        self.assertIn("day_pillar_uncertain_due_to_unknown_time", codes)
        self.assertNotIn("near_midnight", codes)
        self.assertNotIn("standard_vs_mean_solar_changes_hour_pillar", codes)
        self.assertNotIn("luck_cycle_start_age_changed", codes)
        self.assertNotIn("primary_differs_from_candidate", codes)
        self.assertNotIn("day_interval_contains_solar_term", codes)
        self.assertNotIn("year_or_month_pillar_may_change", codes)
        self.assertEqual(response.debug_trace.candidate_charts, [])
        self.assertIn(
            "day_pillar_uncertain_due_to_unknown_time",
            _flag_codes(response.result.uncertainty_summary),
        )
        birth_time_unknown = {
            flag.code: flag for flag in response.debug_trace.uncertainty_flags
        }["birth_time_unknown"]
        self.assertEqual(
            birth_time_unknown.evidence["birth_time_interval"],
            {"start": "1994-10-13 00:00:00", "end": "1994-10-13 23:59:59"},
        )
        self.assertTrue(
            any("internal placeholder" in item for item in response.result.limitations)
        )
        self.assertFalse(response.result.hour_pillar_enabled)
        self.assertFalse(response.manse.luck_cycles_enabled)
        self.assertTrue(response.time_correction.is_placeholder_time)
        self.assertEqual(response.time_correction.placeholder_reason, "birth_time_unknown")
        self.assertTrue(response.calendar_normalization.is_placeholder_time)
        self.assertEqual(response.calendar_normalization.placeholder_reason, "birth_time_unknown")
        self.assertTrue(response.regional_solar_correction.is_placeholder_time)
        self.assertEqual(response.regional_solar_correction.placeholder_reason, "birth_time_unknown")

    def test_birth_time_unknown_limits_placeholder_candidate_warnings(self) -> None:
        response, _payload = self._preview(
            birth_date="1988-11-20",
            birth_time="23:30",
            is_birth_time_estimated=True,
            region_id="kr-seoul-special",
        )

        allowed_codes = {
            "birth_time_unknown",
            "day_pillar_uncertain_due_to_unknown_time",
            "day_interval_contains_solar_term",
            "year_or_month_pillar_may_change",
        }
        codes = _flag_codes(response.debug_trace.uncertainty_flags)
        self.assertTrue(codes.issubset(allowed_codes))
        self.assertNotIn("near_midnight", codes)
        self.assertNotIn("standard_vs_mean_solar_changes_hour_pillar", codes)
        self.assertNotIn("luck_cycle_start_age_changed", codes)
        self.assertNotIn("primary_differs_from_candidate", codes)
        self.assertEqual(response.debug_trace.candidate_charts, [])
        self.assertFalse(response.result.hour_pillar_enabled)
        self.assertFalse(response.manse.luck_cycles_enabled)

    def test_birth_time_unknown_public_summary_filters_placeholder_diffs(self) -> None:
        response, _payload = self._preview(
            birth_date="1988-11-20",
            birth_time="23:30",
            is_birth_time_estimated=True,
            region_id="kr-seoul-special",
            debug=False,
        )

        self.assertIsNone(response.debug_trace)
        summary_codes = _flag_codes(response.result.uncertainty_summary)
        forbidden_codes = {
            "near_midnight",
            "standard_vs_mean_solar_changes_hour_pillar",
            "luck_cycle_start_age_changed",
            "primary_differs_from_candidate",
            "midnight_rule_changes_day_pillar",
            "midnight_rule_changes_hour_pillar",
        }
        self.assertTrue(summary_codes.isdisjoint(forbidden_codes))
        self.assertFalse(response.result.hour_pillar_enabled)
        self.assertFalse(response.manse.luck_cycles_enabled)

    def test_unknown_birth_time_solar_term_day_flags_month_change_risk(self) -> None:
        response, _payload = self._preview(
            birth_date="2024-03-05",
            birth_time="10:30",
            is_birth_time_estimated=True,
            region_id="test-zero-correction",
            region_override=ZERO_CORRECTION_REGION,
        )

        flags = {flag.code: flag for flag in response.debug_trace.uncertainty_flags}
        self.assertIn("day_interval_contains_solar_term", flags)
        self.assertIn("year_or_month_pillar_may_change", flags)
        self.assertEqual(flags["day_interval_contains_solar_term"].severity, "info")
        self.assertEqual(flags["year_or_month_pillar_may_change"].severity, "critical")
        self.assertEqual(flags["year_or_month_pillar_may_change"].affected_fields, ["month_pillar"])
        self.assertEqual(
            flags["day_interval_contains_solar_term"].evidence["provider"],
            "solar_term_reference_table",
        )
        self.assertTrue(
            flags["day_interval_contains_solar_term"].evidence["solar_term"]["used_reference"]
        )
        self.assertIn(
            "year_or_month_pillar_may_change",
            _flag_codes(response.result.uncertainty_summary),
        )

    def test_unknown_birth_time_ipchun_day_flags_year_and_month_change_risk(self) -> None:
        response, _payload = self._preview(
            birth_date="2024-02-04",
            birth_time="10:30",
            is_birth_time_estimated=True,
            region_id="test-zero-correction",
            region_override=ZERO_CORRECTION_REGION,
        )

        flags = {flag.code: flag for flag in response.debug_trace.uncertainty_flags}
        self.assertIn("day_interval_contains_solar_term", flags)
        self.assertIn("year_or_month_pillar_may_change", flags)
        self.assertEqual(
            flags["year_or_month_pillar_may_change"].affected_fields,
            ["year_pillar", "month_pillar"],
        )

    def test_known_birth_time_does_not_emit_unknown_interval_flags(self) -> None:
        response, _payload = self._preview(
            birth_date="2024-03-05",
            birth_time="10:30",
            region_id="test-zero-correction",
            region_override=ZERO_CORRECTION_REGION,
        )

        codes = _flag_codes(response.debug_trace.uncertainty_flags)
        self.assertNotIn("birth_time_unknown", codes)
        self.assertNotIn("day_interval_contains_solar_term", codes)
        self.assertNotIn("year_or_month_pillar_may_change", codes)
        self.assertNotIn("day_pillar_uncertain_due_to_unknown_time", codes)
        self.assertFalse(response.time_correction.is_placeholder_time)
        self.assertIsNone(response.time_correction.placeholder_reason)
        self.assertFalse(response.calendar_normalization.is_placeholder_time)
        self.assertIsNone(response.calendar_normalization.placeholder_reason)
        self.assertFalse(response.regional_solar_correction.is_placeholder_time)
        self.assertIsNone(response.regional_solar_correction.placeholder_reason)

    def test_late_zi_midnight_rule_flags(self) -> None:
        response, _payload = self._preview(
            birth_date="1988-11-20",
            birth_time="23:30",
            region_id="kr-seoul-special",
        )

        flags = {flag.code: flag for flag in response.debug_trace.uncertainty_flags}
        self.assertIn("near_midnight", flags)
        self.assertEqual(flags["near_midnight"].severity, "info")
        self.assertEqual(flags["midnight_rule_changes_day_pillar"].severity, "critical")
        self.assertIn("primary_differs_from_candidate", flags)
        self.assertIn(
            "midnight_rule_changes_day_pillar",
            _flag_codes(response.result.uncertainty_summary),
        )

    def test_standard_vs_mean_solar_hour_flag(self) -> None:
        response, _payload = self._preview(
            birth_date="2024-02-10",
            birth_time="01:10",
        )

        flags = {flag.code: flag for flag in response.debug_trace.uncertainty_flags}
        self.assertEqual(flags["standard_vs_mean_solar_changes_hour_pillar"].severity, "warning")
        self.assertIn("hour_pillar", flags["standard_vs_mean_solar_changes_hour_pillar"].affected_fields)

    def test_dst_and_ambiguous_flags(self) -> None:
        dst_response, _payload = self._preview(
            birth_date="1988-05-20",
            birth_time="12:30",
            gender="female",
            region_id="kr-seoul-special",
        )
        self.assertIn("timezone_dst_applied", _flag_codes(dst_response.debug_trace.uncertainty_flags))

        ambiguous_response, _payload = self._preview(
            birth_date="2024-11-03",
            birth_time="01:30",
            region_id="test-new-york",
            region_override=NEW_YORK_REGION,
        )
        self.assertIn("ambiguous_local_time", _flag_codes(ambiguous_response.debug_trace.uncertainty_flags))

    def test_lunar_and_leap_month_flags(self) -> None:
        lunar_response, _payload = self._preview(
            birth_date="2024-01-01",
            birth_time="10:30",
            calendar_type="lunar",
        )
        self.assertIn("lunar_input_used", _flag_codes(lunar_response.debug_trace.uncertainty_flags))

        leap_response, _payload = self._preview(
            birth_date="2023-02-15",
            birth_time="10:30",
            calendar_type="lunar",
            is_lunar_leap_month=True,
            gender="female",
        )
        codes = _flag_codes(leap_response.debug_trace.uncertainty_flags)
        self.assertIn("lunar_input_used", codes)
        self.assertIn("leap_month_input_used", codes)

    def test_regular_case_does_not_emit_warning_or_critical(self) -> None:
        response, _payload = self._preview(
            birth_date="2024-02-10",
            birth_time="10:30",
        )

        self.assertEqual(response.result.uncertainty_summary, [])
        self.assertFalse(
            [
                flag
                for flag in response.debug_trace.uncertainty_flags
                if flag.severity in ("warning", "critical")
            ]
        )

    def test_debug_trace_only_for_full_uncertainty_flags(self) -> None:
        response, _payload = self._preview(
            birth_date="1988-11-20",
            birth_time="23:30",
            region_id="kr-seoul-special",
            debug=False,
        )

        self.assertIsNone(response.debug_trace)
        self.assertTrue(response.result.uncertainty_summary)
        self.assertFalse(hasattr(response.result, "uncertainty_flags"))

    def test_interpretation_payload_receives_precomputed_uncertainty_summary(self) -> None:
        response, payload = self._preview(
            birth_date="1988-11-20",
            birth_time="23:30",
            region_id="kr-seoul-special",
        )

        interpretation_payload = build_interpretation_payload(
            request=payload,
            response=response,
        )

        codes = {flag.code for flag in interpretation_payload.uncertainty_summary}
        self.assertIn("midnight_rule_changes_day_pillar", codes)
        self.assertIn(
            "If uncertainty_summary is present, verbalize only those precomputed uncertainty flags; do not infer new uncertainty.",
            interpretation_payload.narrative_rules,
        )

    def test_near_ipchun_before_flags_year_and_month_as_critical(self) -> None:
        response, _payload = self._preview(
            birth_date="2024-02-04",
            birth_time="16:58",
            region_id="test-zero-correction",
            region_override=ZERO_CORRECTION_REGION,
        )

        flag = {flag.code: flag for flag in response.debug_trace.uncertainty_flags}["near_solar_term"]
        self.assertEqual(flag.severity, "critical")
        self.assertEqual(flag.affected_fields, ["year_pillar", "month_pillar"])
        self.assertEqual(flag.evidence["nearest_solar_term"]["relation"], "before")
        self.assertEqual(flag.evidence["provider"], "solar_term_reference_table")
        self.assertTrue(flag.evidence["nearest_solar_term"]["used_reference"])
        self.assertEqual(
            flag.evidence["nearest_solar_term"]["reference"]["source_role"],
            "official_reference_table",
        )
        self.assertIn("near_solar_term", _flag_codes(response.result.uncertainty_summary))

    def test_near_ipchun_after_flags_year_and_month_as_critical(self) -> None:
        response, _payload = self._preview(
            birth_date="2024-02-04",
            birth_time="17:56",
            region_id="test-zero-correction",
            region_override=ZERO_CORRECTION_REGION,
        )

        flag = {flag.code: flag for flag in response.debug_trace.uncertainty_flags}["near_solar_term"]
        self.assertEqual(flag.severity, "critical")
        self.assertEqual(flag.affected_fields, ["year_pillar", "month_pillar"])
        self.assertEqual(flag.evidence["nearest_solar_term"]["relation"], "after")

    def test_near_gyeongchip_before_flags_month_as_critical(self) -> None:
        response, _payload = self._preview(
            birth_date="2024-03-05",
            birth_time="10:54",
            region_id="test-zero-correction",
            region_override=ZERO_CORRECTION_REGION,
        )

        flag = {flag.code: flag for flag in response.debug_trace.uncertainty_flags}["near_solar_term"]
        self.assertEqual(flag.severity, "critical")
        self.assertEqual(flag.affected_fields, ["month_pillar"])
        self.assertEqual(flag.evidence["nearest_solar_term"]["relation"], "before")

    def test_near_gyeongchip_after_flags_month_as_critical(self) -> None:
        response, _payload = self._preview(
            birth_date="2024-03-05",
            birth_time="11:52",
            region_id="test-zero-correction",
            region_override=ZERO_CORRECTION_REGION,
        )

        flag = {flag.code: flag for flag in response.debug_trace.uncertainty_flags}["near_solar_term"]
        self.assertEqual(flag.severity, "critical")
        self.assertEqual(flag.affected_fields, ["month_pillar"])
        self.assertEqual(flag.evidence["nearest_solar_term"]["relation"], "after")

    def test_near_cheongmyeong_and_ipha_use_reference_boundary_month_risk(self) -> None:
        cases = [
            ("2024-04-04", "15:32", "cheongmyeong", "before"),
            ("2024-05-05", "09:40", "ipha", "after"),
        ]

        for birth_date, birth_time, term_id, relation in cases:
            with self.subTest(term_id=term_id):
                response, _payload = self._preview(
                    birth_date=birth_date,
                    birth_time=birth_time,
                    region_id="test-zero-correction",
                    region_override=ZERO_CORRECTION_REGION,
                )

                flag = {flag.code: flag for flag in response.debug_trace.uncertainty_flags}["near_solar_term"]
                self.assertEqual(flag.severity, "critical")
                self.assertEqual(flag.affected_fields, ["month_pillar"])
                self.assertEqual(flag.evidence["nearest_solar_term"]["reference"]["term_id"], term_id)
                self.assertEqual(flag.evidence["nearest_solar_term"]["relation"], relation)
                self.assertEqual(flag.evidence["provider"], "solar_term_reference_table")

    def test_regular_date_does_not_emit_near_solar_term(self) -> None:
        response, _payload = self._preview(
            birth_date="2024-02-10",
            birth_time="10:30",
            region_id="test-zero-correction",
            region_override=ZERO_CORRECTION_REGION,
        )

        self.assertNotIn("near_solar_term", _flag_codes(response.debug_trace.uncertainty_flags))


if __name__ == "__main__":
    unittest.main()
