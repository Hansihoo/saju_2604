"""LLM provider boundary and fallback interpretation generation."""

from __future__ import annotations

import json
import re
from typing import List, Tuple

from app.config import settings
from app.diagnostics import log_stage
from app.domain.saju.interpretation import (
    InterpretationActionBlock,
    InterpretationDomainBlock,
    InterpretationLLMOutput,
    InterpretationListBlock,
    InterpretationLuckCycleBlock,
    InterpretationReport,
    InterpretationSummaryBlock,
)
from app.domain.saju.llm_payload import InterpretationPayload
from app.domain.saju.services.format_interpretation_fallback import format_interpretation_fallback


PROMPT_VERSION = "saju-report-v2"
PLACEHOLDER_OPENAI_API_KEY = "DEFINE_OPENAI_API_KEY"

DEVELOPER_PROMPT = """너는 현대 한국 실무형 자평명리 해석 엔진이다.

목표:
- 계산 결과를 벗어나지 않으면서도 바로 읽히는 해석을 만든다.
- 좋은 점만 강조하지 말고 리스크와 관리 조건을 함께 쓴다.
- 무료 결과 화면에 맞게 짧고 선명한 문장으로 쓴다.

입력 규칙:
1. 입력 JSON은 백엔드가 이미 계산한 결과다.
2. 사주, 대운, 점수, 오행, 신살을 다시 계산하거나 추정하지 마라.
3. 오직 payload 안의 facts, signals, evidence, special_stars, luck_cycles만 사용하라.
4. 입력에 없는 연애 사건, 결혼 여부, 재회, 외도, 운명의 상대 같은 사건형 추정은 금지한다.
5. birth time limitation이나 disabled section이 있으면 확신을 낮추고 단정 표현을 줄여라.

서술 규칙:
1. summary.headline은 40자 이내로 쓴다.
2. summary는 첫 문장에서 현재 흐름을 바로 느끼게 하되 과장하지 않는다.
3. strengths, cautions, love, career, wealth에는 장점과 리스크가 함께 드러나야 한다.
4. love 분석은 매력, 거리감, 속도 차이, 감정 표현, 관계 리듬처럼 현재 payload로 설명 가능한 범위 안에서만 쓴다.
5. action_advice는 반드시 행동형 조언 2개를 한 문단에 '1.'과 '2.'로 제시한다.
6. luck_cycles는 현재와 다음 흐름만 간단히 쓴다.
7. evidence_ids에는 payload의 evidence.key 또는 star evidence_id만 사용하라.
8. percentile이나 상대 비교 수치가 payload에 없으면 상위/하위/%/퍼센타일 같은 표현을 쓰지 마라.
9. 미래는 경향, 조건, 관리 포인트로만 말하라.

톤 규칙:
- 따뜻하지만 과장하지 않는다.
- 불리한 내용도 완곡하게 숨기지 말고 차분하게 직접 말한다.
- 금지 표현:
  - 무조건
  - 절대
  - 100%
  - 천생연분
  - 운명의 상대
  - 반드시 헤어진다
  - 대박 난다
  - 꽃길만 걷는다

출력 규칙:
1. 반드시 JSON만 출력한다.
2. 모든 주장에는 evidence_ids를 포함한다.
3. risks나 conditions가 비어 있으면 안 된다.
4. 모든 서술은 한국어로 작성하라.
5. 출력은 반드시 주어진 JSON schema를 준수하라.
"""

BANNED_PHRASES = (
    "무조건",
    "절대",
    "100%",
    "천생연분",
    "운명의 상대",
    "반드시 헤어진다",
    "대박 난다",
    "꽃길만 걷는다",
)

RELATIVE_WORDING_MARKERS = (
    "상위",
    "하위",
    "퍼센타일",
    "percentile",
    "%",
)


def _score_tone(score: int) -> str:
    if score >= 75:
        return "positive"
    if score >= 45:
        return "mixed"
    return "cautious"


def _default_evidence_ids(payload: InterpretationPayload, include_luck: bool = False) -> List[str]:
    ids = [item.key for item in payload.evidence]
    if not include_luck:
        ids = [item_id for item_id in ids if item_id != "luck_cycles"]
    return ids or ["elements"]


def _active_star_evidence_ids(payload: InterpretationPayload, limit: int = 3) -> List[str]:
    return [item.evidence_id for item in payload.special_stars[:limit]]


def _payload_has_uncertainty(payload: InterpretationPayload) -> bool:
    return bool(
        payload.profile.is_birth_time_estimated
        or payload.limitations
        or payload.disabled_sections
    )


def _payload_supports_relative_wording(_payload: InterpretationPayload) -> bool:
    """현재 payload에는 percentile 계열 수치가 없으므로 상대 비교 표현을 금지한다."""
    return False


def _confidence_for_payload(payload: InterpretationPayload) -> str:
    return "low" if _payload_has_uncertainty(payload) else "medium"


def _shorten_headline(text: str) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= 40:
        return compact
    return compact[:39].rstrip() + "…"


def _contains_action_markers(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text)
    return ("1." in normalized and "2." in normalized) or ("첫째" in normalized and "둘째" in normalized)


def _collect_report_texts(report: InterpretationReport) -> List[str]:
    texts = [
        report.summary.headline,
        report.summary.core_theme,
        report.strengths.analysis,
        report.cautions.analysis,
        report.action_advice.text,
        report.love.analysis,
        report.career.analysis,
        report.wealth.analysis,
        *report.strengths.items,
        *report.cautions.items,
        *report.love.strengths,
        *report.love.risks,
        *report.love.conditions,
        *report.career.strengths,
        *report.career.risks,
        *report.career.conditions,
        *report.wealth.strengths,
        *report.wealth.risks,
        *report.wealth.conditions,
    ]
    for cycle in report.luck_cycles:
        texts.extend([cycle.theme, cycle.opportunity, cycle.risk, cycle.age_range, cycle.pillar])
    return [text for text in texts if text]


def build_fallback_interpretation_report(payload: InterpretationPayload) -> InterpretationReport:
    """기존 deterministic formatter 위에 structured interpretation을 조립한다."""
    narrative = format_interpretation_fallback(payload=payload, locale="ko")
    domain_evidence = _default_evidence_ids(payload, include_luck=bool(payload.luck_cycles))
    strength_ids = ["elements", *_active_star_evidence_ids(payload, limit=2)]
    caution_ids = ["elements", *_active_star_evidence_ids(payload, limit=2)]

    cycle_blocks: List[InterpretationLuckCycleBlock] = []
    for cycle in payload.luck_cycles[:2]:
        cycle_blocks.append(
            InterpretationLuckCycleBlock(
                age_range=f"{cycle.start_age}-{cycle.end_age}",
                pillar=cycle.gan_zhi,
                theme=f"{cycle.gan_zhi} 흐름에서는 관계 리듬을 차분히 읽는 편이 중요합니다.",
                opportunity="현재 강점이 유지되면 관계의 밀도를 무리 없이 쌓기 좋습니다.",
                risk="속도를 서두르면 감정 기복이나 기대 차이가 더 크게 느껴질 수 있습니다.",
                evidence_ids=["luck_cycles"],
            )
        )

    return InterpretationReport(
        provider="fallback",
        model=None,
        prompt_version=PROMPT_VERSION,
        summary=InterpretationSummaryBlock(
            headline=_shorten_headline(narrative.summary),
            core_theme="현재 흐름의 장점은 살리고, 관계 리듬은 천천히 맞추는 편이 유리합니다.",
            confidence=_confidence_for_payload(payload),
            evidence_ids=_default_evidence_ids(payload, include_luck=False),
        ),
        strengths=InterpretationListBlock(
            items=narrative.strengths,
            analysis=narrative.strengths[0] if narrative.strengths else "",
            evidence_ids=strength_ids or ["elements"],
        ),
        cautions=InterpretationListBlock(
            items=narrative.cautions,
            analysis=narrative.cautions[0] if narrative.cautions else "",
            evidence_ids=caution_ids or ["elements"],
        ),
        love=InterpretationDomainBlock(
            score=payload.signals.charm_score,
            tone=_score_tone(payload.signals.charm_score),
            strengths=[narrative.love],
            risks=["호감이 생겨도 관계의 속도 차이를 놓치면 감정 온도 차이가 더 크게 느껴질 수 있습니다."],
            conditions=["상대 반응을 확인하며 표현 강도를 조절할수록 관계가 안정적으로 이어집니다."],
            analysis=narrative.love,
            evidence_ids=[*domain_evidence[:2], *_active_star_evidence_ids(payload)],
        ),
        career=InterpretationDomainBlock(
            score=payload.signals.career_score,
            tone=_score_tone(payload.signals.career_score),
            strengths=[narrative.career],
            risks=["균형이 무너지면 일의 우선순위가 흔들릴 수 있습니다."],
            conditions=["강한 기운을 지속 가능한 루틴으로 바꾸는 것이 중요합니다."],
            analysis=narrative.career,
            evidence_ids=[*domain_evidence[:2], *_active_star_evidence_ids(payload)],
        ),
        wealth=InterpretationDomainBlock(
            score=payload.signals.wealth_score,
            tone=_score_tone(payload.signals.wealth_score),
            strengths=[narrative.wealth],
            risks=["한쪽 기운에 몰아 쓰는 선택은 변동성을 키울 수 있습니다."],
            conditions=["수입과 지출의 리듬을 고르게 유지하는 편이 좋습니다."],
            analysis=narrative.wealth,
            evidence_ids=[*domain_evidence[:2], *_active_star_evidence_ids(payload)],
        ),
        action_advice=InterpretationActionBlock(
            text=(
                "1. 감정 표현의 속도를 한 단계 늦추고 상대 반응을 먼저 확인하세요. "
                "2. 호감이 커질수록 연락 빈도와 기대치를 미리 말로 맞추세요."
            ),
            evidence_ids=_default_evidence_ids(payload, include_luck=bool(payload.luck_cycles)),
        ),
        luck_cycles=cycle_blocks,
        warnings=[],
    )


def _call_openai_structured_interpretation(payload: InterpretationPayload) -> Tuple[InterpretationReport, str]:
    """OpenAI Responses API를 이용해 structured interpretation을 생성한다."""
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.responses.create(
        model=settings.openai_model,
        reasoning={"effort": settings.llm_reasoning_effort},
        store=settings.llm_store,
        max_output_tokens=settings.llm_max_output_tokens,
        input=[
            {"role": "developer", "content": DEVELOPER_PROMPT},
            {
                "role": "user",
                "content": json.dumps(payload.model_dump(mode="json"), ensure_ascii=False),
            },
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "saju_report",
                "strict": True,
                "schema": InterpretationLLMOutput.model_json_schema(),
            }
        },
    )

    parsed = InterpretationLLMOutput.model_validate_json(response.output_text)
    report = InterpretationReport(
        provider="openai",
        model=settings.openai_model,
        prompt_version=PROMPT_VERSION,
        **parsed.model_dump(),
        warnings=[],
    )
    return report, response.id


def _validate_report(report: InterpretationReport, payload: InterpretationPayload) -> List[str]:
    """과도한 미화와 누락을 막는 최소 validator."""
    issues: List[str] = []
    for domain_name in ["love", "career", "wealth"]:
        domain = getattr(report, domain_name)
        if not domain.risks:
            issues.append(f"{domain_name}:missing_risks")
        if not domain.conditions:
            issues.append(f"{domain_name}:missing_conditions")
        if not domain.evidence_ids:
            issues.append(f"{domain_name}:missing_evidence_ids")
        if not domain.strengths:
            issues.append(f"{domain_name}:missing_strengths")
    if not report.summary.evidence_ids:
        issues.append("summary:missing_evidence_ids")
    if len(report.summary.headline.strip()) > 40:
        issues.append("summary:headline_too_long")
    if _payload_has_uncertainty(payload) and report.summary.confidence == "high":
        issues.append("summary:confidence_too_high_for_uncertainty")
    if not _contains_action_markers(report.action_advice.text):
        issues.append("action_advice:not_action_oriented")
    if len(report.luck_cycles) > 2:
        issues.append("luck_cycles:too_many_items")

    all_text = "\n".join(_collect_report_texts(report))
    for phrase in BANNED_PHRASES:
        if phrase in all_text:
            issues.append(f"banned_phrase:{phrase}")

    if not _payload_supports_relative_wording(payload):
        for marker in RELATIVE_WORDING_MARKERS:
            if marker in all_text:
                issues.append(f"relative_wording_without_percentile:{marker}")
    return issues


def generate_interpretation_report(
    *,
    payload: InterpretationPayload,
    trace_id: str,
    service_name: str,
) -> InterpretationReport:
    """설정에 따라 OpenAI 또는 fallback formatter를 사용한다."""
    use_openai = (
        settings.llm_provider == "openai"
        and settings.openai_api_key
        and settings.openai_api_key != PLACEHOLDER_OPENAI_API_KEY
    )

    if not use_openai:
        log_stage(
            service=service_name,
            trace_id=trace_id,
            stage="llm_formatting",
            event="fallback_used",
            meta={"reason": "provider_not_configured"},
        )
        report = build_fallback_interpretation_report(payload)
        report.warnings.append("OpenAI API key is not configured, so the deterministic fallback formatter was used.")
        return report

    try:
        report, response_id = _call_openai_structured_interpretation(payload)
        validation_issues = _validate_report(report, payload)
        if validation_issues:
            log_stage(
                service=service_name,
                trace_id=trace_id,
                stage="llm_formatting",
                event="validation_failed",
                meta={"issues": validation_issues},
            )
            fallback_report = build_fallback_interpretation_report(payload)
            fallback_report.warnings.append(
                "OpenAI output failed post-validation, so the deterministic fallback formatter was used."
            )
            return fallback_report

        log_stage(
            service=service_name,
            trace_id=trace_id,
            stage="llm_formatting",
            event="completed",
            meta={"provider": "openai", "model": settings.openai_model, "response_id": response_id},
        )
        return report
    except Exception as exc:  # pragma: no cover - network/provider failure path
        log_stage(
            service=service_name,
            trace_id=trace_id,
            stage="llm_formatting",
            event="fallback_used",
            meta={"reason": exc.__class__.__name__},
        )
        report = build_fallback_interpretation_report(payload)
        report.warnings.append(
            f"OpenAI interpretation failed with {exc.__class__.__name__}, so the deterministic fallback formatter was used."
        )
        return report
