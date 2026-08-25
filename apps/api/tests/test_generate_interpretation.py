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


def make_body(
    intro: str = "이 사람은 기준이 분명할수록 선택과 행동이 안정되는 편입니다.",
) -> str:
    return f"""
### 핵심 결론
{intro} 첫 문단만 읽어도 이 사람의 핵심 방향이 보이도록 강점, 반복 패턴, 주의점을 함께 정리합니다.

### 쉽게 풀어보면
잘 맞는 환경에서는 판단이 빠르고 해야 할 일을 정리하는 힘이 살아납니다. 반대로 기준이 흐리거나 역할이 계속 바뀌는 환경에서는 성과보다 피로가 먼저 커질 수 있습니다.

이 해석은 사용자가 체감할 수 있는 선택 방식과 반복되는 생활 패턴을 먼저 보여 줍니다. 기술적인 근거는 뒤쪽에 두고, 앞부분에서는 어떤 환경에서 편해지고 어떤 상황에서 소모되는지를 중심으로 설명합니다.

현재 시기는 넓게 벌리기보다 관계, 일, 돈의 기준을 나누어 정리하는 데 의미가 있습니다. 강한 부분은 성과로 연결하고 약한 부분은 루틴과 환경으로 보완할 때 해석이 가장 잘 쓰입니다.

카드 미리보기에서는 핵심만 보여 주더라도, 상세 본문에서는 왜 그런 판단이 나왔는지 차분히 이어져야 합니다. 그래서 첫 문단은 사용자가 바로 이해할 수 있는 요약으로 두고, 뒤쪽에서는 관계의 속도, 일의 역할, 돈의 관리 기준처럼 실제 행동으로 옮길 수 있는 단서를 충분히 설명합니다.

### 조언
- 중요한 선택은 감정의 크기보다 반복해서 유지 가능한지 확인하세요.
- 잘 맞는 환경에서는 속도를 내되 피로가 커지는 구조는 빨리 정리하세요.
- 관계, 일, 돈의 기준을 한꺼번에 섞지 말고 나누어 보세요.
- 지금은 큰 결론보다 작은 기준을 세우는 편이 더 현실적입니다.
- 강점을 더 쓰는 것과 약점을 보완하는 일을 함께 가져가세요.
- 매번 새롭게 결심하기보다 매주 반복할 수 있는 기준을 하나씩 남기세요.

### 풀이 포인트
[오행 균형] [십성 신호] [현재 대운] [분야별 근거]

### 전문가 노트
이 본문은 계산을 새로 하지 않고 이미 만들어진 payload의 신호를 사용자 문장으로 바꾼 예시입니다. 점수, 내부 등급, 원자료 식별자는 사용자 본문에 노출하지 않고 해석 방향만 남깁니다.
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
            spouse_house_label="배우자궁" if locale == "ko" else "Spouse house",
            spouse_house_branch="유" if locale == "ko" else "Yu",
            spouse_house_ten_god="편재" if locale == "ko" else "Indirect Wealth",
            partner_star_label="관성" if locale == "ko" else "Officer star",
            partner_star_count=2,
            active_star_labels=["도화", "홍염"] if locale == "ko" else ["Peach Blossom", "Red Charm"],
        ),
        career_facts=InterpretationCareerFacts(
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
    return InterpretationReport(
        provider="openai",
        model="gpt-5.4",
        prompt_version="saju-report-v15",
        summary=InterpretationSummaryBlock(
            headline="기준을 세우고 오래 밀고 가는 사람",
            overview=(
                "이 사주는 기준을 세우고 오래 밀고 갈 때 힘이 살아나는 사람으로 읽습니다. "
                "강점은 빠르게 정리하고 필요한 일을 꾸준히 밀어붙이는 힘입니다. "
                "반복되는 패턴은 맞는 환경에서는 몰입이 살아나지만 기준이 흐려지면 피로가 먼저 커진다는 점입니다. "
                "현재 시기는 관계, 일, 돈의 기준을 다시 정리하는 의미가 큽니다. "
                "주의할 점은 속도만 믿고 움직이면 지출과 관계 부담이 함께 커질 수 있다는 것입니다. "
                "잘 쓰는 방향은 강한 부분을 성과에 쓰고 약한 부분은 루틴과 환경으로 보완하는 것입니다."
            ),
            confidence=confidence,
            evidence_ids=["elements"],
        ),
        core_analysis=InterpretationNarrativeSection(
            title="내 사주 특징",
            body=make_body("이 사람은 기준이 맞으면 오래 밀고 가고 맞지 않으면 피로를 빨리 알아차리는 편입니다."),
            evidence_ids=["elements"],
        ),
        love=InterpretationNarrativeSection(
            title="연애와 결혼 흐름",
            body=make_body("관계에서는 빠른 확정보다 오래 유지될 수 있는 기준을 확인할 때 마음이 편해지는 편입니다."),
            evidence_ids=["ten_gods"],
        ),
        career=InterpretationNarrativeSection(
            title="직장운",
            body=make_body("일에서는 맡은 역할과 결과물이 분명할수록 실력이 잘 드러나는 편입니다."),
            evidence_ids=["ten_gods"],
        ),
        wealth=InterpretationNarrativeSection(
            title="금전운",
            body=make_body("돈은 크게 단정하기보다 들어온 흐름을 남기고 새는 지점을 줄이는 기준이 중요합니다."),
            evidence_ids=["elements"],
        ),
        luck_flow=InterpretationNarrativeSection(
            title="현재 운과 대운 흐름",
            body=make_body("현재 운은 사건을 확정하기보다 지금 세운 기준이 다음 선택으로 이어지는 시간표에 가깝습니다."),
            evidence_ids=["luck_cycles"],
        ),
        warnings=[],
    )


class GenerateInterpretationTests(unittest.TestCase):
    def test_v15_style_report_passes_validation(self) -> None:
        issues = _validate_report(make_report(), make_payload())
        self.assertEqual(issues, [])

    def test_fallback_report_satisfies_v15_validation(self) -> None:
        payload = make_payload()
        report = build_fallback_interpretation_report(payload)

        self.assertEqual(_validate_report(report, payload), [])

    def test_fallback_uses_neutral_copy_without_missing_elements_or_active_cycle(self) -> None:
        payload = make_payload()
        payload.signals.missing_elements = []
        payload.wealth_facts.missing_elements = []
        payload.current_flow.active_luck_cycle = None
        payload.current_flow.next_luck_cycle = None

        report = build_fallback_interpretation_report(payload)
        combined = "\n".join(
            [
                report.summary.overview,
                report.core_analysis.body,
                report.love.body,
                report.career.body,
                report.wealth.body,
                report.luck_flow.body,
            ]
        )

        self.assertNotIn("없음 쪽", combined)
        self.assertNotIn("없음 기운", combined)
        self.assertNotIn("확인 대기 구간", combined)
        self.assertIn("첫 대운이 시작되기 전", combined)
        self.assertEqual(_validate_report(report, payload), [])

    def test_validator_rejects_unknown_evidence_ids(self) -> None:
        payload = make_payload()
        report = make_report()
        report.love.evidence_ids = ["not-real"]

        issues = _validate_report(report, payload)

        self.assertIn("love.evidence_ids:unknown:not-real", issues)

    def test_fallback_does_not_attach_particles_directly_to_luck_cycle_labels(self) -> None:
        report = build_fallback_interpretation_report(make_payload())
        combined = "\n".join(
            [
                report.summary.overview,
                report.core_analysis.body,
                report.love.body,
                report.career.body,
                report.wealth.body,
                report.luck_flow.body,
            ]
        )
        for awkward in ("신묘을", "신묘를", "신묘로", "신묘으로", "신묘은", "신묘는", "경인을", "경인를", "경인로", "경인으로", "경인은", "경인는"):
            self.assertNotIn(awkward, combined)

    def test_fallback_lowers_confidence_when_uncertainty_exists(self) -> None:
        report = build_fallback_interpretation_report(make_payload(estimated=True))
        self.assertEqual(report.summary.confidence, "low")

    def test_fallback_headline_is_not_generic(self) -> None:
        report = build_fallback_interpretation_report(make_payload())
        self.assertNotIn(report.summary.headline, {"당신의 사주 풀이", "전체 운세 요약", "사주 결과", "핵심 요약", "운세 분석"})

    def test_fallback_summary_overview_has_six_or_more_sentences(self) -> None:
        report = build_fallback_interpretation_report(make_payload())
        sentences = [item.strip() for item in re.split(r"(?<=[.!?。！？])\s+", report.summary.overview) if item.strip()]
        self.assertGreaterEqual(len(sentences), 6)

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

    def test_fallback_section_bodies_include_required_headings(self) -> None:
        report = build_fallback_interpretation_report(make_payload())
        required = ("### 핵심 결론", "### 쉽게 풀어보면", "### 조언", "### 풀이 포인트", "### 전문가 노트")
        for section in (
            report.core_analysis,
            report.love,
            report.career,
            report.wealth,
            report.luck_flow,
        ):
            for heading in required:
                self.assertIn(heading, section.body)

    def test_prompt_uses_plain_language_heading(self) -> None:
        prompt = get_interpretation_report_prompt().developer_prompt

        self.assertIn("### 쉽게 풀어보면", prompt)
        self.assertIn('Do not use "현실 해석"', prompt)
        self.assertIn("technical saju terms", prompt)
        self.assertIn("Every paragraph should be 1 to 2 sentences", prompt)

    def test_prompt_spec_keeps_version_and_payload_rules_together(self) -> None:
        prompt_spec = get_interpretation_report_prompt()

        self.assertEqual(prompt_spec.version, "saju-report-v15")
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

    def test_validator_allows_summary_technical_opening_as_non_blocking(self) -> None:
        payload = make_payload()
        report = make_report()
        report.summary.overview = report.summary.overview.replace(
            "이 사주는 기준을 세우고 오래 밀고 갈 때 힘이 살아나는 사람으로 읽습니다.",
            "일간은 기준을 세우고 오래 밀고 갈 때 힘이 살아나는 사람으로 읽습니다.",
        )
        issues = _validate_report(report, payload)
        self.assertEqual(issues, [])

    def test_validator_allows_section_technical_opening_as_non_blocking(self) -> None:
        payload = make_payload()
        report = make_report()
        report.core_analysis.body = report.core_analysis.body.replace(
            "### 핵심 결론\n",
            "### 핵심 결론\n오행은 먼저 기준을 보여 줍니다. ",
            1,
        )
        issues = _validate_report(report, payload)
        self.assertEqual(issues, [])

    def test_validator_allows_five_sentence_summary_overview(self) -> None:
        payload = make_payload()
        report = make_report()
        report.summary.overview = (
            "이 사주는 기준을 세우고 오래 밀고 갈 때 힘이 살아나는 사람으로 읽습니다. "
            "강점은 빠르게 정리하고 필요한 일을 꾸준히 밀어붙이는 힘이며, 중요한 선택을 할 때도 스스로 납득할 수 있는 기준을 찾으려는 태도입니다. "
            "반복되는 패턴은 맞는 환경에서는 몰입이 살아나지만 기준이 흐려지면 피로가 먼저 커진다는 점이고, 이때 관계와 일과 돈의 판단이 한꺼번에 섞일 수 있습니다. "
            "현재 시기는 관계와 일과 돈의 기준을 다시 정리하는 의미가 크고, 작은 루틴을 만드는 데 도움이 되는 구간으로 보는 편이 자연스럽습니다. "
            "주의할 점은 속도만 믿고 움직이면 지출과 관계 부담이 함께 커질 수 있어서 오래 유지할 기준을 먼저 세워야 한다는 것입니다."
        )
        issues = _validate_report(report, payload)
        self.assertEqual(issues, [])

    def test_validator_blocks_four_sentence_summary_overview(self) -> None:
        payload = make_payload()
        report = make_report()
        report.summary.overview = (
            "이 사주는 기준을 세우고 오래 밀고 갈 때 힘이 살아나는 사람으로 읽습니다. "
            "강점은 빠르게 정리하고 필요한 일을 꾸준히 밀어붙이는 힘이며, 중요한 선택을 할 때도 스스로 납득할 수 있는 기준을 찾으려는 태도입니다. "
            "반복되는 패턴은 맞는 환경에서는 몰입이 살아나지만 기준이 흐려지면 피로가 먼저 커진다는 점이고, 이때 관계와 일과 돈의 판단이 한꺼번에 섞일 수 있습니다. "
            "현재 시기는 관계와 일과 돈의 기준을 다시 정리하는 의미가 크지만, 속도만 믿고 움직이면 지출과 관계 부담이 함께 커질 수 있어서 오래 유지할 기준을 먼저 세워야 한다는 것입니다."
        )
        issues = _validate_report(report, payload)
        self.assertIn("summary.overview:too_few_sentences", issues)

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
        report.core_analysis.body = report.core_analysis.body.replace("### 쉽게 풀어보면", "### 현실 해석")
        issues = _validate_report(report, payload)
        self.assertIn("core_analysis.body:outdated_heading", issues)

    def test_validator_blocks_jargon_heavy_core_analysis_main_body(self) -> None:
        payload = make_payload()
        report = make_report()
        report.core_analysis.body = report.core_analysis.body.replace(
            "### 풀이 포인트",
            "일간, 십성, 상관, 인성, 편관, 정관, 화개, 귀문관, 장성, 괴강을 그대로 나열합니다.\n\n### 풀이 포인트",
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

    def test_validator_blocks_internal_values_in_user_text(self) -> None:
        payload = make_payload()
        report = make_report()
        report.summary.overview += " balance_score: 57 internal_grade: B evidence_id: debug"
        issues = _validate_report(report, payload)
        self.assertIn("score_exposed_in_user_text", issues)

    def test_validator_blocks_internal_values_in_section_preview(self) -> None:
        payload = make_payload()
        report = make_report()
        report.career.body = report.career.body.replace(
            "### 핵심 결론\n",
            "### 핵심 결론\nbalance_score: 71 내부값이 노출된 문장입니다. ",
        )
        issues = _validate_report(report, payload)
        self.assertIn("career.body:internal_value_leak_in_preview", issues)

    def test_validator_blocks_generic_headline(self) -> None:
        payload = make_payload()
        report = make_report()
        report.summary.headline = "핵심 요약"
        issues = _validate_report(report, payload)
        self.assertIn("summary.headline:generic", issues)

    def test_validator_blocks_score_colon_in_user_text(self) -> None:
        payload = make_payload()
        report = make_report()
        report.core_analysis.body = report.core_analysis.body.replace(
            "### 핵심 결론\n",
            "### 핵심 결론\n점수: 80점입니다. ",
            1,
        )
        issues = _validate_report(report, payload)
        self.assertIn("score_exposed_in_user_text", issues)

    def test_validator_blocks_one_hundred_percent(self) -> None:
        payload = make_payload()
        report = make_report()
        report.core_analysis.body += "\n- 100% 좋은 결과입니다.\n"
        issues = _validate_report(report, payload)
        self.assertIn("banned_phrase:100%", issues)

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
                    prompt_version="saju-report-v15",
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

    def test_codex_provider_uses_codex_path_without_openai_key(self) -> None:
        payload = make_payload()
        codex_report = make_report()
        codex_report.provider = "codex"
        codex_report.model = "codex-cli"
        diagnostics = InterpretationDiagnostics(
            configured_provider="codex",
            final_provider="codex",
            model="codex-cli",
            prompt_version="saju-report-v15",
            payload_chars=123,
            duration_ms=999,
            final_response_id="codex-test",
            attempts=[],
        )

        with patch(
            "app.domain.saju.services.generate_interpretation.settings.llm_provider",
            "codex",
        ), patch(
            "app.domain.saju.services.generate_interpretation.settings.openai_api_key",
            "",
        ), patch(
            "app.domain.saju.services.generate_interpretation._call_openai_structured_interpretation",
            side_effect=AssertionError("OpenAI path must not be called in Codex mode"),
        ), patch(
            "app.domain.saju.services.generate_interpretation._call_codex_structured_interpretation",
            return_value=(codex_report, diagnostics),
        ):
            report = generate_interpretation_report(
                payload=payload,
                trace_id="test-codex",
                service_name="suju-insight",
            )

        self.assertEqual(report.provider, "codex")
        self.assertIsNotNone(report.diagnostics)
        self.assertEqual(report.diagnostics.final_provider, "codex")


if __name__ == "__main__":
    unittest.main()
