"""Prepare and render section-level expandable saju insight details."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from json import JSONDecodeError
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
from app.domain.saju.services.build_interpretation_payload import build_interpretation_payload
from app.domain.saju.services.preview_orchestrator import create_saju_preview_response

try:  # pragma: no cover - optional in local fallback test envs.
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


DETAIL_PROMPT_VERSION = "saju-detail-render-v1"
DETAIL_TYPES: Tuple[SajuDetailType, ...] = (
    "love_timing",
    "ideal_partner",
    "wealth_timing",
    "career_timing",
    "yearly_caution",
    "monthly_flow",
    "relationship_support",
    "health_condition",
    "compatibility_compare",
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

_DETAIL_BUNDLE_CACHE: Dict[Tuple[str, str], SajuDetailPreparedReport] = {}
_DETAIL_RENDER_CACHE: Dict[Tuple[str, str, str, str], Tuple[SajuDetailRenderedReport, str]] = {}


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
- health_condition must discuss lifestyle rhythm, fatigue, recovery, sleep, and conditioning only; no disease names or medical judgment.
- compatibility_compare must not compare compatibility when partner facts are unavailable.
- Keep the result short enough for an inline expanded panel.
- Return valid JSON only.
""".strip()


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


def _month_flows(payload: InterpretationPayload) -> List[Dict[str, object]]:
    year = payload.current_flow.current_year
    action_tags = payload.luck_flow_facts.now_action_tags[:3] or ["생활 리듬 점검"]
    flows: List[Dict[str, object]] = []
    for month in range(1, 13):
        impact = "neutral"
        if month in {3, 6, 9, 12}:
            impact = "caution"
        if month in {2, 5, 8, 11}:
            impact = "positive"
        flows.append(
            {
                "year_month": f"{year}-{month:02d}",
                "love_impact": impact if month in {2, 6, 10} else "neutral",
                "career_impact": impact if month in {3, 7, 11} else "neutral",
                "wealth_impact": impact if month in {4, 8, 12} else "neutral",
                "best_for": action_tags,
                "caution": "일정과 감정 소모를 함께 살피는 달입니다." if impact == "caution" else "",
                "summary": "실행 속도보다 지속 가능한 리듬을 우선해서 보면 좋습니다.",
            }
        )
    return flows


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
    current_year = payload.current_flow.current_year
    special_stars = [
        {
            "key": star.key,
            "label": star.display_label,
            "category": star.category,
            "usage_summary": star.usage_summary,
        }
        for star in payload.special_stars[:8]
    ]
    relationship_tags = [star.display_label for star in payload.special_stars[:4]]
    now_tags = payload.luck_flow_facts.now_action_tags[:5]

    return {
        "love_timing": {
            "available": True,
            "basis": {
                "annual_flows": _analysis_periods(payload, "love"),
                "monthly_flows": _month_flows(payload),
                "partner_star_activated_years": payload.love_facts.active_star_labels,
                "spouse_house_relations": [payload.love_facts.spouse_house_label],
            },
            "best_periods": _analysis_periods(payload, "love")[:2],
            "caution_periods": [period for period in _analysis_periods(payload, "relationship") if period["impact"] == "caution"][:2],
            "summary_tags": ["관계 기회", "마음 열기", "거리 조절"],
        },
        "ideal_partner": {
            "available": True,
            "basis": {
                "day_master": payload.day_master,
                "spouse_house": {
                    "label": payload.love_facts.spouse_house_label,
                    "branch": payload.love_facts.spouse_house_branch,
                    "ten_god": payload.love_facts.spouse_house_ten_god,
                },
                "partner_star": {
                    "label": payload.love_facts.partner_star_label,
                    "count": payload.love_facts.partner_star_count,
                },
                "element_balance": dict(payload.element_counts),
                "missing_elements": payload.signals.missing_elements,
                "ten_gods": dict(payload.ten_god_stems),
            },
            "good_match_traits": ["약속을 꾸준히 지키는 사람", "감정 표현보다 생활 태도가 안정적인 사람", "서로의 시간을 존중하는 사람"],
            "difficult_match_traits": ["역할을 흐리게 넘기는 사람", "말은 빠르지만 반복 태도가 바뀌는 사람"],
            "relationship_advice_tags": ["생활 리듬", "책임 분담", "천천히 신뢰 쌓기"],
        },
        "wealth_timing": {
            "available": True,
            "basis": {
                "annual_flows": _analysis_periods(payload, "wealth"),
                "monthly_flows": _month_flows(payload),
                "wealth_star_activated_years": [item.label for item in payload.wealth_facts.key_ten_gods],
                "output_to_wealth_flow_periods": _analysis_periods(payload, "wealth")[:2],
                "peer_leakage_risk_periods": _analysis_periods(payload, "relationship")[:2],
            },
            "best_periods": _analysis_periods(payload, "wealth")[:2],
            "caution_periods": [period for period in _analysis_periods(payload, "wealth") if period["impact"] == "caution"][:2],
            "management_tags": ["지출 누수 점검", "성과와 보상 연결", "관계 지출 경계"],
        },
        "career_timing": {
            "available": True,
            "basis": {
                "career_facts": model_to_dict(payload.career_facts, mode="json"),
                "current_flow": model_to_dict(payload.current_flow, mode="json"),
                "annual_flows": _analysis_periods(payload, "career"),
                "monthly_flows": _month_flows(payload),
            },
            "move_review_periods": _analysis_periods(payload, "career")[:2],
            "stabilize_periods": _analysis_periods(payload, "career")[2:4],
            "caution_periods": [period for period in _analysis_periods(payload, "career") if period["impact"] == "caution"][:2],
            "strategy_tags": ["역할 조정", "일정 과부하 점검", "성과 기록"],
        },
        "yearly_caution": {
            "available": True,
            "year": current_year,
            "basis": {
                "current_year_flow": model_to_dict(payload.current_flow, mode="json"),
                "relations_to_base_chart": now_tags,
            },
            "love_caution": ["기대와 거리감의 속도를 맞추기"],
            "career_caution": ["맡는 범위가 애매한 일을 오래 끌지 않기"],
            "wealth_caution": ["관계나 급한 결정으로 새는 지출 살피기"],
            "relationship_caution": ["괜찮다고 넘긴 피로를 뒤늦게 폭발시키지 않기"],
            "overall_advice_tags": now_tags or ["생활 리듬", "지출 점검", "관계 거리"],
        },
        "monthly_flow": {
            "available": True,
            "months": _month_flows(payload),
        },
        "relationship_support": {
            "available": True,
            "basis": {
                "peer": {"visible_distribution": dict(payload.ten_god_stems)},
                "resource": {"support_need": payload.signals.missing_elements},
                "officer": {"career_signal": payload.career_facts.month_stem_ten_god},
                "special_stars": special_stars,
            },
            "helpful_people_traits": ["약속을 지키는 사람", "감정 소모보다 실질적 도움을 주는 사람", "경계를 존중하는 사람"],
            "tiring_people_traits": ["책임을 떠넘기는 사람", "말을 자주 바꾸는 사람", "관계를 급하게 몰아가는 사람"],
            "relationship_strategy_tags": relationship_tags or ["관계 거리 조절", "도움 요청"],
        },
        "health_condition": {
            "available": True,
            "basis": {
                "element_balance": dict(payload.element_counts),
                "dominant_elements": payload.signals.dominant_elements,
                "missing_elements": payload.signals.missing_elements,
                "current_flow_pressure_tags": now_tags,
            },
            "condition_rhythm_tags": ["수면 리듬", "과로 신호", "회복 루틴"],
            "caution_tags": ["무리한 일정", "감정 소모", "쉬어도 쉰 것 같지 않은 패턴"],
            "care_advice_tags": ["일정 줄이기", "수면 시간 고정", "가벼운 반복 루틴"],
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
    cached = _DETAIL_BUNDLE_CACHE.get(cache_key)
    if cached is not None:
        return cached, True

    preview = create_saju_preview_response(
        payload=request_payload,
        trace_id=trace_id,
        debug_requested=request_payload.debug,
        service_name=service_name,
        render_reports=False,
    )
    interpretation_payload = build_interpretation_payload(request=request_payload, response=preview)
    bundle = SajuDetailPreparedReport(
        report_id=report_id,
        input_hash=input_hash,
        prepared_at=datetime.now(timezone.utc).isoformat(),
        base_context=_base_context(interpretation_payload),
        detail_analysis_bundle=_detail_bundle(interpretation_payload),
    )
    _DETAIL_BUNDLE_CACHE[cache_key] = bundle
    return bundle, False


def get_cached_detail_bundle(report_id: str, input_hash: str) -> SajuDetailPreparedReport | None:
    return _DETAIL_BUNDLE_CACHE.get((report_id, input_hash))


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

    if detail_type == "monthly_flow":
        months = list(detail_payload.get("months", []))[:6]
        periods = [
            SajuDetailPeriod(
                label="월별 실행 포인트",
                period=str(month.get("year_month", "")),
                description=str(month.get("summary", "")) or "월별로 실행하기 좋은 방향과 조심할 부분을 함께 봅니다.",
            )
            for month in months
            if isinstance(month, dict)
        ]
        return SajuDetailRenderedReport(
            detail_type=detail_type,
            title=title,
            summary="모든 달을 길게 늘어놓기보다 체감하기 쉬운 실행 타이밍을 먼저 봅니다.",
            body=SajuDetailBody(
                conclusion="월별 흐름은 좋고 나쁨을 확정하는 표가 아니라, 어떤 달에 무엇을 가볍게 조정하면 좋은지 보는 기준입니다. 일정, 관계, 지출을 한꺼번에 밀어붙이지 않는 것이 핵심입니다.",
                periods=periods,
                cautions=["흐름이 강한 달에는 결정을 서두르기보다 일정과 감정 소모를 같이 보세요."],
                advice=["중요한 선택은 한 번에 몰아서 처리하지 말고, 준비와 실행을 나누어 보세요."],
                basis_chips=["월운", "실행 타이밍", "생활 리듬"],
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
        "ideal_partner": "함께 있을 때 덜 소모되고 생활 리듬이 맞기 쉬운 사람의 특징을 봅니다.",
        "wealth_timing": "돈 흐름을 만들기 좋은 때와 지출 관리가 필요한 때를 함께 봅니다.",
        "career_timing": "움직임을 검토하기 좋은 때와 보수적으로 봐야 할 때를 나눠 봅니다.",
        "yearly_caution": "올해 관계, 일, 돈에서 과부하가 생기기 쉬운 지점을 봅니다.",
        "relationship_support": "도움이 되는 사람과 피로해지기 쉬운 관계 패턴을 봅니다.",
        "health_condition": "생활 리듬과 회복 관점에서 컨디션 관리 포인트를 봅니다.",
    }
    conclusion_by_type = {
        "love_timing": "관계운은 확정된 사건보다 마음을 열기 쉬운 조건과 거리 조절이 중요합니다. 좋은 시기일수록 빠른 결론보다 대화의 반복성과 생활 태도를 같이 보는 편이 좋습니다.",
        "ideal_partner": "잘 맞는 사람은 강한 설렘만 주는 사람보다 함께 있을 때 생활이 덜 흔들리는 사람에 가깝습니다. 약속을 지키고 서로의 회복 시간을 존중하는 태도가 오래 남습니다.",
        "wealth_timing": "돈 흐름은 많이 들어오는지만 보지 말고 어디서 새는지도 함께 봐야 합니다. 성과를 보상과 연결하고 관계성 지출을 줄이는 감각이 중요합니다.",
        "career_timing": "커리어 전환은 바로 움직이라는 뜻보다 역할과 보상의 균형을 점검하라는 신호에 가깝습니다. 지금 자리에서 조정할 것과 밖에서 찾아야 할 것을 나눠 보는 것이 좋습니다.",
        "yearly_caution": "올해 조심할 지점은 극단적인 사건보다 피로가 쌓이는 방식입니다. 관계, 일정, 지출을 동시에 키우면 체감 부담이 커질 수 있습니다.",
        "relationship_support": "도움이 되는 사람은 나를 급하게 몰아붙이기보다 현실적인 도움과 안정된 태도를 주는 사람입니다. 반대로 책임을 흐리게 넘기는 관계는 빨리 피로해질 수 있습니다.",
        "health_condition": "컨디션은 특정 문제를 단정하기보다 생활 리듬과 회복 속도로 보는 편이 좋습니다. 쉬어도 회복감이 적다면 일정과 수면 루틴을 먼저 가볍게 만드는 것이 도움이 됩니다.",
    }
    basis_by_type = {
        "love_timing": ["세운", "월운", "관계 신호"],
        "ideal_partner": ["관계 성향", "오행 균형", "생활 리듬"],
        "wealth_timing": ["재물 신호", "성과 연결", "지출 관리"],
        "career_timing": ["직장운", "역할 변화", "현재 흐름"],
        "yearly_caution": ["올해 흐름", "관계", "일", "돈"],
        "relationship_support": ["귀인", "관계 패턴", "보조 신호"],
        "health_condition": ["오행 균형", "회복 루틴", "생활 리듬"],
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

    client = OpenAI(api_key=settings.openai_api_key)
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


def render_detail_insight(
    *,
    report_id: str,
    input_hash: str,
    detail_type: SajuDetailType,
    locale: str,
    bundle: SajuDetailPreparedReport,
) -> Tuple[SajuDetailRenderedReport, bool, str]:
    cache_key = (report_id, input_hash, detail_type, locale)
    cached = _DETAIL_RENDER_CACHE.get(cache_key)
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
    report = _call_openai_detail_render(detail_type, detail_payload, locale=locale)
    provider = "openai" if report is not None else "fallback"
    if report is None:
        report = build_fallback_detail_render(detail_type, detail_payload, locale=locale)

    issues = _validate_rendered_report(report)
    if issues:
        report = build_fallback_detail_render(detail_type, detail_payload, locale=locale)
        provider = "fallback"

    _ = int((time.perf_counter() - started) * 1000)
    _DETAIL_RENDER_CACHE[cache_key] = (report, provider)
    return report, False, provider
