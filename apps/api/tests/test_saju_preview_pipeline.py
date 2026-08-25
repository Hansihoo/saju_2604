import json
import re
import unittest
from collections import OrderedDict
from types import SimpleNamespace
from unittest.mock import patch

from app.api.routes import (
    create_saju_free_detail,
    create_saju_preview,
    prepare_saju_detail_bundle,
    render_saju_detail,
)
from app.domain.saju.pydantic_compat import model_to_dict
from app.domain.saju.schemas import (
    SajuDetailPrepareRequest,
    SajuDetailRenderRequest,
    SajuPreviewRequest,
)
from app.domain.saju.services import generate_detail_insights
from app.domain.saju.services.generate_detail_insights import build_fallback_detail_render
from app.domain.saju.services.generate_free_preview import build_fallback_free_preview_report
from app.domain.saju.services.generate_interpretation import build_fallback_interpretation_report
from app.domain.saju.services.preview_orchestrator import create_saju_preview_response


class SajuPreviewPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._llm_provider_patch = patch(
            "app.domain.saju.services.generate_interpretation.settings.llm_provider",
            "fallback",
        )
        self._llm_provider_patch.start()
        self.addCleanup(self._llm_provider_patch.stop)

    def test_preview_pipeline_includes_real_saju_calculation_stage(self) -> None:
        request = SimpleNamespace(
            state=SimpleNamespace(
                trace_id="test-trace",
                debug_requested=True,
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
            debug=True,
        )

        response = create_saju_preview(payload=payload, request=request)

        self.assertEqual(response.response_mode, "preview")
        self.assertEqual(response.pipeline_status.saju_calculation, "passed")
        self.assertEqual(response.pipeline_status.regional_solar_correction, "passed")
        self.assertEqual(response.result.evidence_sections["elements"].status, "ready")
        self.assertEqual(response.result.evidence_sections["ten_gods"].status, "ready")
        self.assertEqual(response.result.signals.visible_pillar_keys, ["year", "month", "day", "time"])
        self.assertIsNone(response.result.signals.internal_grade)
        self.assertEqual(response.debug_trace.checkpoints[4].stage, "regional_solar_correction")
        self.assertEqual(response.debug_trace.checkpoints[4].status, "passed")
        self.assertEqual(response.debug_trace.checkpoints[5].stage, "saju_calculation")
        self.assertEqual(response.debug_trace.checkpoints[5].status, "passed")
        self.assertEqual(response.debug_trace.checkpoints[6].stage, "analysis_engine")
        self.assertEqual(response.debug_trace.checkpoints[6].status, "passed")
        self.assertEqual(response.debug_trace.checkpoints[7].stage, "llm_formatting")
        self.assertEqual(response.debug_trace.checkpoints[7].status, "skipped")
        self.assertEqual(response.debug_trace.checkpoints[8].stage, "free_preview_formatting")
        self.assertEqual(response.debug_trace.checkpoints[8].status, "failed")
        self.assertEqual(response.debug_trace.failed_stage, "free_preview_formatting")
        self.assertIn("Internal grade", response.debug_trace.checkpoints[6].note)
        self.assertIsNotNone(response.debug_trace.internal_analysis)
        self.assertEqual(response.debug_trace.internal_analysis.internal_grade, "B")
        self.assertIn("\u7532\u8fb0", response.debug_trace.checkpoints[5].note)
        self.assertEqual(response.region.longitude, 126.991824)
        self.assertEqual(response.regional_solar_correction.corrected_solar_datetime, "2024-02-10 09:57:58")
        self.assertIsNotNone(response.debug_trace.birth_time_context)
        self.assertEqual(
            response.debug_trace.birth_time_context.corrected_solar_datetime,
            response.regional_solar_correction.corrected_solar_datetime,
        )
        self.assertEqual(response.debug_trace.birth_time_context.standard_local_datetime, "2024-02-10 10:30:00")
        self.assertEqual(response.debug_trace.birth_time_context.mean_solar_datetime, "2024-02-10 09:57:58")
        json.dumps(model_to_dict(response.debug_trace))

    def test_preview_pipeline_includes_core_manse_data(self) -> None:
        request = SimpleNamespace(
            state=SimpleNamespace(
                trace_id="test-trace-manse",
                debug_requested=True,
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
            debug=True,
        )

        response = create_saju_preview(payload=payload, request=request)

        self.assertEqual(response.manse.meta.day_master, "\u7532")
        self.assertEqual(response.manse.meta.schema_version, "v1")
        self.assertTrue(response.manse.meta.hour_pillar_enabled)
        self.assertIsNone(response.result.signals.balance_score)
        self.assertEqual(response.result.signals.missing_elements, ["metal", "water"])
        self.assertEqual(response.manse.elements.wood, 3)
        self.assertEqual(response.manse.analysis.visible_element_total, 8)
        self.assertEqual(response.manse.analysis.imbalance_gap, 3)
        self.assertIsNone(response.manse.analysis.balance_score)
        self.assertEqual(response.manse.analysis.element_percentages.wood, 37.5)
        self.assertEqual(response.manse.analysis.element_percentages.metal, 0.0)
        self.assertEqual(response.manse.analysis.visible_ten_god_distribution["비견"], 3)
        self.assertEqual(response.manse.analysis.first_luck_cycle_direction, "forward")
        self.assertEqual(response.manse.pillars.time.twelve_fortune, "병")
        self.assertEqual(response.manse.pillars.day.twelve_shinsal, "\ud654\uac1c\uc0b4")
        self.assertEqual(response.manse.table_rows[0].label, "\ucc9c\uac04")
        self.assertEqual(response.manse.table_rows[4].label, "\uc9c0\uc7a5\uac04")
        self.assertEqual(response.manse.table_rows[6].label, "12\uc2e0\uc0b4")
        self.assertEqual(
            response.manse.supplementary_positions.tai_yuan.gan_zhi,
            "\u4e01\u5df3",
        )
        special_star_map = {star.key: star for star in response.manse.special_stars}
        self.assertEqual(len(response.manse.special_stars), 34)
        self.assertFalse(special_star_map["cheoneul-gwiin"].active)
        self.assertEqual(special_star_map["woldeok-gwiin"].tier, "S")
        self.assertEqual(special_star_map["cheonmun-seong"].tier, "B")
        self.assertEqual(special_star_map["cheonmun-seong"].scope, "optional")
        self.assertEqual(special_star_map["wangji-dohwa"].tier, "B")
        self.assertEqual(special_star_map["mokyok-dohwa"].tier, "A")
        self.assertEqual(
            special_star_map["gwimungwan"].method_id,
            "day-branch-pair-common-kr",
        )
        self.assertTrue(special_star_map["yeokma-year-branch"].active)
        self.assertEqual(
            [match.pillar_key for match in special_star_map["yeokma-year-branch"].matches],
            ["month"],
        )
        self.assertTrue(special_star_map["gongmang"].active)
        self.assertEqual(len(response.manse.luck_cycles), 10)
        self.assertTrue(all(cycle.gan_zhi for cycle in response.manse.luck_cycles))
        self.assertEqual(response.manse.luck_cycles[0].gan_zhi, "\u4e01\u536f")
        self.assertEqual(response.manse.luck_cycles[0].start_age, 8)
        self.assertEqual(response.manse.luck_cycles[0].start_age_years, 7)
        self.assertEqual(response.manse.luck_cycles[0].start_age_months, 10)
        self.assertEqual(response.manse.luck_cycles[0].start_age_total_months, 94)
        self.assertRegex(
            response.manse.luck_cycles[0].start_datetime or "",
            r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$",
        )
        self.assertRegex(
            response.manse.luck_cycles[0].change_datetime or "",
            r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$",
        )
        self.assertEqual(response.pipeline_status.llm_formatting, "skipped")
        self.assertEqual(response.pipeline_status.free_preview_formatting, "fallback")
        self.assertIsNone(response.result.interpretation)
        self.assertIsNotNone(response.result.free_preview)
        self.assertEqual(response.result.free_preview.schema_version, "free-preview-v1")
        self.assertEqual(response.result.free_preview.provider, "fallback")
        self.assertEqual(response.result.free_preview.prompt_version, "saju-free-preview-v3")
        self.assertEqual(len(response.result.free_preview.core_diagnoses), 3)
        self.assertEqual(len(response.result.free_preview.cards), 4)
        self.assertIn("free_preview", model_to_dict(response)["result"])
        self.assertTrue(response.result.overview)

    def test_late_zi_uses_local_civil_time_for_iljin_query_and_hour_pillar(self) -> None:
        request = SimpleNamespace(
            state=SimpleNamespace(
                trace_id="test-trace-late-zi",
                debug_requested=True,
            )
        )
        payload = SajuPreviewRequest(
            calendar_type="solar",
            birth_date="1988-11-20",
            birth_time="23:30",
            is_birth_time_estimated=False,
            is_lunar_leap_month=False,
            gender="male",
            region_id="kr-seoul-special",
            debug=True,
        )

        response = create_saju_preview(payload=payload, request=request)

        self.assertEqual(
            response.regional_solar_correction.corrected_solar_datetime,
            "1988-11-20 22:57:58",
        )
        self.assertEqual(response.manse.pillars.year.gan_zhi, "\u620a\u8fb0")
        self.assertEqual(response.manse.pillars.month.gan_zhi, "\u7678\u4ea5")
        self.assertEqual(response.manse.pillars.day.gan_zhi, "\u5e9a\u8fb0")
        self.assertEqual(response.manse.pillars.time.gan_zhi, "\u4e19\u5b50")
        self.assertEqual(response.manse.meta.day_time_basis_datetime, "1988-11-20 23:30:00")
        self.assertEqual(response.manse.meta.day_pillar_basis_date, "1988-11-21")
        self.assertEqual(response.manse.meta.iljin_query_date, "1988-11-21")
        self.assertEqual(response.manse.meta.day_pillar_rule, "sect1_23_changes_day")
        self.assertEqual(
            response.result.calculation_basis.primary_day_pillar_basis_datetime,
            "1988-11-20 23:30:00",
        )

    def test_estimated_birth_time_hides_hour_pillar_outputs(self) -> None:
        request = SimpleNamespace(
            state=SimpleNamespace(
                trace_id="test-trace-estimated",
                debug_requested=True,
            )
        )
        payload = SajuPreviewRequest(
            calendar_type="solar",
            birth_date="2024-02-10",
            birth_time="13:45",
            is_birth_time_estimated=True,
            is_lunar_leap_month=False,
            gender="male",
            region_id="kr-seoul",
            debug=True,
        )

        response = create_saju_preview(payload=payload, request=request)

        self.assertFalse(response.result.hour_pillar_enabled)
        self.assertIn("time_pillar", response.result.disabled_sections)
        self.assertEqual(response.result.evidence_sections["luck_cycles"].status, "disabled")
        self.assertEqual(response.pipeline_status.analysis_engine, "passed")
        self.assertIn("hidden by policy", response.debug_trace.checkpoints[5].note)
        self.assertFalse(response.manse.meta.hour_pillar_enabled)
        self.assertFalse(response.manse.pillars.time.enabled)
        self.assertEqual(response.calendar_normalization.input_time, "00:00")
        self.assertTrue(response.time_correction.source_local_datetime.endswith("00:00:00"))
        self.assertEqual(response.manse.analysis.visible_element_total, 6)
        self.assertIsNone(response.manse.analysis.first_luck_cycle_direction)
        self.assertEqual(response.manse.table_rows[0].time, "")
        self.assertEqual(response.manse.table_rows[6].time, "")
        self.assertEqual(response.manse.luck_cycles, [])
        self.assertEqual(
            response.manse.notes,
            ["\ucd9c\uc0dd\uc2dc\uac04 \ubbf8\uc0c1\uc73c\ub85c \uc2dc\uc8fc\uc640 \uc2dc\uc8fc \uae30\ubc18 \ub300\uc6b4 \uc815\ubcf4\ub294 \ube44\ud65c\uc131\ud654\ub418\uc5c8\uc2b5\ub2c8\ub2e4."],
        )
        self.assertIsNone(response.result.interpretation)

    def test_preview_pipeline_respects_requested_output_language(self) -> None:
        request = SimpleNamespace(
            state=SimpleNamespace(
                trace_id="test-trace-language",
                debug_requested=False,
            )
        )
        payload = SajuPreviewRequest(
            locale="en",
            calendar_type="solar",
            birth_date="1996-06-19",
            birth_time="15:03",
            is_birth_time_estimated=False,
            is_lunar_leap_month=False,
            gender="female",
            region_id="kr-seoul-special",
            debug=False,
        )

        response = create_saju_preview(payload=payload, request=request)

        self.assertIsNone(response.result.interpretation)
        self.assertIsNotNone(response.result.free_preview)
        self.assertEqual(response.result.free_preview.provider, "fallback")
        self.assertEqual(response.result.free_preview.headline, "A steady builder of clear standards")
        self.assertIn("Love", response.result.free_preview.cards[2].title)

    def test_preview_pipeline_uses_explicit_luck_cycle_formula(self) -> None:
        request = SimpleNamespace(
            state=SimpleNamespace(
                trace_id="test-trace-luck-cycles",
                debug_requested=True,
            )
        )
        payload = SajuPreviewRequest(
            calendar_type="solar",
            birth_date="1996-06-19",
            birth_time="15:03",
            is_birth_time_estimated=False,
            is_lunar_leap_month=False,
            gender="female",
            region_id="kr-seoul-special",
            debug=True,
        )

        response = create_saju_preview(payload=payload, request=request)

        self.assertEqual(response.pipeline_status.saju_calculation, "passed")
        self.assertEqual(response.manse.luck_cycles[0].start_age, 5)
        self.assertEqual(response.manse.luck_cycles[0].start_age_years, 4)
        self.assertEqual(response.manse.luck_cycles[0].start_age_months, 6)
        self.assertEqual(response.manse.analysis.first_luck_cycle_start_age_years, 4)
        self.assertEqual(response.manse.analysis.first_luck_cycle_start_age_months, 6)
        self.assertEqual(response.manse.analysis.first_luck_cycle_start_age_total_months, 54)
        self.assertEqual(response.manse.luck_cycles[0].gan_zhi, "\u7678\u5df3")
        self.assertEqual(response.manse.luck_cycles[1].start_age, 15)
        self.assertEqual(response.manse.luck_cycles[1].gan_zhi, "\u58ec\u8fb0")
        self.assertRegex(
            response.manse.luck_cycles[0].start_datetime or "",
            r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$",
        )
        self.assertRegex(
            response.manse.luck_cycles[0].change_datetime or "",
            r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$",
        )
        self.assertIn("\u7678\u5df3", response.result.evidence_sections["luck_cycles"].summary)

    def test_preview_response_survives_free_preview_generation_failure(self) -> None:
        request = SimpleNamespace(
            state=SimpleNamespace(
                trace_id="test-trace-free-preview-failure",
                debug_requested=True,
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
            debug=True,
        )

        with patch(
            "app.domain.saju.services.build_preview_response.generate_free_preview_report",
            side_effect=RuntimeError("free preview unavailable"),
        ):
            response = create_saju_preview(payload=payload, request=request)

        self.assertEqual(response.response_mode, "preview")
        self.assertEqual(response.pipeline_status.saju_calculation, "passed")
        self.assertEqual(response.pipeline_status.free_preview_formatting, "fallback")
        self.assertIsNone(response.result.interpretation)
        self.assertIsNotNone(response.result.free_preview)
        self.assertEqual(response.result.free_preview.provider, "fallback")
        self.assertEqual(response.manse.meta.day_master, "\u7532")

    def test_preview_pipeline_marks_successful_codex_reports_as_passed(self) -> None:
        request = SimpleNamespace(
            state=SimpleNamespace(
                trace_id="test-trace-preview-codex",
                debug_requested=True,
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
            debug=True,
        )

        def build_codex_free_preview(*, payload, **_):
            report = build_fallback_free_preview_report(payload)
            report.provider = "codex"
            report.model = "codex-cli"
            return report

        def build_codex_interpretation(*, payload, **_):
            report = build_fallback_interpretation_report(payload)
            report.provider = "codex"
            report.model = "codex-cli"
            return report

        with patch(
            "app.domain.saju.services.build_preview_response.generate_free_preview_report",
            side_effect=build_codex_free_preview,
        ), patch(
            "app.domain.saju.services.build_preview_response.generate_interpretation_report",
            side_effect=build_codex_interpretation,
        ):
            response = create_saju_preview_response(
                payload=payload,
                trace_id=request.state.trace_id,
                debug_requested=request.state.debug_requested,
                service_name="test",
                report_mode="all",
            )

        self.assertEqual(response.pipeline_status.llm_formatting, "passed")
        self.assertEqual(response.pipeline_status.free_preview_formatting, "success")
        self.assertEqual(response.result.interpretation.provider, "codex")
        self.assertEqual(response.result.free_preview.provider, "codex")
        self.assertIsNotNone(response.debug_trace)
        self.assertEqual(response.debug_trace.checkpoints[7].status, "passed")
        self.assertEqual(response.debug_trace.checkpoints[8].status, "passed")
        self.assertIsNone(response.debug_trace.failed_stage)

    def test_preview_and_free_detail_generate_only_the_requested_report(self) -> None:
        request = SimpleNamespace(
            state=SimpleNamespace(
                trace_id="test-trace-report-separation",
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

        with patch(
            "app.domain.saju.services.build_preview_response.generate_free_preview_report",
            side_effect=lambda *, payload, **_: build_fallback_free_preview_report(payload),
        ) as free_preview_mock, patch(
            "app.domain.saju.services.build_preview_response.generate_interpretation_report",
            side_effect=AssertionError("Preview must not generate the full interpretation"),
        ) as interpretation_mock:
            preview_response = create_saju_preview(payload=payload, request=request)

        free_preview_mock.assert_called_once()
        interpretation_mock.assert_not_called()
        self.assertIsNotNone(preview_response.result.free_preview)
        self.assertIsNone(preview_response.result.interpretation)
        self.assertEqual(preview_response.pipeline_status.llm_formatting, "skipped")
        public_response = model_to_dict(preview_response, exclude_none=True)
        serialized_public_response = json.dumps(public_response, ensure_ascii=False)
        for internal_field in (
            "balance_score",
            "charm_score",
            "wealth_score",
            "career_score",
            "leadership_score",
            "internal_grade",
        ):
            self.assertNotIn(internal_field, serialized_public_response)

        with patch(
            "app.domain.saju.services.build_preview_response.generate_free_preview_report",
            side_effect=AssertionError("Detail must not regenerate the free preview"),
        ) as free_preview_mock, patch(
            "app.domain.saju.services.build_preview_response.generate_interpretation_report",
            side_effect=lambda *, payload, **_: build_fallback_interpretation_report(payload),
        ) as interpretation_mock:
            detail_response = create_saju_free_detail(payload=payload, request=request)

        free_preview_mock.assert_not_called()
        interpretation_mock.assert_called_once()
        self.assertEqual(detail_response.interpretation.provider, "fallback")
        self.assertEqual(detail_response.pipeline_status.free_preview_formatting, "skipped")

    def test_free_detail_endpoint_returns_existing_interpretation_schema(self) -> None:
        request = SimpleNamespace(
            state=SimpleNamespace(
                trace_id="test-trace-free-detail",
                debug_requested=False,
            )
        )
        payload = SajuPreviewRequest(
            locale="ko",
            calendar_type="solar",
            birth_date="1996-06-19",
            birth_time="15:03",
            is_birth_time_estimated=False,
            is_lunar_leap_month=False,
            gender="female",
            region_id="kr-seoul-special",
            debug=False,
        )

        response = create_saju_free_detail(payload=payload, request=request)

        self.assertEqual(response.response_mode, "free_detail")
        self.assertEqual(response.pipeline_status.saju_calculation, "passed")
        self.assertEqual(response.detail_report, response.interpretation)
        self.assertEqual(response.interpretation.schema_version, "m2-llm-v5")
        self.assertEqual(response.interpretation.prompt_version, "saju-report-v15")
        self.assertEqual(response.interpretation.provider, "fallback")
        self.assertEqual(response.interpretation.core_analysis.title, "내 사주 특징")
        self.assertEqual(response.interpretation.luck_flow.title, "현재 운과 대운 흐름")

    def test_detail_prepare_and_render_endpoints_use_cached_detail_bundle(self) -> None:
        request = SimpleNamespace(
            state=SimpleNamespace(
                trace_id="test-trace-detail-insight",
                debug_requested=False,
            )
        )
        payload = SajuPreviewRequest(
            locale="ko",
            calendar_type="solar",
            birth_date="1996-06-19",
            birth_time="15:03",
            is_birth_time_estimated=False,
            is_lunar_leap_month=False,
            gender="female",
            region_id="kr-seoul-special",
            debug=False,
        )

        with patch(
            "app.domain.saju.services.generate_detail_insights.settings.llm_provider",
            "fallback",
        ):
            prepared = prepare_saju_detail_bundle(
                report_id="test-report",
                payload=SajuDetailPrepareRequest(input=payload, detail_type="love_timing"),
                request=request,
            )
            prepared_again = prepare_saju_detail_bundle(
                report_id="test-report",
                payload=SajuDetailPrepareRequest(input=payload, detail_type="wealth_timing"),
                request=request,
            )
            rendered = render_saju_detail(
                report_id="test-report",
                payload=SajuDetailRenderRequest(
                    detail_type="love_timing",
                    input_hash=prepared.input_hash,
                    locale="ko",
                ),
                request=request,
            )
            rendered_again = render_saju_detail(
                report_id="test-report",
                payload=SajuDetailRenderRequest(
                    detail_type="love_timing",
                    input_hash=prepared.input_hash,
                    locale="ko",
                ),
                request=request,
            )

        self.assertEqual(prepared.response_mode, "detail_prepare")
        self.assertFalse(prepared.cached)
        self.assertTrue(prepared_again.cached)
        self.assertEqual(prepared.input_hash, prepared_again.input_hash)
        self.assertIn("love_timing", prepared.available_detail_types)
        self.assertEqual(prepared.bundle.schema_version, "saju-detail-v1")
        self.assertIn("love_timing", prepared.bundle.detail_analysis_bundle)
        self.assertEqual(rendered.response_mode, "detail_render")
        self.assertEqual(rendered.detail_type, "love_timing")
        self.assertFalse(rendered.cached)
        self.assertTrue(rendered_again.cached)
        self.assertEqual(rendered.provider, rendered_again.provider)
        self.assertEqual(rendered.report.schema_version, "saju-detail-render-v1")
        combined = json.dumps(model_to_dict(rendered.report), ensure_ascii=False)
        for forbidden in ("무료", "유료", "프리미엄", "결제", "score", "internal_grade", "evidence_id"):
            self.assertNotIn(forbidden, combined)
        self.assertIsNone(re.search(r"[\u3400-\u9fff]", combined))

    def test_detail_cache_is_bounded_and_can_be_disabled(self) -> None:
        cache = OrderedDict()
        with patch.object(generate_detail_insights.settings, "detail_cache_ttl_seconds", 900), patch.object(
            generate_detail_insights.settings,
            "detail_cache_max_entries",
            1,
        ):
            generate_detail_insights._set_detail_cache_item(cache, ("first",), "first-value")
            generate_detail_insights._set_detail_cache_item(cache, ("second",), "second-value")

            self.assertIsNone(generate_detail_insights._get_detail_cache_item(cache, ("first",)))
            self.assertEqual(
                generate_detail_insights._get_detail_cache_item(cache, ("second",)),
                "second-value",
            )

        disabled_cache = OrderedDict()
        with patch.object(generate_detail_insights.settings, "detail_cache_ttl_seconds", 0):
            generate_detail_insights._set_detail_cache_item(disabled_cache, ("disabled",), "value")

        self.assertEqual(disabled_cache, OrderedDict())

    def test_detail_render_codex_provider_uses_codex_path(self) -> None:
        request = SimpleNamespace(
            state=SimpleNamespace(
                trace_id="test-trace-detail-codex",
                debug_requested=False,
            )
        )
        payload = SajuPreviewRequest(
            locale="ko",
            calendar_type="solar",
            birth_date="1996-06-19",
            birth_time="15:03",
            is_birth_time_estimated=False,
            is_lunar_leap_month=False,
            gender="female",
            region_id="kr-seoul-special",
            debug=False,
        )
        codex_report = build_fallback_detail_render(
            "love_timing",
            {"available": True, "best_periods": []},
            locale="ko",
        )

        with patch(
            "app.domain.saju.services.generate_detail_insights.settings.llm_provider",
            "codex",
        ), patch(
            "app.domain.saju.services.generate_detail_insights._call_openai_detail_render",
            side_effect=AssertionError("OpenAI detail path must not be called in Codex mode"),
        ), patch(
            "app.domain.saju.services.generate_detail_insights._call_codex_detail_render",
            return_value=codex_report,
        ):
            rendered = render_saju_detail(
                report_id="test-report-codex-detail",
                payload=SajuDetailRenderRequest(
                    detail_type="love_timing",
                    input=payload,
                    locale="ko",
                ),
                request=request,
            )

        self.assertEqual(rendered.provider, "codex")
        self.assertEqual(rendered.model, "codex-cli")
        self.assertEqual(rendered.report.detail_type, "love_timing")

    def test_compatibility_detail_requires_partner_flow(self) -> None:
        request = SimpleNamespace(
            state=SimpleNamespace(
                trace_id="test-trace-compatibility-detail",
                debug_requested=False,
            )
        )
        payload = SajuPreviewRequest(
            locale="ko",
            calendar_type="solar",
            birth_date="1996-06-19",
            birth_time="15:03",
            is_birth_time_estimated=False,
            is_lunar_leap_month=False,
            gender="female",
            region_id="kr-seoul-special",
            debug=False,
        )

        with patch(
            "app.domain.saju.services.generate_detail_insights.settings.llm_provider",
            "fallback",
        ):
            rendered = render_saju_detail(
                report_id="test-report-compat",
                payload=SajuDetailRenderRequest(
                    detail_type="compatibility_compare",
                    input=payload,
                    locale="ko",
                ),
                request=request,
            )

        self.assertEqual(rendered.detail_type, "compatibility_compare")
        self.assertIn("상대 정보", rendered.report.summary)
        self.assertFalse(rendered.report.body.periods)
        self.assertIn("상대 정보 없이 실제 궁합 결과를 만들지 않습니다.", rendered.report.body.cautions)


if __name__ == "__main__":
    unittest.main()
