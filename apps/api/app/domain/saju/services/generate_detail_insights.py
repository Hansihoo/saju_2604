"""Prepare and render section-level expandable saju insight details."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import time
from collections import OrderedDict
from datetime import datetime, timezone
from json import JSONDecodeError
from threading import Lock
from typing import Any, Dict, List, Sequence, Tuple

from pydantic import ValidationError

from app.config import PLACEHOLDER_OPENAI_API_KEY, settings
from app.domain.saju.interpretation import (
    SajuDetailBody,
    SajuDetailPeriod,
    SajuDetailPreparedReport,
    SajuDetailRenderedReport,
    SajuDetailType,
)
from app.domain.saju.llm_payload import InterpretationPayload
from app.domain.saju.pydantic_compat import model_to_dict, model_validate_compat
from app.domain.saju.schemas import SajuPreviewRequest
from app.domain.saju.services.codex_provider import CodexProviderError, call_codex_json
from app.domain.saju.services.build_interpretation_payload import build_interpretation_payload
from app.domain.saju.services.preview_orchestrator import create_saju_preview_response

try:  # pragma: no cover - optional in local fallback test envs.
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


DETAIL_PROMPT_VERSION = "saju-detail-render-v2"
DETAIL_TYPES: Tuple[SajuDetailType, ...] = (
    "love_timing",
    "wealth_timing",
    "career_timing",
)
FORBIDDEN_USER_TEXT = (
    "무료",
    "유료",
    "프리미엄",
    "결제",
    "반드시",
    "무조건",
    "운명적으로",
    "100%",
    "대박",
    "큰돈을 번다",
    "결혼한다",
    "이혼한다",
    "재회한다",
    "바람난다",
    "사고가 난다",
    "병이 생긴다",
    "죽음",
    "파산",
    "망한다",
    "score",
    "balance_score",
    "internal_grade",
    "evidence_id",
    "점수:",
    "등급:",
    "100점",
)

_DETAIL_BUNDLE_CACHE: OrderedDict[
    Tuple[str, str],
    Tuple[SajuDetailPreparedReport, float],
] = OrderedDict()
_DETAIL_RENDER_CACHE: OrderedDict[
    Tuple[str, str, str, str],
    Tuple[Tuple[SajuDetailRenderedReport, str], float],
] = OrderedDict()
_DETAIL_CACHE_LOCK = Lock()


DETAIL_RENDER_DEVELOPER_PROMPT = """
You render one expandable saju detail insight as concise JSON.

Rules:
- Do not calculate saju. Use only the provided detail_payload facts.
- Do not invent missing periods, stars, scores, or deterministic events.
- Do not expose score, internal_grade, evidence_id, raw evidence ids, or point-based phrasing.
- Do not use the words 무료, 유료, 프리미엄, or 결제 in any user-facing field.
- For Korean locale, write user-facing fields in Hangul/Korean prose only. Do not include Hanja characters.
- Do not guarantee marriage, breakup, reunion, disease, accident, bankruptcy, or investment profit.
- "좋아지는 시기" means relatively easier timing, not a guaranteed event.
- Keep the result short enough for an inline expanded panel.
- Return valid JSON only.
""".strip()


def _prune_detail_cache(cache: OrderedDict) -> None:
    ttl_seconds = settings.detail_cache_ttl_seconds
    if ttl_seconds <= 0:
        cache.clear()
        return

    now = time.monotonic()
    expired_keys = [
        key
        for key, (_, cached_at) in cache.items()
        if now - cached_at >= ttl_seconds
    ]
    for key in expired_keys:
        cache.pop(key, None)


def _get_detail_cache_item(cache: OrderedDict, cache_key: Tuple[str, ...]):
    with _DETAIL_CACHE_LOCK:
        _prune_detail_cache(cache)
        cached = cache.get(cache_key)
        if cached is None:
            return None
        cache.move_to_end(cache_key)
        return cached[0]


def _set_detail_cache_item(cache: OrderedDict, cache_key: Tuple[str, ...], value: Any) -> None:
    if settings.detail_cache_ttl_seconds <= 0:
        return

    with _DETAIL_CACHE_LOCK:
        _prune_detail_cache(cache)
        cache[cache_key] = (value, time.monotonic())
        cache.move_to_end(cache_key)
        while len(cache) > settings.detail_cache_max_entries:
            cache.popitem(last=False)


def compute_detail_input_hash(payload: SajuPreviewRequest) -> str:
    payload_dict = (
        payload.model_dump(mode="json")
        if hasattr(payload, "model_dump")
        else json.loads(payload.json())
    )
    raw = json.dumps(payload_dict, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _model_json_schema(model_class: Any) -> Dict[str, Any]:
    if hasattr(model_class, "model_json_schema"):
        return model_class.model_json_schema()
    return model_class.schema()


def _make_openai_json_schema_strict(name: str, schema: Dict[str, Any]) -> Dict[str, Any]:
    strict_schema = copy.deepcopy(schema)

    def tighten(node: Dict[str, Any]) -> None:
        if node.get("type") == "object":
            node.setdefault("additionalProperties", False)
            properties = node.get("properties")
            if isinstance(properties, dict):
                for child in properties.values():
                    if isinstance(child, dict):
                        tighten(child)
                node["required"] = list(properties.keys())
        if node.get("type") == "array":
            items = node.get("items")
            if isinstance(items, dict):
                tighten(items)
        for key in ("anyOf", "oneOf", "allOf"):
            variants = node.get(key)
            if isinstance(variants, list):
                for variant in variants:
                    if isinstance(variant, dict):
                        tighten(variant)
        defs = node.get("$defs") or node.get("definitions")
        if isinstance(defs, dict):
            for definition in defs.values():
                if isinstance(definition, dict):
                    tighten(definition)

    tighten(strict_schema)
    return {"type": "json_schema", "name": name, "strict": True, "schema": strict_schema}


def _join(values: Sequence[str], fallback: str) -> str:
    clean = [value for value in values if value]
    return ", ".join(clean) if clean else fallback


def _period_from_cycle(cycle: Any | None) -> str:
    if not cycle:
        return "확인 가능한 시기"
    start = getattr(cycle, "start_year", None)
    end = getattr(cycle, "end_year", None)
    if start and end:
        return f"{start}년-{end}년"
    return getattr(cycle, "period", "") or "확인 가능한 시기"


def _analysis_periods(payload: InterpretationPayload, domain: str) -> List[Dict[str, object]]:
    periods: List[Dict[str, object]] = []
    for analysis in payload.luck_cycle_analysis:
        favorable = domain in analysis.favorable_domains
        caution = domain in analysis.caution_domains
        if not favorable and not caution:
            continue
        periods.append(
            {
                "period": analysis.period or f"{analysis.start_year}년-{analysis.end_year}년",
                "display_gan_zhi": analysis.display_gan_zhi,
                "impact": "positive" if favorable else "caution",
                "reason_tags": analysis.reason_tags[:4],
                "caution_tags": analysis.caution_tags[:4],
                "good_for": analysis.good_for[:4],
                "watch_out": analysis.watch_out[:4],
                "summary": analysis.summary,
            }
        )
    if periods:
        return periods[:4]

    cycle = payload.current_flow.active_luck_cycle or payload.current_flow.next_luck_cycle
    return [
        {
            "period": _period_from_cycle(cycle),
            "impact": "neutral",
            "reason_tags": payload.luck_flow_facts.now_action_tags[:4],
            "caution_tags": [],
            "good_for": [],
            "watch_out": [],
            "summary": "현재 확인 가능한 큰 시기 안에서 생활 선택을 조정하는 흐름입니다.",
        }
    ]


def _base_context(payload: InterpretationPayload) -> Dict[str, object]:
    return {
        "day_master": payload.day_master,
        "visible_pillars": [model_to_dict(pillar, mode="json") for pillar in payload.visible_pillars],
        "element_analysis": {
            "counts": dict(payload.element_counts),
            "dominant_elements": payload.signals.dominant_elements,
            "missing_elements": payload.signals.missing_elements,
        },
        "ten_gods": dict(payload.ten_god_stems),
        "current_flow": model_to_dict(payload.current_flow, mode="json"),
        "limitations": list(payload.limitations),
        "uncertainty_summary": [model_to_dict(flag, mode="json") for flag in payload.uncertainty_summary],
    }


def _detail_bundle(payload: InterpretationPayload) -> Dict[str, Dict[str, object]]:
    return {
        "love_timing": {
            "available": True,
            "basis": {
                "luck_cycle_analysis": _analysis_periods(payload, "love"),
                "partner_star_activated_years": payload.love_facts.active_star_labels,
                "spouse_house_relations": [payload.love_facts.spouse_house_label],
            },
            "best_periods": _analysis_periods(payload, "love")[:2],
            "caution_periods": [
                period
                for period in _analysis_periods(payload, "love")
                if period["impact"] == "caution"
            ][:2],
        },
        "wealth_timing": {
            "available": True,
            "basis": {
                "luck_cycle_analysis": _analysis_periods(payload, "wealth"),
                "wealth_facts": model_to_dict(payload.wealth_facts, mode="json"),
            },
            "best_periods": _analysis_periods(payload, "wealth")[:2],
            "caution_periods": [period for period in _analysis_periods(payload, "wealth") if period["impact"] == "caution"][:2],
        },
        "career_timing": {
            "available": True,
            "basis": {
                "career_facts": model_to_dict(payload.career_facts, mode="json"),
                "current_flow": model_to_dict(payload.current_flow, mode="json"),
                "luck_cycle_analysis": _analysis_periods(payload, "career"),
            },
            "move_review_periods": _analysis_periods(payload, "career")[:2],
            "stabilize_periods": _analysis_periods(payload, "career")[2:4],
            "caution_periods": [period for period in _analysis_periods(payload, "career") if period["impact"] == "caution"][:2],
        },
        "yearly_caution": {
            "available": False,
            "reason_code": "annual_rules_not_ready",
        },
        "monthly_flow": {
            "available": False,
            "reason_code": "monthly_rules_not_ready",
        },
        "relationship_support": {
            "available": False,
            "reason_code": "relationship_rules_not_ready",
        },
        "health_condition": {
            "available": False,
            "reason_code": "health_rules_not_ready",
        },
        "ideal_partner": {
            "available": False,
            "reason_code": "partner_profile_rules_not_ready",
        },
        "compatibility_compare": {
            "available": False,
            "requires_partner_payload": True,
            "reason": "상대 정보를 입력하면 두 사람의 관계 흐름을 비교할 수 있습니다.",
        },
    }


def prepare_detail_analysis_bundle(
    *,
    report_id: str,
    request_payload: SajuPreviewRequest,
    trace_id: str,
    service_name: str,
) -> Tuple[SajuDetailPreparedReport, bool]:
    input_hash = compute_detail_input_hash(request_payload)
    cache_key = (report_id, input_hash)
    cached = _get_detail_cache_item(_DETAIL_BUNDLE_CACHE, cache_key)
    if cached is not None:
        return cached, True

    preview = create_saju_preview_response(
        payload=request_payload,
        trace_id=trace_id,
        debug_requested=False,
        service_name=service_name,
        report_mode="none",
    )
    interpretation_payload = build_interpretation_payload(request=request_payload, response=preview)
    bundle = SajuDetailPreparedReport(
        report_id=report_id,
        input_hash=input_hash,
        prepared_at=datetime.now(timezone.utc).isoformat(),
        base_context=_base_context(interpretation_payload),
        detail_analysis_bundle=_detail_bundle(interpretation_payload),
    )
    _set_detail_cache_item(_DETAIL_BUNDLE_CACHE, cache_key, bundle)
    return bundle, False


def get_cached_detail_bundle(report_id: str, input_hash: str) -> SajuDetailPreparedReport | None:
    return _get_detail_cache_item(_DETAIL_BUNDLE_CACHE, (report_id, input_hash))


def _title_for(detail_type: SajuDetailType, locale: str) -> str:
    ko = {
        "love_timing": "연애운이 좋아지는 시기",
        "ideal_partner": "나와 잘 맞는 사람 유형",
        "wealth_timing": "금전 흐름이 좋아지는 시기",
        "career_timing": "이직과 커리어 전환 시기",
        "yearly_caution": "올해 조심할 흐름",
        "monthly_flow": "월별 흐름",
        "relationship_support": "인간관계와 귀인",
        "health_condition": "건강과 컨디션",
        "compatibility_compare": "상대와 궁합 비교",
    }
    en = {
        "love_timing": "Relationship timing",
        "ideal_partner": "A person who fits you well",
        "wealth_timing": "Money-flow timing",
        "career_timing": "Career transition timing",
        "yearly_caution": "What to watch this year",
        "monthly_flow": "Monthly flow",
        "relationship_support": "Helpful relationships",
        "health_condition": "Condition and rhythm",
        "compatibility_compare": "Compatibility comparison",
    }
    return (ko if locale == "ko" else en)[detail_type]


def _period_description(detail_type: SajuDetailType, item: Dict[str, object]) -> str:
    if detail_type == "love_timing":
        return "관계 기회가 늘기 쉬운 때로 보되, 확정된 만남보다 마음을 열고 대화를 늘리기 좋은 시기로 보는 편이 좋습니다."
    if detail_type == "wealth_timing":
        return "성과를 수입 구조와 연결해 보기 좋은 때입니다. 수익을 단정하기보다 빠져나가는 돈과 보상 방식을 함께 보는 것이 중요합니다."
    if detail_type == "career_timing":
        return "이직을 바로 결정하기보다 역할 조정과 전환 가능성을 검토하기 좋은 때입니다. 기존 자리에서 쌓은 성과 기록도 함께 챙기는 편이 좋습니다."
    return str(item.get("summary") or "현재 선택을 조금 더 구체적으로 나누어 보기 좋은 시기입니다.")


def _unavailable_detail_copy(detail_type: SajuDetailType, locale: str) -> Tuple[str, str, str, str]:
    if locale == "ko":
        reasons = {
            "ideal_partner": "상대 유형을 개인 맞춤 결론으로 제시할 검증된 규칙이 아직 충분하지 않습니다.",
            "yearly_caution": "연간 주의 문구를 개인화할 검증된 규칙이 아직 충분하지 않습니다.",
            "monthly_flow": "월별 시기를 개인화할 검증된 규칙이 아직 충분하지 않습니다.",
            "relationship_support": "관계 유형을 개인 맞춤으로 분류할 검증된 규칙이 아직 충분하지 않습니다.",
            "health_condition": "건강 상태로 읽힐 수 있는 판단은 이 결과에 포함하지 않습니다.",
        }
        return (
            "계산 근거가 충분하지 않아 이 항목은 현재 제공하지 않습니다.",
            reasons.get(detail_type, "선택한 항목의 계산 근거가 아직 충분하지 않습니다."),
            "검증되지 않은 규칙으로 개인화된 결론을 만들지 않습니다.",
            "현재 제공되는 사주 기둥과 큰 시기 흐름을 먼저 참고하세요.",
        )

    reasons = {
        "ideal_partner": "The validated rules needed to describe a personally fitting partner type are not ready yet.",
        "yearly_caution": "The validated rules needed to personalize annual cautions are not ready yet.",
        "monthly_flow": "The validated rules needed to personalize month-by-month timing are not ready yet.",
        "relationship_support": "The validated rules needed to classify relationship patterns are not ready yet.",
        "health_condition": "This result does not include judgments that could be read as health conditions.",
    }
    return (
        "This item is not shown because its calculation basis is not sufficient yet.",
        reasons.get(detail_type, "The calculation basis for this selected item is not sufficient yet."),
        "The result does not create personalized conclusions from unvalidated rules.",
        "Use the displayed pillars and broader timing context first.",
    )


def build_fallback_detail_render(
    detail_type: SajuDetailType,
    detail_payload: Dict[str, object],
    *,
    locale: str = "ko",
) -> SajuDetailRenderedReport:
    title = _title_for(detail_type, locale)
    if detail_type == "compatibility_compare":
        return SajuDetailRenderedReport(
            detail_type=detail_type,
            title=title,
            summary="상대 정보가 있어야 두 사람의 관계 흐름을 비교할 수 있습니다.",
            body=SajuDetailBody(
                conclusion="이 항목은 내 사주만으로 단정해서 비교하지 않습니다. 상대의 생년월일, 출생시간, 성별, 출생지역을 입력하면 두 사람의 관계 리듬을 따로 비교할 수 있습니다.",
                periods=[],
                cautions=["상대 정보 없이 실제 궁합 결과를 만들지 않습니다."],
                advice=["비교를 원할 때는 상대 정보를 입력하는 별도 흐름에서 확인하세요."],
                basis_chips=["상대 정보 필요", "별도 비교"],
            ),
        )

    if not detail_payload.get("available", False):
        summary, conclusion, caution, advice = _unavailable_detail_copy(detail_type, locale)
        return SajuDetailRenderedReport(
            detail_type=detail_type,
            title=title,
            summary=summary,
            body=SajuDetailBody(
                conclusion=conclusion,
                periods=[],
                cautions=[caution],
                advice=[advice],
                basis_chips=["계산 근거 검토 중"] if locale == "ko" else ["Calculation basis under review"],
            ),
        )

    periods_source = (
        detail_payload.get("best_periods")
        or detail_payload.get("move_review_periods")
        or detail_payload.get("caution_periods")
        or []
    )
    periods = [
        SajuDetailPeriod(
            label="살펴볼 시기",
            period=str(item.get("period", "확인 가능한 시기")),
            description=_period_description(detail_type, item),
        )
        for item in periods_source[:3]
        if isinstance(item, dict)
    ]
    if not periods:
        periods = [
            SajuDetailPeriod(
                label="살펴볼 시기",
                period="현재 확인 가능한 시기",
                description="지금의 선택을 조금 더 구체적으로 나누어 보면 다음 행동이 덜 무거워질 수 있습니다.",
            )
        ]

    summary_by_type = {
        "love_timing": "관계 기회가 늘기 쉬운 시기와 조심할 시기를 함께 봅니다.",
        "wealth_timing": "돈 흐름을 만들기 좋은 때와 지출 관리가 필요한 때를 함께 봅니다.",
        "career_timing": "움직임을 검토하기 좋은 때와 보수적으로 봐야 할 때를 나눠 봅니다.",
    }
    conclusion_by_type = {
        "love_timing": "관계운은 확정된 사건보다 마음을 열기 쉬운 조건과 거리 조절이 중요합니다. 좋은 시기일수록 빠른 결론보다 대화의 반복성과 생활 태도를 같이 보는 편이 좋습니다.",
        "wealth_timing": "돈 흐름은 많이 들어오는지만 보지 말고 어디서 새는지도 함께 봐야 합니다. 성과를 보상과 연결하고 관계성 지출을 줄이는 감각이 중요합니다.",
        "career_timing": "커리어 전환은 바로 움직이라는 뜻보다 역할과 보상의 균형을 점검하라는 신호에 가깝습니다. 지금 자리에서 조정할 것과 밖에서 찾아야 할 것을 나눠 보는 것이 좋습니다.",
    }
    basis_by_type = {
        "love_timing": ["큰 시기 분석", "관계 신호", "배우자궁"],
        "wealth_timing": ["큰 시기 분석", "금전 관련 십성", "관리 포인트"],
        "career_timing": ["큰 시기 분석", "직업 관련 십성", "역할 변화"],
    }
    return SajuDetailRenderedReport(
        detail_type=detail_type,
        title=title,
        summary=summary_by_type.get(detail_type, "추가로 살펴볼 흐름을 정리합니다."),
        body=SajuDetailBody(
            conclusion=conclusion_by_type.get(detail_type, "현재 선택을 더 구체적으로 나누어 보는 것이 좋습니다."),
            periods=periods,
            cautions=[
                "확정된 사건처럼 받아들이기보다 선택을 조정하는 참고점으로 보세요.",
                "피로가 커지는 선택은 시기가 좋아 보여도 속도를 늦추는 편이 좋습니다.",
            ],
            advice=[
                "지금 바로 크게 바꾸기보다, 반복해서 무거워지는 부분을 먼저 줄여 보세요.",
                "관계, 일, 돈 중 하나를 정하면 나머지도 같은 날 한꺼번에 결정하지 않는 편이 좋습니다.",
            ],
            basis_chips=basis_by_type.get(detail_type, ["계산 근거", "현재 흐름"]),
        ),
    )


def _collect_report_text(report: SajuDetailRenderedReport) -> str:
    chunks = [report.title, report.summary, report.body.conclusion]
    chunks.extend(period.description for period in report.body.periods)
    chunks.extend(report.body.cautions)
    chunks.extend(report.body.advice)
    chunks.extend(report.body.basis_chips)
    return "\n".join(chunks)


def _validate_rendered_report(report: SajuDetailRenderedReport) -> List[str]:
    text = _collect_report_text(report)
    issues = [f"forbidden:{term}" for term in FORBIDDEN_USER_TEXT if term in text]
    if re.search(r"[\u3400-\u9fff]", text):
        issues.append("hanja_exposed")
    return issues


def _call_openai_detail_render(
    detail_type: SajuDetailType,
    detail_payload: Dict[str, object],
    *,
    locale: str,
) -> SajuDetailRenderedReport | None:
    if settings.llm_provider != "openai":
        return None
    if OpenAI is None:
        return None
    if settings.openai_api_key in {"", PLACEHOLDER_OPENAI_API_KEY}:
        return None

    client = OpenAI(
        api_key=settings.openai_api_key,
        timeout=settings.llm_timeout_seconds,
        max_retries=0,
    )
    output_text = ""
    try:
        response = client.responses.create(
            model=settings.openai_model,
            reasoning={"effort": settings.llm_reasoning_effort},
            store=settings.llm_store,
            max_output_tokens=min(max(settings.llm_max_output_tokens, 1200), 2400),
            input=[
                {"role": "developer", "content": DETAIL_RENDER_DEVELOPER_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "detail_type": detail_type,
                            "locale": locale,
                            "detail_payload": detail_payload,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            text={
                "format": _make_openai_json_schema_strict(
                    "saju_detail_render",
                    _model_json_schema(SajuDetailRenderedReport),
                )
            },
        )
        output_text = getattr(response, "output_text", "") or ""
        parsed_json = json.loads(output_text)
        report = model_validate_compat(SajuDetailRenderedReport, parsed_json)
        if report.detail_type != detail_type:
            return None
        if _validate_rendered_report(report):
            return None
        return report
    except (JSONDecodeError, ValidationError, Exception):
        return None


def _call_codex_detail_render(
    detail_type: SajuDetailType,
    detail_payload: Dict[str, object],
    *,
    locale: str,
) -> SajuDetailRenderedReport | None:
    if settings.llm_provider != "codex":
        return None

    try:
        result = call_codex_json(
            developer_prompt=DETAIL_RENDER_DEVELOPER_PROMPT,
            user_payload={
                "detail_type": detail_type,
                "locale": locale,
                "detail_payload": detail_payload,
            },
            output_schema=_model_json_schema(SajuDetailRenderedReport),
            schema_name="saju_detail_render",
            extra_instructions=(
                "Use only the supplied detail_payload facts.",
                "Return one SajuDetailRenderedReport JSON object for the requested detail_type.",
            ),
        )
        parsed_json = json.loads(result.output_text)
        report = model_validate_compat(SajuDetailRenderedReport, parsed_json)
        if report.detail_type != detail_type:
            return None
        if _validate_rendered_report(report):
            return None
        return report
    except (CodexProviderError, JSONDecodeError, ValidationError, Exception):
        return None


def render_detail_insight(
    *,
    report_id: str,
    input_hash: str,
    detail_type: SajuDetailType,
    locale: str,
    bundle: SajuDetailPreparedReport,
) -> Tuple[SajuDetailRenderedReport, bool, str]:
    cache_key = (report_id, input_hash, detail_type, locale)
    cached = _get_detail_cache_item(_DETAIL_RENDER_CACHE, cache_key)
    if cached is not None:
        cached_report, cached_provider = cached
        return cached_report, True, cached_provider

    detail_payload = bundle.detail_analysis_bundle.get(detail_type)
    if detail_payload is None:
        detail_payload = {
            "available": False,
            "reason": "해당 상세 항목을 준비하지 못했습니다.",
        }

    started = time.perf_counter()
    if not detail_payload.get("available", False):
        report = build_fallback_detail_render(detail_type, detail_payload, locale=locale)
        provider = "fallback"
    else:
        if settings.llm_provider == "codex":
            report = _call_codex_detail_render(detail_type, detail_payload, locale=locale)
            provider = "codex" if report is not None else "fallback"
        else:
            report = _call_openai_detail_render(detail_type, detail_payload, locale=locale)
            provider = "openai" if report is not None else "fallback"
        if report is None:
            report = build_fallback_detail_render(detail_type, detail_payload, locale=locale)

    issues = _validate_rendered_report(report)
    if issues:
        report = build_fallback_detail_render(detail_type, detail_payload, locale=locale)
        provider = "fallback"

    _ = int((time.perf_counter() - started) * 1000)
    _set_detail_cache_item(_DETAIL_RENDER_CACHE, cache_key, (report, provider))
    return report, False, provider
