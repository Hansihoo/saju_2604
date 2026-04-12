import unittest
from unittest.mock import patch

from app.domain.saju.interpretation import (
    InterpretationActionBlock,
    InterpretationDomainBlock,
    InterpretationListBlock,
    InterpretationReport,
    InterpretationSummaryBlock,
)
from app.domain.saju.llm_payload import (
    InterpretationEvidenceItem,
    InterpretationInputProfile,
    InterpretationPayload,
    InterpretationSignalBlock,
    InterpretationSpecialStar,
    InterpretationTimeContext,
    InterpretationVisiblePillar,
)
from app.domain.saju.services.generate_interpretation import (
    _validate_report,
    build_fallback_interpretation_report,
    generate_interpretation_report,
)


def make_payload(*, estimated: bool = False) -> InterpretationPayload:
    return InterpretationPayload(
        output_sections=["summary", "strengths", "cautions", "love", "career", "wealth", "action_advice"],
        profile=InterpretationInputProfile(
            calendar_type="solar",
            birth_date="2024-02-10",
            birth_time="00:00" if estimated else "10:30",
            is_birth_time_estimated=estimated,
            is_lunar_leap_month=False,
            gender="male",
            region_id="kr-seoul",
            region_display_name="서울특별시",
            tzid="Asia/Seoul",
        ),
        time_context=InterpretationTimeContext(
            normalized_local_datetime="2024-02-10 10:30:00",
            normalized_utc_datetime="2024-02-10 01:30:00",
            corrected_solar_datetime="2024-02-10 09:57:58",
            regional_time_offset_minutes=-32.02,
            daylight_saving_offset_minutes=0,
            correction_basis="local_mean_time",
        ),
        visible_pillars=[
            InterpretationVisiblePillar(key="year", label="연주", gan_zhi="甲辰", stem="甲", branch="辰"),
            InterpretationVisiblePillar(key="month", label="월주", gan_zhi="丙寅", stem="丙", branch="寅"),
            InterpretationVisiblePillar(key="day", label="일주", gan_zhi="甲辰", stem="甲", branch="辰"),
            InterpretationVisiblePillar(key="time", label="시주", gan_zhi="己巳", stem="己", branch="巳"),
        ],
        day_master="甲",
        element_counts={"wood": 3, "fire": 2, "earth": 3, "metal": 0, "water": 0},
        ten_god_stems={"year": "비견", "month": "식신", "day": "", "time": "정재"},
        signals=InterpretationSignalBlock(
            internal_grade="B",
            balance_score=35,
            charm_score=42,
            wealth_score=58,
            career_score=63,
            leadership_score=49,
            dominant_elements=["wood", "earth"],
            missing_elements=["metal", "water"],
        ),
        evidence=[
            InterpretationEvidenceItem(key="elements", title="Five Elements", status="ready", summary="elements"),
            InterpretationEvidenceItem(key="ten_gods", title="Ten Gods", status="ready", summary="ten gods"),
            InterpretationEvidenceItem(key="luck_cycles", title="Luck Cycles", status="ready", summary="luck cycles"),
        ],
        luck_cycles=[],
        supplementary_positions=[],
        special_stars=[
            InterpretationSpecialStar(
                key="wangji-dohwa",
                label="왕지도화",
                tier="B",
                category="sinsal",
                usage_summary="도화 계열 보조 지표",
                matched_pillars=["year"],
                evidence_id="star:wangji-dohwa",
            )
        ],
        limitations=["출생시간 미상으로 시주 해석 제한"] if estimated else [],
        disabled_sections=["time_pillar"] if estimated else [],
        notes=[],
        narrative_rules=[],
        prompt_seed=None,
    )


def make_report(*, confidence: str = "medium", advice_text: str = "1. 속도를 조절하세요. 2. 기대치를 먼저 맞추세요.") -> InterpretationReport:
    return InterpretationReport(
        provider="openai",
        model="gpt-5.4",
        prompt_version="saju-report-v2",
        summary=InterpretationSummaryBlock(
            headline="관계의 속도 조절이 중요한 흐름",
            core_theme="호감은 생기지만 리듬을 맞추는 과정이 중요합니다.",
            confidence=confidence,
            evidence_ids=["elements"],
        ),
        strengths=InterpretationListBlock(
            items=["감정의 반응은 분명한 편입니다."],
            analysis="호감이 생기면 관계의 방향을 비교적 빨리 잡는 편입니다.",
            evidence_ids=["elements"],
        ),
        cautions=InterpretationListBlock(
            items=["속도 차이를 놓치면 피로가 쌓일 수 있습니다."],
            analysis="관계의 온도 차이를 관리하지 않으면 오해가 커질 수 있습니다.",
            evidence_ids=["elements"],
        ),
        love=InterpretationDomainBlock(
            score=42,
            tone="mixed",
            strengths=["호감 신호를 알아차리는 편입니다."],
            risks=["표현 속도가 상대보다 빠르면 부담이 생길 수 있습니다."],
            conditions=["반응을 확인하며 표현 강도를 조절하는 편이 좋습니다."],
            analysis="호감은 분명하지만 속도를 조절할수록 관계가 안정됩니다.",
            evidence_ids=["elements", "star:wangji-dohwa"],
        ),
        career=InterpretationDomainBlock(
            score=63,
            tone="mixed",
            strengths=["일에서는 추진력이 비교적 살아 있습니다."],
            risks=["균형이 깨지면 집중력이 흔들릴 수 있습니다."],
            conditions=["일정 리듬을 고르게 유지하는 편이 좋습니다."],
            analysis="무리하지 않으면 강점을 유지하기 좋습니다.",
            evidence_ids=["elements"],
        ),
        wealth=InterpretationDomainBlock(
            score=58,
            tone="mixed",
            strengths=["기본 흐름은 무난한 편입니다."],
            risks=["기분에 따라 지출이 흔들릴 수 있습니다."],
            conditions=["지출 기준을 먼저 정하면 안정적입니다."],
            analysis="크게 몰아가기보다 균형이 중요합니다.",
            evidence_ids=["elements"],
        ),
        action_advice=InterpretationActionBlock(
            text=advice_text,
            evidence_ids=["elements"],
        ),
        luck_cycles=[],
        warnings=[],
    )


class GenerateInterpretationTests(unittest.TestCase):
    def test_fallback_lowers_confidence_when_uncertainty_exists(self) -> None:
        report = build_fallback_interpretation_report(make_payload(estimated=True))
        self.assertEqual(report.summary.confidence, "low")

    def test_validator_blocks_relative_wording_without_percentile_support(self) -> None:
        payload = make_payload()
        report = make_report()
        report.love.analysis = "상위 10% 수준의 끌림이 보입니다."
        issues = _validate_report(report, payload)
        self.assertTrue(any(issue.startswith("relative_wording_without_percentile") for issue in issues))

    def test_validator_blocks_banned_phrases(self) -> None:
        payload = make_payload()
        report = make_report()
        report.summary.core_theme = "운명의 상대를 반드시 만나는 흐름입니다."
        issues = _validate_report(report, payload)
        self.assertTrue(any(issue.startswith("banned_phrase:") for issue in issues))

    def test_generate_interpretation_falls_back_when_validation_fails(self) -> None:
        payload = make_payload(estimated=True)
        invalid_report = make_report(confidence="high")
        with patch(
            "app.domain.saju.services.generate_interpretation._call_openai_structured_interpretation",
            return_value=(invalid_report, "resp_test"),
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


if __name__ == "__main__":
    unittest.main()
