import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.api.routes import create_saju_preview
from app.domain.saju.schemas import SajuPreviewRequest
from app.domain.saju.services.calculate_saju import calculate_saju
from app.domain.saju.services.canonical_year_month import (
    calculate_canonical_year_month,
    month_ganzhi_for_year_stem,
)
from app.domain.saju.services.solar_term_boundaries import find_jie_boundary_by_term


GAN = {
    "gap": "\u7532",
    "eul": "\u4e59",
    "byeong": "\u4e19",
    "jeong": "\u4e01",
    "mu": "\u620a",
    "gi": "\u5df1",
    "gyeong": "\u5e9a",
    "sin": "\u8f9b",
    "im": "\u58ec",
    "gye": "\u7678",
}
JI = {
    "ja": "\u5b50",
    "chuk": "\u4e11",
    "in": "\u5bc5",
    "myo": "\u536f",
    "jin": "\u8fb0",
}


def _context_for(datetime_text: str):
    return calculate_canonical_year_month(
        basis_datetime_text=datetime_text,
        timezone_id="Asia/Seoul",
        day_stem=GAN["gap"],
        legacy_year_pillar="legacy-year",
        legacy_month_pillar="legacy-month",
        apply_to_primary=False,
    ).context


class CanonicalYearMonthTests(unittest.TestCase):
    def setUp(self) -> None:
        self._llm_provider_patch = patch(
            "app.domain.saju.services.generate_interpretation.settings.llm_provider",
            "fallback",
        )
        self._llm_provider_patch.start()
        self.addCleanup(self._llm_provider_patch.stop)

    def test_year_pillar_uses_ipchun_boundary_inclusively(self) -> None:
        before = _context_for("2024-02-04 17:26:00")
        exact = _context_for("2024-02-04 17:27:00")
        after = _context_for("2024-02-04 17:28:00")

        self.assertEqual(before["canonical_year_pillar"], f"{GAN['gye']}{JI['myo']}")
        self.assertEqual(exact["canonical_year_pillar"], f"{GAN['gap']}{JI['jin']}")
        self.assertEqual(after["canonical_year_pillar"], f"{GAN['gap']}{JI['jin']}")
        self.assertTrue(exact["exact_boundary_applied"])

    def test_month_pillar_uses_jie_boundary_inclusively(self) -> None:
        gyeongchip_before = _context_for("2024-03-05 11:22:00")
        gyeongchip_exact = _context_for("2024-03-05 11:23:00")
        gyeongchip_after = _context_for("2024-03-05 11:24:00")
        cheongmyeong_before = _context_for("2024-04-04 16:01:00")
        cheongmyeong_exact = _context_for("2024-04-04 16:02:00")

        self.assertEqual(gyeongchip_before["month_boundary_term"], "ipchun")
        self.assertTrue(gyeongchip_before["canonical_month_pillar"].endswith(JI["in"]))
        self.assertEqual(gyeongchip_exact["month_boundary_term"], "gyeongchip")
        self.assertTrue(gyeongchip_exact["canonical_month_pillar"].endswith(JI["myo"]))
        self.assertEqual(gyeongchip_after["month_boundary_term"], "gyeongchip")
        self.assertTrue(gyeongchip_after["canonical_month_pillar"].endswith(JI["myo"]))
        self.assertEqual(cheongmyeong_before["month_boundary_term"], "gyeongchip")
        self.assertTrue(cheongmyeong_before["canonical_month_pillar"].endswith(JI["myo"]))
        self.assertEqual(cheongmyeong_exact["month_boundary_term"], "cheongmyeong")
        self.assertTrue(cheongmyeong_exact["canonical_month_pillar"].endswith(JI["jin"]))

    def test_winter_month_boundaries_cover_sohan_and_daeseol(self) -> None:
        sohan = _context_for("2024-01-06 05:49:00")
        daeseol_boundary = find_jie_boundary_by_term(2024, "daeseol")
        self.assertIsNotNone(daeseol_boundary)
        daeseol = _context_for(daeseol_boundary.datetime_text)

        self.assertEqual(sohan["month_boundary_term"], "sohan")
        self.assertTrue(sohan["canonical_month_pillar"].endswith(JI["chuk"]))
        self.assertEqual(daeseol["month_boundary_term"], "daeseol")
        self.assertTrue(daeseol["canonical_month_pillar"].endswith(JI["ja"]))

    def test_month_stem_formula_for_yin_month(self) -> None:
        cases = [
            (GAN["gap"], f"{GAN['byeong']}{JI['in']}"),
            (GAN["gi"], f"{GAN['byeong']}{JI['in']}"),
            (GAN["eul"], f"{GAN['mu']}{JI['in']}"),
            (GAN["gyeong"], f"{GAN['mu']}{JI['in']}"),
            (GAN["byeong"], f"{GAN['gyeong']}{JI['in']}"),
            (GAN["sin"], f"{GAN['gyeong']}{JI['in']}"),
            (GAN["jeong"], f"{GAN['im']}{JI['in']}"),
            (GAN["im"], f"{GAN['im']}{JI['in']}"),
            (GAN["mu"], f"{GAN['gap']}{JI['in']}"),
            (GAN["gye"], f"{GAN['gap']}{JI['in']}"),
        ]
        for year_stem, expected in cases:
            with self.subTest(year_stem=year_stem):
                self.assertEqual(month_ganzhi_for_year_stem(year_stem, "ipchun"), expected)

    def test_feature_flag_false_keeps_primary_pillars_legacy(self) -> None:
        result = calculate_saju(
            corrected_solar_datetime="2024-02-04 17:27:00",
            gender="male",
            tzid="Asia/Seoul",
            use_canonical_year_month_pillars=False,
        )

        self.assertFalse(result.year_month_boundary_context["applied_to_primary"])
        self.assertEqual(
            result.year_month_boundary_context["legacy_year_pillar"],
            result.pillars["year"].gan_zhi,
        )
        self.assertEqual(
            result.year_month_boundary_context["legacy_month_pillar"],
            result.pillars["month"].gan_zhi,
        )

    def test_feature_flag_true_switches_only_year_month_sources(self) -> None:
        legacy = calculate_saju(
            corrected_solar_datetime="2024-02-04 17:27:00",
            gender="male",
            tzid="Asia/Seoul",
            use_canonical_year_month_pillars=False,
        )
        canonical = calculate_saju(
            corrected_solar_datetime="2024-02-04 17:27:00",
            gender="male",
            tzid="Asia/Seoul",
            use_canonical_year_month_pillars=True,
        )

        self.assertTrue(canonical.year_month_boundary_context["applied_to_primary"])
        self.assertEqual(
            canonical.year_month_boundary_context["canonical_year_pillar"],
            canonical.pillars["year"].gan_zhi,
        )
        self.assertEqual(
            canonical.year_month_boundary_context["canonical_month_pillar"],
            canonical.pillars["month"].gan_zhi,
        )
        self.assertEqual(legacy.pillars["day"].gan_zhi, canonical.pillars["day"].gan_zhi)
        self.assertEqual(legacy.pillars["time"].gan_zhi, canonical.pillars["time"].gan_zhi)

    def test_preview_debug_exposes_shadow_context_without_primary_switch(self) -> None:
        request = SimpleNamespace(
            state=SimpleNamespace(
                trace_id="canonical-year-month-shadow",
                debug_requested=True,
            )
        )
        payload = SajuPreviewRequest(
            calendar_type="solar",
            birth_date="2024-02-04",
            birth_time="17:27",
            is_birth_time_estimated=False,
            is_lunar_leap_month=False,
            gender="male",
            region_id="kr-seoul",
            debug=True,
        )

        with patch(
            "app.domain.saju.services.preview_orchestrator.settings.use_canonical_year_month_pillars",
            False,
        ):
            response = create_saju_preview(payload=payload, request=request)

        context = response.debug_trace.year_month_boundary_context
        self.assertTrue(context["available"])
        self.assertFalse(context["applied_to_primary"])
        self.assertEqual(context["year_pillar_source"], "LUNAR_PYTHON_LEGACY")
        self.assertIn("canonical_year_pillar", context)
        self.assertEqual(response.result.calculation_basis.accuracy_mode, "legacy")


if __name__ == "__main__":
    unittest.main()
