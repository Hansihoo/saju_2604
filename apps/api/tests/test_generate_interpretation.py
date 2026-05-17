import re
import unittest
from unittest.mock import patch

from app.domain.saju.interpretation import (
    InterpretationDiagnostics,
    InterpretationNarrativeSection,
    InterpretationReport,
    InterpretationSummaryBlock,
)
from app.domain.saju.llm_payload import (
    InterpretationCareerFacts,
    InterpretationCountMetric,
    InterpretationCurrentFlowContext,
    InterpretationEvidenceItem,
    InterpretationInputProfile,
    InterpretationLoveFacts,
    InterpretationLuckCycle,
    InterpretationPayload,
    InterpretationSignalBlock,
    InterpretationSpecialStar,
    InterpretationSupplementaryPosition,
    InterpretationTimeContext,
    InterpretationVisiblePillar,
    InterpretationWealthFacts,
)
from app.domain.saju.prompts.interpretation_report import get_interpretation_report_prompt
from app.domain.saju.services.generate_interpretation import (
    MIN_SECTION_LENGTH,
    MIN_SUMMARY_LENGTH,
    _validate_report,
    build_fallback_interpretation_report,
    generate_interpretation_report,
)


def make_body() -> str:
    return """
현재 구조는 강점과 약점의 대비가 비교적 선명하게 보이는 편입니다. 그래서 환경이 맞으면 강점이 빨리 살아나고, 맞지 않으면 피로도 함께 커질 가능성이 있습니다.

### 1. 핵심 구조
- 현재 보이는 신호를 먼저 정리하는 편이 좋습니다.
- 강한 기운은 장점이 되지만, 약한 기운을 늦게 보완하면 기복이 생길 수 있습니다.
- 그래서 방향을 단순하게 잡는 태도가 중요합니다.

### 2. 관리 포인트
- 장점만 밀기보다 약한 부분을 함께 보완하는 편이 좋습니다.
- 사람, 일, 돈의 기준을 분리해서 보면 흔들림을 줄일 수 있습니다.
- 현재 흐름을 같이 읽으면 실전 판단이 더 쉬워집니다.
""".strip()


def make_payload(locale: str = "ko", estimated: bool = False) -> InterpretationPayload:
    return InterpretationPayload(
        output_sections=["core_analysis", "love", "career", "wealth", "luck_flow"],
        profile=InterpretationInputProfile(
            locale=locale,
            calendar_type="solar",
            birth_date="1996-06-19",
            birth_time="00:00" if estimated else "15:03",
            is_birth_time_estimated=estimated,
            is_lunar_leap_month=False,
            gender="female",
            region_id="kr-seoul-special",
            region_display_name="서울특별시" if locale == "ko" else "Seoul, South Korea",
            tzid="Asia/Seoul",
        ),
        time_context=InterpretationTimeContext(
            normalized_local_datetime="1996-06-19 15:03:00",
            normalized_utc_datetime="1996-06-19 06:03:00",
            corrected_solar_datetime="1996-06-19 14:31:00",
            regional_time_offset_minutes=-32.02,
            daylight_saving_offset_minutes=0,
            correction_basis="local_mean_time",
        ),
        visible_pillars=[
            InterpretationVisiblePillar(
                key="year",
                label="연주",
                gan_zhi="丙子",
                stem="丙",
                branch="子",
                display_label="연주" if locale == "ko" else "Year pillar",
                display_gan_zhi="병자" if locale == "ko" else "Byeong-Ja",
                display_stem="병" if locale == "ko" else "Byeong",
                display_branch="자" if locale == "ko" else "Ja",
            ),
            InterpretationVisiblePillar(
                key="month",
                label="월주",
                gan_zhi="甲午",
                stem="甲",
                branch="午",
                display_label="월주" if locale == "ko" else "Month pillar",
                display_gan_zhi="갑오" if locale == "ko" else "Gap-O",
                display_stem="갑" if locale == "ko" else "Gap",
                display_branch="오" if locale == "ko" else "O",
            ),
            InterpretationVisiblePillar(
                key="day",
                label="일주",
                gan_zhi="丁酉",
                stem="丁",
                branch="酉",
                display_label="일주" if locale == "ko" else "Day pillar",
                display_gan_zhi="정유" if locale == "ko" else "Jeong-Yu",
                display_stem="정" if locale == "ko" else "Jeong",
                display_branch="유" if locale == "ko" else "Yu",
            ),
        ],
        day_master="정" if locale == "ko" else "Jeong",
        element_counts={"wood": 1, "fire": 3, "earth": 1, "metal": 2, "water": 1},
        ten_god_stems={"year": "겁재", "month": "정관", "day": "", "time": ""},
        signals=InterpretationSignalBlock(
            internal_grade="B",
            balance_score=57,
            charm_score=67,
            wealth_score=54,
            career_score=71,
            leadership_score=48,
            dominant_elements=["fire", "metal"],
            missing_elements=["earth"],
        ),
        evidence=[
            InterpretationEvidenceItem(key="elements", title="Five Elements", status="ready", summary="elements"),
            InterpretationEvidenceItem(key="ten_gods", title="Ten Gods", status="ready", summary="ten gods"),
            InterpretationEvidenceItem(key="luck_cycles", title="Luck Cycles", status="ready", summary="luck cycles"),
        ],
        luck_cycles=[
            InterpretationLuckCycle(
                start_age=5,
                end_age=14,
                start_year=2000,
                end_year=2009,
                gan_zhi="癸巳",
                display_gan_zhi="계사" if locale == "ko" else "Gye-Sa",
            ),
            InterpretationLuckCycle(
                start_age=25,
                end_age=34,
                start_year=2020,
                end_year=2029,
                gan_zhi="辛卯",
                display_gan_zhi="신묘" if locale == "ko" else "Sin-Myo",
            ),
            InterpretationLuckCycle(
                start_age=35,
                end_age=44,
                start_year=2030,
                end_year=2039,
                gan_zhi="庚寅",
                display_gan_zhi="경인" if locale == "ko" else "Gyeong-In",
            ),
        ],
        current_flow=InterpretationCurrentFlowContext(
            current_year=2026,
            current_age=29,
            active_luck_cycle=InterpretationLuckCycle(
                start_age=25,
                end_age=34,
                start_year=2020,
                end_year=2029,
                gan_zhi="辛卯",
                display_gan_zhi="신묘" if locale == "ko" else "Sin-Myo",
            ),
            next_luck_cycle=InterpretationLuckCycle(
                start_age=35,
                end_age=44,
                start_year=2030,
                end_year=2039,
                gan_zhi="庚寅",
                display_gan_zhi="경인" if locale == "ko" else "Gyeong-In",
            ),
        ),
        love_facts=InterpretationLoveFacts(
            score=67,
            spouse_house_label="배우자궁" if locale == "ko" else "Spouse house",
            spouse_house_branch="유" if locale == "ko" else "Yu",
            spouse_house_ten_god="편재" if locale == "ko" else "Indirect Wealth",
            partner_star_label="관성" if locale == "ko" else "Officer star",
            partner_star_count=2,
            active_star_labels=["도화", "홍염"] if locale == "ko" else ["Peach Blossom", "Red Charm"],
        ),
        career_facts=InterpretationCareerFacts(
            score=71,
            month_pillar_label="월주" if locale == "ko" else "Month pillar",
            month_pillar_gan_zhi="갑오" if locale == "ko" else "Gap-O",
            month_stem_ten_god="정관" if locale == "ko" else "Direct Officer",
            key_ten_gods=[
                InterpretationCountMetric(key="officer", label="관성" if locale == "ko" else "Officer stars", count=2),
                InterpretationCountMetric(key="resource", label="인성" if locale == "ko" else "Resource stars", count=1),
                InterpretationCountMetric(key="output", label="식상" if locale == "ko" else "Output stars", count=2),
            ],
            active_star_labels=["문창귀인", "학당"] if locale == "ko" else ["Literary Star", "Study Hall"],
        ),
        wealth_facts=InterpretationWealthFacts(
            score=54,
            key_ten_gods=[
                InterpretationCountMetric(key="wealth", label="재성" if locale == "ko" else "Wealth stars", count=1),
                InterpretationCountMetric(key="output", label="식상" if locale == "ko" else "Output stars", count=2),
                InterpretationCountMetric(key="peer", label="비겁" if locale == "ko" else "Peer stars", count=1),
            ],
            active_star_labels=["월덕귀인"] if locale == "ko" else ["Monthly Virtue"],
            missing_elements=["earth"] if locale == "ko" else ["earth"],
        ),
        supplementary_positions=[
            InterpretationSupplementaryPosition(
                key="tai_yuan",
                label="태원",
                gan_zhi="丙申",
                display_label="태원" if locale == "ko" else "Tai Yuan",
                display_gan_zhi="병신" if locale == "ko" else "Byeong-Sin",
            )
        ],
        special_stars=[
            InterpretationSpecialStar(
                key="dohwa-day-branch",
                label="도화",
                tier="S",
                category="sinsal",
                usage_summary="relationship signal",
                matched_pillars=["day"],
                evidence_id="star:dohwa-day-branch",
                display_label="도화" if locale == "ko" else "Peach Blossom",
            )
        ],
        limitations=["출생시간 미상으로 시주 기반 해석을 제한합니다."] if estimated and locale == "ko" else (
            ["Hour-pillar-based interpretation is limited because the birth time is estimated."] if estimated else []
        ),
        disabled_sections=["time_pillar"] if estimated else [],
        notes=[],
        narrative_rules=[],
        prompt_seed=None,
    )


def make_report(confidence: str = "medium") -> InterpretationReport:
    body = make_body()
    return InterpretationReport(
        provider="openai",
        model="gpt-5.4",
        prompt_version="saju-report-v14",
        summary=InterpretationSummaryBlock(
            headline="현재 흐름을 함께 보는 사주",
            overview="현재 기준 흐름과 원국 구조를 함께 반영해 장점과 주의점을 읽는 해석입니다. 연애, 직장, 금전 모두 현재 대운과 다음 대운의 연결을 같이 보도록 구성했습니다.",
            confidence=confidence,
            evidence_ids=["elements"],
        ),
        core_analysis=InterpretationNarrativeSection(title="내 사주의 특징", body=body, evidence_ids=["elements"]),
        love=InterpretationNarrativeSection(title="연애운과 결혼운", body=body, evidence_ids=["ten_gods"]),
        career=InterpretationNarrativeSection(title="직장운", body=body, evidence_ids=["ten_gods"]),
        wealth=InterpretationNarrativeSection(title="금전운", body=body, evidence_ids=["elements"]),
        luck_flow=InterpretationNarrativeSection(title="현재와 다음 흐름", body=body, evidence_ids=["luck_cycles"]),
        warnings=[],
    )


class GenerateInterpretationTests(unittest.TestCase):
    def test_fallback_lowers_confidence_when_uncertainty_exists(self) -> None:
        report = build_fallback_interpretation_report(make_payload(estimated=True))
        self.assertEqual(report.summary.confidence, "low")

    def test_fallback_does_not_expose_numeric_scores(self) -> None:
        report = build_fallback_interpretation_report(make_payload())
        combined = "\n".join(
            [
                report.summary.overview,
                report.core_analysis.body,
                report.love.body,
                report.career.body,
                report.wealth.body,
            ]
        )
        self.assertIsNone(re.search(r"\d+\s*점", combined))
        self.assertNotIn("/100", combined)

    def test_fallback_sections_are_substantial(self) -> None:
        report = build_fallback_interpretation_report(make_payload())
        self.assertGreaterEqual(len(report.summary.overview), MIN_SUMMARY_LENGTH)
        for section in (
            report.core_analysis,
            report.love,
            report.career,
            report.wealth,
            report.luck_flow,
        ):
            self.assertGreaterEqual(len(section.body), MIN_SECTION_LENGTH)

    def test_prompt_uses_plain_language_heading(self) -> None:
        prompt = get_interpretation_report_prompt().developer_prompt

        self.assertIn("### 쉽게 풀어보면", prompt)
        self.assertIn('Do not use "현실 해석"', prompt)
        self.assertIn("technical saju terms", prompt)
        self.assertIn("Every paragraph should be 1 to 2 sentences", prompt)

    def test_prompt_spec_keeps_version_and_payload_rules_together(self) -> None:
        prompt_spec = get_interpretation_report_prompt()

        self.assertEqual(prompt_spec.version, "saju-report-v14")
        self.assertIn("Use only the provided facts and signals.", prompt_spec.narrative_rules)
        self.assertIn("무조건", prompt_spec.validation_banned_phrases)
        self.assertIn("일간", prompt_spec.core_analysis_technical_terms)

    def test_validator_blocks_numeric_relative_wording(self) -> None:
        payload = make_payload()
        report = make_report()
        report.core_analysis.body += "\n- 상위 10% 수준으로 강합니다.\n"
        issues = _validate_report(report, payload)
        self.assertIn("relative_wording_without_percentile:numeric", issues)

    def test_validator_blocks_banned_phrases(self) -> None:
        payload = make_payload()
        report = make_report()
        report.love.body += "\n- 운명의 상대를 반드시 만납니다.\n"
        issues = _validate_report(report, payload)
        self.assertTrue(any(issue.startswith("banned_phrase:") for issue in issues))

    def test_validator_requires_heading_and_bullets(self) -> None:
        payload = make_payload()
        report = make_report()
        report.career.body = "짧은 본문만 있습니다."
        issues = _validate_report(report, payload)
        self.assertIn("career.body:too_short", issues)
        self.assertIn("career.body:missing_subheadings", issues)
        self.assertIn("career.body:missing_bullets", issues)

    def test_validator_blocks_outdated_plain_reading_heading(self) -> None:
        payload = make_payload()
        report = make_report()
        report.core_analysis.body = report.core_analysis.body.replace("### 1. 핵심 구조", "### 현실 해석")
        issues = _validate_report(report, payload)
        self.assertIn("core_analysis.body:outdated_heading", issues)

    def test_validator_blocks_jargon_heavy_core_analysis_main_body(self) -> None:
        payload = make_payload()
        report = make_report()
        report.core_analysis.body += (
            "\n### 쉽게 풀어보면\n"
            "- 일간, 십성, 상관, 인성, 편관, 정관, 화개, 귀문관, 장성, 괴강을 그대로 나열합니다.\n"
        )
        issues = _validate_report(report, payload)
        self.assertIn("core_analysis.body:too_many_technical_terms", issues)

    def test_validator_blocks_hanja_in_korean_output(self) -> None:
        payload = make_payload(locale="ko")
        report = make_report()
        report.summary.overview += " 甲"
        issues = _validate_report(report, payload)
        self.assertIn("language:contains_hanja", issues)

    def test_validator_blocks_exposed_scores(self) -> None:
        payload = make_payload()
        report = make_report()
        report.summary.overview += " 균형 점수는 57점입니다."
        issues = _validate_report(report, payload)
        self.assertIn("score_exposed_in_user_text", issues)

    def test_generate_interpretation_falls_back_when_validation_fails(self) -> None:
        payload = make_payload(estimated=True)
        invalid_report = make_report(confidence="high")
        invalid_report.summary.overview = "짧음"
        with patch(
            "app.domain.saju.services.generate_interpretation._call_openai_structured_interpretation",
            return_value=(
                invalid_report,
                InterpretationDiagnostics(
                    configured_provider="openai",
                    final_provider="openai",
                    model="gpt-5.4-mini",
                    prompt_version="saju-report-v14",
                    payload_chars=123,
                    duration_ms=999,
                    final_response_id="resp_test",
                    attempts=[],
                ),
            ),
        ), patch(
            "app.domain.saju.services.generate_interpretation.settings.llm_provider",
            "openai",
        ), patch(
            "app.domain.saju.services.generate_interpretation.settings.openai_api_key",
            "test-key",
        ):
            report = generate_interpretation_report(
                payload=payload,
                trace_id="test-trace",
                service_name="suju-insight",
            )
        self.assertEqual(report.provider, "fallback")
        self.assertTrue(report.warnings)
        self.assertIsNotNone(report.diagnostics)
        self.assertEqual(report.diagnostics.fallback_reason, "validation_failed")

    def test_fallback_provider_does_not_call_openai_path(self) -> None:
        payload = make_payload()
        with patch(
            "app.domain.saju.services.generate_interpretation.settings.llm_provider",
            "fallback",
        ), patch(
            "app.domain.saju.services.generate_interpretation._call_openai_structured_interpretation",
            side_effect=AssertionError("OpenAI path must not be called in fallback mode"),
        ):
            report = generate_interpretation_report(
                payload=payload,
                trace_id="test-no-openai",
                service_name="suju-insight",
            )

        self.assertEqual(report.provider, "fallback")
        self.assertEqual(report.diagnostics.fallback_reason, "provider_not_openai")


if __name__ == "__main__":
    unittest.main()
