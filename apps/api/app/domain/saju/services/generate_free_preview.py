"""Free first-screen saju preview report generation."""

from __future__ import annotations

import json
import re
import time
from json import JSONDecodeError
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from pydantic import ValidationError

from app.config import PLACEHOLDER_OPENAI_API_KEY, settings
from app.diagnostics import log_stage
from app.domain.saju.interpretation import (
    FreePreviewCard,
    FreePreviewDiagnosis,
    FreePreviewLLMOutput,
    FreePreviewReport,
    InterpretationAttemptDiagnostic,
    InterpretationDiagnostics,
    ReadingBasisExplanation,
)
from app.domain.saju.llm_payload import InterpretationPayload
from app.domain.saju.localization import TEN_GOD_ENGLISH, contains_hangul, contains_hanja, localize_ten_god
from app.domain.saju.prompts.free_preview_report import get_free_preview_report_prompt
from app.domain.saju.services.codex_provider import CodexProviderError, call_codex_json
from app.domain.saju.services.build_reading_plan import apply_reading_plan, build_reading_plan, unsupported_claim_issues, validate_reading_structure

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - import guard for local test envs
    OpenAI = None


PROMPT_SPEC = get_free_preview_report_prompt()
MIN_HERO_SENTENCES = 7
MAX_HERO_SENTENCES = 9
MIN_CARD_PREVIEW_CHARS = 120
MAX_CARD_PREVIEW_CHARS = 1400
OUTPUT_EXCERPT_LIMIT = 280
ERROR_MESSAGE_LIMIT = 280
SCHEMA_NOISE_KEYS = {
    "default",
    "examples",
    "minLength",
    "maxLength",
    "pattern",
    "format",
    "minimum",
    "maximum",
    "multipleOf",
    "minItems",
    "maxItems",
}
CARD_KEYS = ("core", "work_money", "love", "luck_flow")
DIAGNOSIS_KEYS = ("strongest_point", "repeating_pattern", "current_task")
INTERNAL_VALUE_PATTERNS = (
    r"\bbalance_score\b",
    r"\binternal_grade\b",
    r"\bevidence_id\b",
    r"\braw\s+evidence\b",
    r"\bscore\s*:",
    r"\bscore\b",
    r"점수\s*:",
    r"등급\s*:",
    r"(?:100|90|80|70|60|50)\s*점",
    r"100%",
)
PLACEHOLDER_USER_PHRASES = (
    "없음 쪽",
    "없음 기운",
    "확인 대기 구간",
)


def _model_dump_json(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return json.loads(model.json())


def _model_copy(model: Any, *, update: Dict[str, Any]) -> Any:
    if hasattr(model, "model_copy"):
        return model.model_copy(update=update)
    return model.copy(update=update, deep=True)


def _model_validate(model_class: Any, data: Dict[str, Any]) -> Any:
    if hasattr(model_class, "model_validate"):
        return model_class.model_validate(data)
    return model_class.parse_obj(data)


def _model_json_schema(model_class: Any) -> Dict[str, Any]:
    if hasattr(model_class, "model_json_schema"):
        return model_class.model_json_schema()
    return model_class.schema()


def _make_openai_json_schema_strict(name: str, schema: Dict[str, Any]) -> Dict[str, Any]:
    strict_schema = json.loads(json.dumps(schema))

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            for key in list(node.keys()):
                if key in SCHEMA_NOISE_KEYS:
                    node.pop(key, None)
            if node.get("type") == "object":
                node["additionalProperties"] = False
                if "properties" in node:
                    node["required"] = list(node["properties"].keys())
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(strict_schema)
    return {"type": "json_schema", "name": name, "strict": True, "schema": strict_schema}


def _clean_excerpt(text: str, *, limit: int = OUTPUT_EXCERPT_LIMIT) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    return compact[:limit]


def _clean_error_message(error: Exception | str) -> str:
    message = str(error)
    return re.sub(r"\s+", " ", message).strip()[:ERROR_MESSAGE_LIMIT]


def _make_diagnostics(
    *,
    final_provider: str,
    payload_json: str,
    duration_ms: int = 0,
    attempts: Sequence[InterpretationAttemptDiagnostic] | None = None,
    final_response_id: str | None = None,
    fallback_reason: str | None = None,
    validation_issues: Sequence[str] | None = None,
) -> InterpretationDiagnostics:
    return InterpretationDiagnostics(
        configured_provider=settings.llm_provider,
        final_provider=final_provider,  # type: ignore[arg-type]
        model=_provider_model(final_provider),
        prompt_version=PROMPT_SPEC.version,
        payload_chars=len(payload_json),
        duration_ms=duration_ms,
        final_response_id=final_response_id,
        fallback_reason=fallback_reason,
        validation_issues=list(validation_issues or []),
        attempts=list(attempts or []),
    )


def _provider_model(provider: str) -> str | None:
    if provider == "openai":
        return settings.openai_model
    if provider == "codex":
        return settings.codex_model or "codex-cli"
    return None


def _attach_diagnostics(
    report: FreePreviewReport,
    diagnostics: InterpretationDiagnostics,
    *,
    provider: str,
    warnings: Sequence[str] | None = None,
) -> FreePreviewReport:
    return _model_copy(
        report,
        update={
            "provider": provider,
            "model": _provider_model(provider) or "fallback",
            "prompt_version": PROMPT_SPEC.version,
            "warnings": list(dict.fromkeys([*report.warnings, *(warnings or [])])),
            "diagnostics": diagnostics,
            "cards": report.cards if provider == "fallback" else [
                _model_copy(card, update={"basis_explanation": None, "reading_structure": None}) for card in report.cards
            ],
        },
    )


def _locale(payload: InterpretationPayload) -> str:
    return payload.profile.locale


def _is_ko(payload: InterpretationPayload) -> bool:
    return _locale(payload) == "ko"


def _join(items: Iterable[str], *, fallback: str) -> str:
    values = [item for item in items if item]
    return ", ".join(values) if values else fallback


def _element_text(payload: InterpretationPayload) -> str:
    labels = {
        "ko": {"wood": "목", "fire": "화", "earth": "토", "metal": "금", "water": "수"},
        "en": {
            "wood": "wood",
            "fire": "fire",
            "earth": "earth",
            "metal": "metal",
            "water": "water",
        },
    }[_locale(payload)]
    return _join((labels.get(item, item) for item in payload.signals.dominant_elements), fallback="없음" if _is_ko(payload) else "none")


def _missing_element_text(payload: InterpretationPayload) -> str:
    labels = {
        "ko": {"wood": "목", "fire": "화", "earth": "토", "metal": "금", "water": "수"},
        "en": {
            "wood": "wood",
            "fire": "fire",
            "earth": "earth",
            "metal": "metal",
            "water": "water",
        },
    }[_locale(payload)]
    return _join((labels.get(item, item) for item in payload.signals.missing_elements), fallback="두드러진 공백 없음" if _is_ko(payload) else "no clear gap")


def _cycle_name(payload: InterpretationPayload, which: str) -> str:
    facts = payload.luck_flow_facts
    cycle = facts.current_luck_cycle if which == "current" else facts.next_luck_cycle
    if cycle:
        return cycle
    source = payload.current_flow.active_luck_cycle if which == "current" else payload.current_flow.next_luck_cycle
    if source:
        return source.display_gan_zhi
    return "현재 구간" if _is_ko(payload) else "the current cycle"


def _period_text(payload: InterpretationPayload, which: str) -> str:
    facts = payload.luck_flow_facts
    period = facts.current_period if which == "current" else facts.next_period
    return period or ("확인 가능한 구간" if _is_ko(payload) else "the available period")


def _star_text(payload: InterpretationPayload, labels: Sequence[str]) -> str:
    if labels:
        return _join(labels[:3], fallback="")
    return "뚜렷한 보조 신호는 적은 편" if _is_ko(payload) else "few strong auxiliary signals"


def _has_confirmed_current_cycle(payload: InterpretationPayload) -> bool:
    return (
        not payload.profile.is_birth_time_estimated
        and "luck_cycles" not in payload.disabled_sections
        and not any(item.key == "luck_cycles" and item.status == "disabled" for item in payload.evidence)
        and payload.current_flow.active_luck_cycle is not None
    )


def _confirmed_action_tags(payload: InterpretationPayload) -> List[str]:
    if not _has_confirmed_current_cycle(payload):
        return []
    return payload.luck_flow_facts.now_action_tags


def _dominant_strength_phrase(payload: InterpretationPayload) -> str:
    phrases = ({
        "wood": "유연하게 넓히고 가능성을 찾아가는 힘",
        "fire": "빠르게 반응하고 표현하는 힘",
        "earth": "현실을 붙잡고 안정적으로 정리하는 힘",
        "metal": "필요한 것과 아닌 것을 골라내는 힘",
        "water": "상황을 읽고 조율하는 힘",
    } if _is_ko(payload) else {
        "wood": "exploring possibilities and adapting",
        "fire": "responding and expressing ideas",
        "earth": "stabilizing practical tasks",
        "metal": "separating essentials and finishing tasks",
        "water": "reading situations and coordinating",
    })
    values = [
        phrases[item]
        for item in payload.signals.dominant_elements
        if item in phrases
    ]
    return _join(values[:2], fallback="상황을 살피고 필요한 일을 구분하는 힘" if _is_ko(payload) else "reviewing situations and practical tasks")


def _support_need_phrase(payload: InterpretationPayload) -> str:
    phrases = ({
        "wood": "유연하게 넓히는 힘",
        "fire": "표현하고 활기를 되살리는 힘",
        "earth": "생활을 안정시키고 중심을 잡는 힘",
        "metal": "경계를 세우고 끝맺는 힘",
        "water": "상황을 읽고 조율하는 힘",
    } if _is_ko(payload) else {
        "wood": "adaptability and exploration",
        "fire": "expression and renewed energy",
        "earth": "a steady daily rhythm",
        "metal": "boundaries and completion",
        "water": "reflection and coordination",
    })
    values = [
        phrases[item]
        for item in payload.signals.missing_elements
        if item in phrases
    ]
    return _join(values[:2], fallback="회복 루틴과 주변 환경" if _is_ko(payload) else "recovery routines and the surrounding environment")


def _headline_ko(payload: InterpretationPayload) -> str:
    headlines = {
        "wood": "가능성을 넓히며 방향을 찾는 사람",
        "fire": "반응과 표현에서 힘이 살아나는 사람",
        "earth": "현실을 붙잡고 중심을 세우는 사람",
        "metal": "기준을 세우고 핵심을 가르는 사람",
        "water": "상황을 읽고 흐름을 조율하는 사람",
    }
    for element in payload.signals.dominant_elements:
        if element in headlines:
            return headlines[element]
    return "나에게 맞는 방식을 찾아가는 사람"


def _diagnoses_ko(payload: InterpretationPayload) -> List[FreePreviewDiagnosis]:
    strength = _dominant_strength_phrase(payload)
    support_need = _support_need_phrase(payload)
    now_actions = _join(
        _confirmed_action_tags(payload)[:3],
        fallback="생활 리듬과 주변 환경을 정리하기",
    )
    return [
        FreePreviewDiagnosis(
            key="strongest_point",
            title="가장 강한 점",
            body=(
                f"급한 상황에서도 {strength}이 잘 살아납니다. "
                "해야 할 일과 미뤄도 되는 일을 빠르게 가르기 때문에, 주변이 어수선할수록 오히려 존재감이 커질 수 있습니다."
            ),
        ),
        FreePreviewDiagnosis(
            key="repeating_pattern",
            title="반복되는 패턴",
            body=(
                f"반복되는 패턴은 혼자 먼저 감당하다가 {support_need}이 늦어질 때 피로가 쌓인다는 점입니다. "
                "일, 돈, 관계 문제가 한꺼번에 섞이면 판단이 급해질 수 있어 처음부터 맡을 범위를 작게 나누는 편이 좋습니다."
            ),
        ),
        FreePreviewDiagnosis(
            key="current_task",
            title="지금 시기 과제",
            body=(
                f"지금은 {now_actions}처럼 현재 흐름에서 제시된 행동을 작게 반복하는 일이 중요합니다. "
                "한 번에 크게 바꾸기보다 생활 리듬, 돈 쓰는 습관, 사람을 대하는 거리를 조금씩 정리하면 다음 선택 앞에서 덜 흔들릴 수 있습니다."
            ),
        ),
    ]


def _diagnoses_en(payload: InterpretationPayload) -> List[FreePreviewDiagnosis]:
    current_cycle = _cycle_name(payload, "current")
    confirmed_timing = _has_confirmed_current_cycle(payload)
    return [
        FreePreviewDiagnosis(
            key="strongest_point",
            title="Strongest point",
            body=(
                f"With {payload.day_master} as the day master, the chart responds strongly through {_element_text(payload)}. "
                "When the person has clear standards, priorities become easier to separate and action becomes steadier."
            ),
        ),
        FreePreviewDiagnosis(
            key="repeating_pattern",
            title="Repeating pattern",
            body=(
                f"The repeating pattern is that strengths move quickly while the {_missing_element_text(payload)} side needs conscious support. "
                "Work, money, and relationship decisions become easier when they are not mixed into one urgent choice."
            ),
        ),
        FreePreviewDiagnosis(
            key="current_task",
            title="Current task",
            body=(
                (f"The supplied current period is {current_cycle}; use the provided action points to review choices rather than expand everything at once. "
                 if confirmed_timing else "Current timing is unconfirmed, so review observable daily habits without assigning them to a luck-cycle period. ")
                + "Observable routines can help you check which choices are sustainable."
            ),
        ),
    ]


def _cards_ko(payload: InterpretationPayload) -> List[FreePreviewCard]:
    now_actions = _join(_confirmed_action_tags(payload)[:4], fallback="관계 거리 조절, 지출 점검, 생활 루틴")
    strength = _dominant_strength_phrase(payload)
    support_need = _support_need_phrase(payload)
    limitation = (
        "출생시간이 추정값이라 시간에 따라 달라지는 세부 판단은 조금 보수적으로 보는 편이 좋습니다. "
        if payload.profile.is_birth_time_estimated
        else ""
    )
    return [
        FreePreviewCard(
            key="core",
            title="강점이 잘 살아나는 조건은?",
            subtitle="역할과 회복 리듬을 함께 보는 법",
            chips=["강점의 방향", "책임 범위", "피로 신호", "생활 리듬"],
            preview_paragraphs=[
                f"이 결과에서 먼저 보는 강점은 {strength}입니다. 실제 생활에서는 해야 할 일과 미뤄도 되는 일을 가르는 방식, 책임을 정리하는 방식, 익숙한 문제를 다루는 방식에서 이 강점이 드러날 수 있습니다.",
                "강점은 역할과 우선순위가 분명할 때 더 안정적으로 쓰입니다. 반대로 해야 할 일의 범위가 계속 바뀌거나 한 사람이 모든 결정을 떠안으면, 잘해내는 힘이 피로로 바뀌는지 함께 살피는 편이 좋습니다.",
                f"보완 포인트는 {support_need}입니다. {limitation}무리한 요청이 쌓일 때는 참는 양을 늘리기보다, 맡을 범위와 쉬는 시간을 먼저 조정하는 편이 현실적입니다.",
                "지금 살펴볼 포인트는 내가 편해지는 자리와 금방 소모되는 자리를 구분하는 것입니다. 잘하는 방식과 계속 버티게 되는 방식을 나누면 같은 노력도 덜 무겁게 이어지고, 관계와 일에서 스스로를 과하게 몰아붙이는 선택도 줄일 수 있습니다. 필요한 도움을 먼저 요청하는 여유도 함께 생깁니다.",
            ],
            user_takeaway="지금 필요한 건 더 많이 버티는 힘이 아니라, 어떤 조건에서 강점이 안정적으로 쓰이는지 알아차리는 감각입니다.",
            next_question="어떤 조건에서 내 강점이 가장 편하게 이어질까요?",
            basis_line="보이는 오행 분포와 십성 신호, 현재 시기 자료를 함께 봤습니다.",
        ),
        FreePreviewCard(
            key="work_money",
            title="일과 돈은 어디에서 연결될까?",
            subtitle="역할과 보상 구조를 함께 보는 이유",
            chips=["역할 피로", "돈의 체감", "새는 지점", "남는 결과"],
            preview_paragraphs=[
                "일의 흐름은 능력의 우열보다 역할을 어떻게 맡고 결과를 어떻게 남기는지에서 더 분명해집니다. 무엇을 해내야 하는지가 분명하면 속도와 책임감이 함께 살아나지만, 누가 결정하고 어디까지 맡는지가 흐리면 에너지 소모가 커질 수 있습니다.",
                "돈도 단순히 많이 들어오는지보다 어디서 새는지가 먼저 보입니다. 감정적으로 쓰는 돈, 관계를 유지하려고 쓰는 돈, 급해서 고른 선택이 체감 수입을 늦출 수 있으니 버는 능력만큼 빠져나가는 이유를 알아차리는 감각이 중요합니다.",
                "잘 맞는 일은 결과물이 남고 다시 신뢰로 돌아오는 일입니다. 나의 시간이 쌓일수록 평판이나 기술로 남는 일인지 보는 것이 핵심이고, 이런 일은 당장 화려하지 않아도 시간이 지나며 몸값을 만들 수 있습니다.",
                "지금 살펴볼 것은 더 많이 하는 일이 아니라, 어떤 일이 돈과 안정감으로 이어지는가입니다. 수입 자체보다 일의 형태와 돈의 체감이 어긋나는 지점을 보면 방향이 더 분명해지고, 일의 이름보다 남는 결과를 볼 때 선택이 덜 흔들립니다.",
            ],
            user_takeaway="돈의 답은 더 많이 하는 데보다, 무엇이 실제 보상으로 돌아오는지 알아차리는 데 있습니다.",
            next_question="돈이 들어와도 체감이 늦은 이유는 어디에 있을까요?",
            basis_line="일의 방식과 돈이 움직이는 조건을 함께 봤습니다.",
        ),
        FreePreviewCard(
            key="love",
            title="관계에서 편안함이 중요한 이유",
            subtitle="설렘과 반복되는 태도를 함께 보는 관계",
            chips=["느린 신뢰", "약속의 무게", "표현 속도", "편한 거리"],
            preview_paragraphs=[
                "관계 흐름에서는 마음의 속도만큼 반복되는 태도와 약속을 지키는 방식을 함께 보는 것이 중요합니다. 시간이 지나도 태도가 크게 달라지지 않는지, 일상에서 서로의 리듬을 존중하는지가 관계의 편안함과 연결될 수 있습니다.",
                "처음의 설렘이 커도 생활 리듬이 맞지 않으면 금방 피곤해질 수 있습니다. 관계가 안정되려면 좋아하는 감정만큼 서로의 하루를 방해하지 않는 방식도 중요하고, 작은 약속이 지켜질 때 마음이 천천히 깊어집니다.",
                "주의할 점은 혼자 괜찮은 척하다가 서운함을 늦게 꺼내는 패턴입니다. 작게 말하지 못한 감정은 나중에 한꺼번에 무겁게 터질 수 있고, 그때는 상대가 아니라 나도 내 감정을 늦게 알아차린 것일 수 있습니다.",
                "지금 보면 좋은 것은 누가 더 끌리는가보다 누구와 있을 때 내 생활이 무너지지 않는가입니다. 나를 불안하게 만드는 설렘과 편안하게 만드는 애정을 구분하면 관계 선택이 훨씬 선명해지고, 감정이 편안하게 머무는 자리가 오래 남습니다. 작은 불편을 말로 나눌 수 있는지도 함께 확인해 보세요.",
            ],
            user_takeaway="마음이 깊어지는 속도보다, 함께 있을 때 내가 덜 무너지는지가 더 오래 남습니다.",
            next_question="왜 어떤 관계에서는 편한데, 어떤 관계에서는 금방 지칠까요?",
            basis_line="관계 성향과 현재 시기의 변화를 함께 봤습니다.",
        ),
        FreePreviewCard(
            key="luck_flow",
            title="현재 흐름에서 먼저 정리할 것",
            subtitle="지금 시기와 다음 변화",
            chips=["덜어낼 것", "생활 패턴", "다음 변화", "감정 소모"],
            preview_paragraphs=[
                "현재 흐름은 많은 일을 한꺼번에 판단하기보다, 지금 부담이 되는 선택을 구분하는 데 활용하는 편이 좋습니다. 새로운 일을 전부 막으라는 뜻이 아니라, 이미 무거운 것 위에 또 얹지 않도록 우선순위를 정하는 일이 필요합니다.",
                f"생활에서는 작은 약속을 지키는 힘이 중요합니다. {now_actions} 같은 행동이 쌓이면 다음 변화 앞에서 덜 흔들릴 수 있고, 하루를 망가뜨리는 습관 하나만 줄여도 마음의 여유가 돌아올 수 있습니다.",
                "주의할 점은 불안해서 더 많이 붙잡는 패턴입니다. 특히 책임감 때문에 놓지 못한 일은 실제보다 더 크게 느껴질 수 있고, 내려놓는 일이 실패처럼 보여도 실제로는 에너지를 되찾는 과정일 수 있습니다.",
                "지금 볼 것은 운이 좋고 나쁨이 아니라 무엇을 남기고 무엇을 내려놓을지입니다. 가벼워진 자리에서 새 선택이 들어올 공간도 생기고, 작아 보이는 선택이 앞으로의 속도를 바꿉니다. 매주 한 번만이라도 부담이 커진 일을 돌아보면 조정할 지점이 더 잘 보입니다.",
            ],
            user_takeaway="다음 변화를 잘 쓰려면, 더 얹는 일보다 먼저 내려놓을 일을 알아차려야 합니다.",
            next_question="다음 변화 전에 먼저 덜어내야 할 생활 패턴은 무엇일까요?",
            basis_line="현재와 다음 10년 흐름을 함께 봤습니다.",
        ),
    ]


def _cards_en(payload: InterpretationPayload) -> List[FreePreviewCard]:
    current_cycle = _cycle_name(payload, "current")
    next_cycle = _cycle_name(payload, "next")
    current_period = _period_text(payload, "current")
    next_period = _period_text(payload, "next")
    now_actions = _join(_confirmed_action_tags(payload)[:4], fallback="relationship sorting, spending review, daily routines")
    limitation = (
        "Because the birth time is estimated, hour-pillar-based details should stay conservative. "
        if payload.profile.is_birth_time_estimated
        else ""
    )
    return [
        FreePreviewCard(
            key="core",
            title="Core traits",
            subtitle="Tendencies, strengths, and repeating patterns",
            chips=["standards", "strengths", "patterns", "routine"],
            preview_paragraphs=[
                f"This chart becomes stronger when the person has clear standards around the {payload.day_master} day master. The dominant {_element_text(payload)} signals support quick response, organization, and the ability to separate what matters from what can wait.",
                "Rather than spreading evenly in every direction, the chart tends to show a clear difference between fitting and unfitting environments. When the setting is right, focus comes back quickly and priorities become easier to name.",
                f"The caution is that the same strength may look like stubbornness or over-focus when standards are unclear. {limitation}The chart works best when strong parts are used for results and weaker parts are supported through routine and environment.",
                "The most useful first-screen insight is how the person chooses, recovers, and becomes tired. Once the standard feels internally convincing, work, money, and relationship decisions become less scattered; without that standard, even small choices can feel heavier than they need to be.",
            ],
            user_takeaway="The first task is not to add more choices, but to define standards that can be kept.",
            next_question="How should these strengths be used differently in work and relationships?",
            basis_line="Reflects the day master, five elements, ten-god structure, and current luck cycle.",
        ),
        FreePreviewCard(
            key="work_money",
            title="Work and money flow",
            subtitle="Work style and how money can accumulate",
            chips=["work style", "income structure", "management point", "leakage"],
            preview_paragraphs=[
                f"At work, the chart becomes clearer when roles and standards are defined. The {payload.career_facts.month_pillar_label} and {payload.career_facts.month_stem_ten_god} signals point more toward working method and environment than a single job title.",
                "Money is connected to the way responsibility, output, and trust are built through work. It is better to read this as a structure of income and leakage than as a promise of large earnings.",
                "The practical point is to track which results actually create value and which choices create scattered spending. When work standards become clearer, the money flow also becomes easier to manage.",
                "Work and money should not be read as separate stories here. The better question is which tasks build trust, which outputs can become repeatable value, and which spending habits leave pressure afterward.",
            ],
            user_takeaway="Read work and money together by asking which output can become stable value.",
            next_question="Is the current work direction worth continuing or adjusting?",
            basis_line="Connects the career and wealth readings into one practical structure.",
        ),
        FreePreviewCard(
            key="love",
            title="Love and long-term relationships",
            subtitle="Relationship style and long-term patterns",
            chips=["relationship style", "good fit", "long-term bond", "current advice"],
            preview_paragraphs=[
                f"In relationships, the chart values standards that can last more than quick certainty. The {payload.love_facts.spouse_house_label} and {payload.love_facts.partner_star_label} signals make daily rhythm and responsibility more important than attraction alone.",
                "Auxiliary charm signals should be read only as social attention or attraction indicators. A person may be easy to notice at first, but the relationship becomes meaningful when repeated behavior feels steady.",
                f"During the {current_cycle} period, it is more practical to refine relationship standards than to force a fixed outcome. A long-term bond is easier when both people can share ordinary routines without constant emotional strain.",
                "This preview does not decide the result of a specific relationship. It is meant to show what kind of bond feels sustainable, what pattern creates fatigue, and why ordinary rhythm matters as much as emotional intensity.",
            ],
            user_takeaway="Do not rush the label; watch whether the relationship makes everyday life steadier.",
            next_question="What kind of person is easier to stay compatible with over time?",
            basis_line="Reviews spouse-house, partner-star, relationship signals, and current flow.",
        ),
        FreePreviewCard(
            key="luck_flow",
            title="Current and next luck flow",
            subtitle="Current timing and the next shift",
            chips=["current timing", "next shift", "preparation", "standards"],
            preview_paragraphs=[
                f"The current timing is read through {current_cycle} in {current_period}. It is not a fixed-event prediction, but a period for shaping standards through practical actions such as {now_actions}.",
                f"The next flow moves toward {next_cycle} in {next_period}. Standards and routines built now can make later choices in work, relationships, and money easier to read.",
                "Luck cycles are best used as a map of tendencies, not a sentence about what must happen. The useful move now is to slow down enough to organize boundaries, habits, and repeatable choices.",
                "When emotions rise, the current flow asks for a pause before deciding. Preparing for the next cycle means setting small rules around daily rhythm, spending, work boundaries, and the kinds of relationships that are worth continuing.",
            ],
            user_takeaway="The current flow is preparation for better choices, not a guarantee of a fixed event.",
            next_question="What should be prepared now to use the next luck cycle well?",
            basis_line="Centers on the current luck cycle and the next luck-cycle transition.",
        ),
    ]


# These are plain-language renderings of supplied Ten-God labels, not a new
# calculation or ranking. The same peer/output/wealth/officer/resource meanings
# are used by the existing period guidance. Unknown labels stay unclassified.
FACT_VOICES = {
    "peer": {
        "ko": (
            "같이 일하는데 왜 내 몫만 늘어날까?",
            "자기 방식과 협업의 경계를 먼저 살펴볼 만합니다. 혼자 해낼 수 있는 일이라도 함께 맡으면 누가 결정하고 어디까지 책임지는지 적어 두는 편이 좋습니다.",
            "혼자 잘하는 것과 함께 잘하는 건 다릅니다. 내 몫과 공동의 몫을 먼저 나눠 보세요.",
            "좋아해도 내 시간은 지키고 싶은 걸까?",
            "가까워지는 마음과 내 생활을 지키는 일을 함께 살펴봅니다. 연락 횟수만 맞추기보다 혼자 쉬는 시간과 함께 보내는 시간을 서로 이야기해 보는 방식이 도움이 될 수 있습니다.",
            "가까워져도 내 하루는 남겨 두세요. 함께하는 시간과 혼자 쉬는 시간을 말로 맞춰 보세요.",
        ),
        "en": (
            "Working together, carrying it alone?",
            "Start with personal methods and shared ownership. Even when you can complete a task alone, agreeing who decides and who is responsible makes collaboration easier to check.",
            "Being good alone and working well together are different tasks. Separate personal and shared ownership.",
            "Can closeness leave room for your own day?",
            "Look at closeness alongside personal space. Instead of measuring the bond by message frequency, talk about time together and time to recover alone.",
            "Leave room for your own day too. Agree on time together and time to recover alone.",
        ),
    },
    "output": {
        "ko": (
            "아이디어는 많은데 완성본은 어디 갔을까?",
            "표현한 생각을 결과물로 남기는 방식을 먼저 살펴볼 만합니다. 제안이 늘어날 때마다 새 일을 벌이기보다 초안 하나를 끝까지 마쳐 누가 쓸 수 있는지 확인해 보세요.",
            "생각 하나를 남이 쓸 수 있는 완성본으로 바꿔 보세요. 말한 것과 마친 것을 나눠 보면 일이 선명해집니다.",
            "마음은 있는데 말이 먼저 앞서는 걸까?",
            "마음을 표현하고 함께 시간을 즐기는 방식을 먼저 살펴봅니다. 대화가 잘 이어지는 순간에도 내 말만 길어지지 않는지, 상대가 답할 자리가 남아 있는지 확인해 볼 만합니다.",
            "마음을 말로 꺼냈다면 답을 들을 자리도 남겨 두세요. 표현과 경청을 한 쌍으로 보세요.",
        ),
        "en": (
            "Plenty of ideas, but where is the finished work?",
            "Start with turning expression into a usable result. When proposals keep multiplying, finish one draft and check who can actually use it before opening another task.",
            "Turn one idea into something another person can use. Separate what was said from what was finished.",
            "Does the conversation run ahead of the feeling?",
            "Look first at expression and enjoyment together. Even when conversation feels easy, leave space for the other person to answer instead of carrying the whole exchange yourself.",
            "After expressing a feeling, leave room for an answer. Read expression and listening together.",
        ),
    },
    "wealth": {
        "ko": (
            "열심히 했는데 남는 건 어디에 있을까?",
            "쓴 시간과 실제로 남은 보상을 함께 살펴볼 만합니다. 바쁜 일정 자체를 성과로 세기보다 일이 끝난 뒤 돈, 기술, 다시 쓸 수 있는 결과물 중 무엇이 남는지 적어 보세요.",
            "바빴다는 사실보다 남은 결과를 보세요. 쓴 시간과 돌아온 보상을 나란히 적어 보세요.",
            "설렘 다음에 현실도 같이 보는 걸까?",
            "호감과 함께 시간, 돈, 생활을 나누는 방식을 살펴봅니다. 마음을 확인하려고 무리한 선물이나 약속을 늘리기보다 함께 보내는 평범한 하루가 서로에게 편한지 볼 만합니다.",
            "설렘을 확인하느라 생활을 무리하게 쓰지 마세요. 평범한 하루도 함께 편한지 보세요.",
        ),
        "en": (
            "Working hard, but what actually remains?",
            "Look at time spent alongside the reward that remains. Rather than treating a crowded schedule as an achievement, check whether each task leaves income, a skill, or reusable work.",
            "Check the result that remains, not only the effort spent. Put time and actual reward side by side.",
            "What happens when excitement meets daily life?",
            "Look at affection alongside sharing time, money, and everyday life. Instead of stretching gifts or promises to prove a feeling, check whether an ordinary day together feels manageable.",
            "Do not stretch daily life just to prove excitement. See whether an ordinary day together feels comfortable.",
        ),
    },
    "officer": {
        "ko": (
            "일은 돌아가는데 왜 내 일정은 꽉 찰까?",
            "책임과 마감을 어디까지 맡는지 먼저 살펴볼 만합니다. 믿고 맡긴다는 말을 들었을 때 모든 요청을 받아들일 필요는 없고, 추가되는 일만큼 일정과 담당 범위도 다시 확인해 보세요.",
            "새 일을 받으면 마감과 담당 범위도 같이 바꾸세요. 믿고 맡긴다는 말이 내 일정 전체를 뜻하지는 않습니다.",
            "좋아한다는 말보다 약속이 먼저 보일까?",
            "관계에서 약속과 책임을 나누는 방식을 먼저 살펴봅니다. 연락이 달콤한 날만 보기보다 취소된 약속을 어떻게 다시 잡는지, 어려운 이야기를 함께 이어갈 수 있는지 볼 만합니다.",
            "좋아한다는 말과 약속을 지키는 행동을 함께 보세요. 작은 약속 하나부터 서로의 속도를 맞춰 보세요.",
        ),
        "en": (
            "Why does every task fill your calendar?",
            "Start with the responsibility and deadlines you accept. Being trusted with a task does not require taking every request; confirm scope and timing whenever extra work is added.",
            "When new work arrives, revise the scope and deadline too. Trust does not mean owning every request.",
            "Do promises matter before sweet words?",
            "Look first at shared promises and responsibility. Beyond an affectionate message, watch how a cancelled plan is rearranged and whether difficult conversations can continue.",
            "Read affectionate words alongside kept promises. Start with one small agreement at a shared pace.",
        ),
    },
    "resource": {
        "ko": (
            "많이 배웠는데 써먹을 시간은 있을까?",
            "배운 것을 실제 일에 옮기는 방식을 먼저 살펴볼 만합니다. 자료를 더 모으는 날과 이미 아는 것을 써보는 날을 나눠 두고, 지식이 쌓인 만큼 일이 조금이라도 편해지는지 확인해 보세요.",
            "더 배우기 전에 이미 아는 것 하나를 써보세요. 자료를 모으는 시간과 쓰는 시간을 나눠 보세요.",
            "마음이 편해야 가까워지는 걸까?",
            "관계 안에서 이해받고 회복할 자리가 있는지 먼저 살펴봅니다. 상대를 더 잘 알기 위해 생각하는 시간도 필요하지만, 대답을 혼자 추측하기보다 작은 질문으로 직접 확인하는 방식이 도움이 될 수 있습니다.",
            "혼자 오래 해석하기 전에 작은 질문을 건네 보세요. 편안함은 마음을 맞히는 일보다 대화에서 확인하세요.",
        ),
        "en": (
            "Learning plenty, but when do you use it?",
            "Start with bringing learned knowledge into actual work. Separate collecting material from applying something you already know, and check whether learning makes one task easier.",
            "Before collecting more knowledge, use one thing you already know. Separate learning time from application time.",
            "Do you need comfort before getting closer?",
            "Look first for room to feel understood and recover within a relationship. Time to think can help, but a small direct question is more useful than privately guessing another person's answer.",
            "Ask a small question before privately interpreting everything. Check comfort through conversation.",
        ),
    },
}


def _supplied_ten_god_group(label: str) -> str | None:
    reverse_english = {value: key for key, value in TEN_GOD_ENGLISH.items()}
    canonical = reverse_english.get(label, localize_ten_god(label, "ko"))
    for group, labels in {
        "peer": {"비견", "겁재"},
        "output": {"식신", "상관"},
        "wealth": {"정재", "편재"},
        "officer": {"정관", "편관"},
        "resource": {"정인", "편인"},
    }.items():
        if canonical in labels:
            return group
    return None


def _metric_basis(metrics: Sequence[Any], locale: str) -> str:
    unit = "개" if locale == "ko" else ""
    values = [f"{item.label} {item.count}{unit}" for item in metrics]
    return ", ".join(values) or ("확인된 항목 없음" if locale == "ko" else "No supplied metrics")


BASIS_READINGS = {
    "peer": {
        "ko": ("개인 업무와 공동 업무의 역할 경계", "관계 안에서의 개인 기준과 시간 배분"),
        "en": ("personal and shared ownership at work", "personal space and time together"),
    },
    "output": {
        "ko": ("생각을 완성된 결과물로 옮기는 방식", "마음을 표현하는 방식과 상대의 응답을 수용할 여지"),
        "en": ("turning an idea into finished, usable work", "expression and room to hear an answer"),
    },
    "wealth": {
        "ko": ("투입한 시간과 확보한 보상의 균형", "관계에서의 애정 표현과 시간·돈·생활 자원의 배분"),
        "en": ("time spent and the reward that remains", "affection alongside shared time and everyday resources"),
    },
    "officer": {
        "ko": ("책임의 범위와 마감 관리", "애정 표현과 약속 이행의 일치 여부"),
        "en": ("the responsibility and deadlines you accept", "affectionate words and kept promises"),
    },
    "resource": {
        "ko": ("학습한 내용을 실제 업무에 적용하는 방식", "관계에서의 이해와 회복을 위한 여유"),
        "en": ("applying what you have learned", "feeling understood and having room to recover"),
    },
}


def _cycle_basis_fact(cycle: Any, *, next_cycle: bool, locale: str) -> str | None:
    label = cycle.display_gan_zhi
    if not label or contains_hanja(label) or (locale == "en" and contains_hangul(label)):
        return None
    start, end = cycle.start_datetime, cycle.change_datetime
    if start and end and re.match(r"^\d{4}-\d{2}", start) and re.match(r"^\d{4}-\d{2}", end):
        period = (f"{start[:4]}년 {int(start[5:7])}월 ~ {end[:4]}년 {int(end[5:7])}월" if locale == "ko" else f"{start[:7]} to {end[:7]}")
    else:
        period = f"{cycle.start_year} ~ {cycle.end_year}"
    prefix = ("다음 10년 구간(대운)" if next_cycle else "현재 10년 구간(대운)") if locale == "ko" else ("Next luck-cycle window" if next_cycle else "Current luck-cycle window")
    return f"{prefix}: {label} · {period}"


def _card_basis_explanation(payload: InterpretationPayload, key: str) -> ReadingBasisExplanation | None:
    """Expose facts behind the existing renderer, without adding chart judgments."""
    ko = _is_ko(payload)
    locale = _locale(payload)
    if key in {"work_money", "love"}:
        label = payload.career_facts.month_stem_ten_god if key == "work_money" else payload.love_facts.spouse_house_ten_god
        group = _supplied_ten_god_group(label)
        if group is None:
            return None
        supplied = localize_ten_god(label, locale)
        prefix = ("태어난 달에서 확인한 단서(월간)" if key == "work_money" else "관계를 살펴본 자리(배우자궁)") if ko else ("Work reference (month stem)" if key == "work_money" else "Relationship reference (spouse house)")
        theme = BASIS_READINGS[group][locale][0 if key == "work_money" else 1]
        reference = ("월간 십성" if key == "work_money" else "배우자궁에서 확인된 십성") if ko else ("month-stem ten-god" if key == "work_money" else "spouse-house ten-god")
        reading = f"{reference}은 ‘{supplied}’입니다. 이를 근거로 {theme}에 관한 해석 방향을 검토했습니다." if ko else f"The {reference} is '{supplied}'. The interpretation considers {theme}."
        return ReadingBasisExplanation(facts=[f"{prefix}: {supplied}"], reading=reading)
    if key == "core":
        labels = {"wood": "목", "fire": "화", "earth": "토", "metal": "금", "water": "수"} if ko else {item: item for item in ("wood", "fire", "earth", "metal", "water")}
        dominant = payload.signals.dominant_elements[:2]
        if not dominant or any(item not in labels or payload.element_counts.get(item, 0) <= 0 for item in dominant):
            return None
        counts = ", ".join(f"{labels[item]} {payload.element_counts[item]}{'개' if ko else ''}" for item in dominant)
        facts = [f"보이는 기둥의 강한 오행: {counts}" if ko else f"Stronger visible elements: {counts}"]
        reading = f"표면 오행의 분포를 {_dominant_strength_phrase(payload)}과 관련된 해석의 참고 자료로 검토했습니다." if ko else f"The visible-element distribution was reviewed in relation to {_dominant_strength_phrase(payload)}."
        missing = payload.signals.missing_elements
        if missing and all(item in labels and payload.element_counts.get(item) == 0 for item in missing):
            values = ", ".join(labels[item] for item in missing)
            facts.append(f"보이는 기둥에 없는 오행: {values}" if ko else f"Elements absent from the visible pillars: {values}")
            reading += f" 표면 오행에서 확인되지 않은 항목은 {_support_need_phrase(payload)}을 살펴보는 참고 단서로 검토했습니다." if ko else f" Elements absent from the visible pillars were considered as prompts to review {_support_need_phrase(payload)}."
        if payload.profile.is_birth_time_estimated:
            facts.append("출생시간 미상: 시주 제외" if ko else "Unknown birth time: the hour pillar is excluded")
        return ReadingBasisExplanation(facts=facts, reading=reading)
    if key != "luck_flow":
        return None
    if not _has_confirmed_current_cycle(payload):
        if payload.profile.is_birth_time_estimated:
            fact = "출생시간 미상: 시주·대운 계산 비활성" if ko else "Unknown birth time: hour-pillar and luck-cycle calculation are disabled"
        elif "luck_cycles" in payload.disabled_sections or any(item.key == "luck_cycles" and item.status == "disabled" for item in payload.evidence):
            fact = "대운 계산 비활성: 현재·다음 구간 미확인" if ko else "Luck-cycle calculation is disabled; current and next windows are unconfirmed"
        else:
            fact = "현재 대운 자료: 미확인" if ko else "Current luck-cycle facts: unavailable"
        return ReadingBasisExplanation(facts=[fact], reading="현재·다음 대운과 전환 시점을 확인할 수 없어 시기 비교를 보류했습니다. 조언은 확인 가능한 생활 점검 항목으로 제한했습니다." if ko else "The current and next luck cycles and their transition timing could not be confirmed, so timing comparison was withheld. Advice is limited to observable everyday checks.")
    current, following = payload.current_flow.active_luck_cycle, payload.current_flow.next_luck_cycle
    current_fact = _cycle_basis_fact(current, next_cycle=False, locale=locale)
    next_fact = _cycle_basis_fact(following, next_cycle=True, locale=locale) if following else None
    if current_fact is None or (following is not None and next_fact is None):
        return None
    facts = [current_fact, next_fact] if next_fact else [current_fact, "다음 대운 자료: 미확인" if ko else "Next luck-cycle facts: unavailable"]
    flow = payload.luck_flow_facts
    current_phase = flow.current_phase_label if flow.current_luck_cycle == current.display_gan_zhi else ""
    next_phase = flow.next_phase_label if following and flow.next_luck_cycle == following.display_gan_zhi else ""
    if not following:
        reading = "현재 대운만 확인되어 다음 대운과의 비교는 보류했습니다." if ko else "Only the current luck cycle was confirmed; comparison with the next cycle was withheld."
    elif current_phase and next_phase and not contains_hanja(current_phase + next_phase) and (ko or not contains_hangul(current_phase + next_phase)):
        if current_phase == next_phase:
            reading = f"현재·다음 대운의 제공된 분류에서 ‘{current_phase}’라는 공통 주제를 확인했습니다. 이를 조언의 참고 방향으로 검토했습니다." if ko else f"The supplied current and next luck-cycle classifications share the theme '{current_phase}'. This classification was reviewed as context for the advice."
        else:
            reading = f"제공된 분류에서 현재 대운은 ‘{current_phase}’, 다음 대운은 ‘{next_phase}’로 확인했습니다. 각 분류를 조언의 참고 방향으로 검토했습니다." if ko else f"The supplied classifications identify '{current_phase}' for the current luck cycle and '{next_phase}' for the next. These classifications were reviewed as context for the advice."
    else:
        reading = "제공된 현재·다음 대운의 기간을 생활 점검의 시간 범위로 검토했습니다. 특정 사건의 발생일을 산출하거나 확정하지 않았습니다." if ko else "The supplied current and next luck-cycle periods were reviewed as timing context for everyday choices. No date for a specific event was calculated or confirmed."
    return ReadingBasisExplanation(facts=facts, reading=reading)


def _fact_aware_cards(payload: InterpretationPayload, cards: List[FreePreviewCard]) -> List[FreePreviewCard]:
    """Render supplied facts without inferring missing counts, stars or timing.

    A missing/zero fact must not become a negative prediction. These cards are
    practical reference prompts selected by the already calculated categories.
    """
    ko = _is_ko(payload)
    locale = _locale(payload)
    by_key = {card.key: card for card in cards}
    work = by_key["work_money"]
    love = by_key["love"]
    core = by_key["core"]
    luck = by_key["luck_flow"]
    work_group = _supplied_ten_god_group(payload.career_facts.month_stem_ten_god)
    love_group = _supplied_ten_god_group(payload.love_facts.spouse_house_ten_god)
    if work_group:
        voice = FACT_VOICES[work_group][locale]
        work.title = work.subtitle = voice[0]
        work.preview_paragraphs[0] = voice[1] + (
            " 직업 이름 하나를 정답으로 고르기보다 일을 맡고 마치는 방식부터 확인하는 참고 포인트입니다. 잘해낼 수 있는 일과 계속 감당할 수 있는 일이 같은지도 함께 보세요."
            if ko else " This is a reference point for how work is accepted and completed, not a choice of one destined occupation. Check both what you can do and what you can keep doing sustainably."
        )
        work.user_takeaway = voice[2]
    else:
        work.title = work.subtitle = "어떤 일이 남는 결과로 이어질까?" if ko else "Which tasks leave a useful result?"
        work.preview_paragraphs[0] = (
            "현재 확인된 자료만으로 한 가지 일하는 방식을 강하게 고르기는 어렵습니다. 직업 이름이나 성공 가능성을 단정하는 대신, 일주일 동안 맡은 일과 끝낸 일을 적어 어떤 환경에서 힘이 덜 드는지 살펴볼 만합니다. 역할이 분명한 날과 요청이 계속 바뀌는 날을 나눠 보면 실제로 지속할 수 있는 일이 무엇인지 더 쉽게 확인할 수 있습니다."
            if ko else "The supplied facts do not support singling out one strong working method. Instead of choosing a destined job or predicting success, record the tasks accepted and completed during one week and compare the environments that require less effort. Separate days with clear ownership from days when requests keep changing."
        )
        work.user_takeaway = "맡은 일과 끝낸 일을 나란히 적어 보세요. 내게 남는 결과부터 확인하세요." if ko else "Put accepted and finished tasks side by side. Check what actually remains for you."
    present_wealth = any(item.key == "wealth" and item.count > 0 for item in payload.wealth_facts.key_ten_gods)
    present_output = any(item.key == "output" and item.count > 0 for item in payload.wealth_facts.key_ten_gods)
    if present_wealth:
        work.preview_paragraphs[1] = (
            "돈과 자원을 다루는 단서가 현재 확인된 자료에 있어, 들어온 돈과 남은 돈을 나눠 살펴봅니다. 수입이 생겨도 유지 비용이나 반복 지출이 함께 커지면 체감이 늦어질 수 있으니, 금액을 예측하기보다 한 달 동안 들어오고 나간 항목을 같은 종이에 적어 보세요."
            if ko else "The supplied facts include money-and-resource signals, so compare incoming money with what remains. Income can feel less useful when carrying costs and recurring expenses rise alongside it. Rather than predicting an amount, put one month's inflows and outflows on the same page."
        )
    elif present_output:
        work.preview_paragraphs[1] = (
            "현재 확인된 자료에서는 표현하고 만드는 단서를 참고할 수 있지만, 이것만으로 수입의 크기를 정할 수는 없습니다. 만든 결과물을 누가 쓰고 어떤 대가를 지불하는지 연결해 보는 편이 좋습니다. 작업 시간이 길었다는 사실과 실제 보상으로 이어진 일을 나눠 적으면 계속할 일과 조정할 일이 더 분명해집니다."
            if ko else "The supplied facts include expression-and-output signals, which cannot determine the size of an income. Check who uses a finished result and what they pay for it. Separate long hours from work that actually creates compensation, so continuing or adjusting a task becomes easier to assess."
        )
    else:
        work.preview_paragraphs[1] = (
            "현재 확인된 자료에서 돈과 결과물의 연결을 강하게 고를 단서는 제한적입니다. 이것을 돈을 못 벌거나 일이 안 된다는 뜻으로 읽지는 않습니다. 사주 문장보다 실제 수입과 지출 기록을 함께 보고, 생활에 필요한 비용과 선택해서 쓰는 비용을 나눠 지금 조정할 수 있는 항목부터 확인해 보세요."
            if ko else "The supplied facts provide limited signals for singling out a money-and-output connection. That does not mean an inability to earn or succeed. Compare the reading with actual income and expense records, separating essential costs from optional choices before selecting one item you can adjust now."
        )
    work.basis_line = (
        f"월간 {payload.career_facts.month_stem_ten_god or '미확인'}; 일 단서 {_metric_basis(payload.career_facts.key_ten_gods, locale)}; 돈 단서 {_metric_basis(payload.wealth_facts.key_ten_gods, locale)}."
        if ko else f"Month-stem signal: {payload.career_facts.month_stem_ten_god or 'unavailable'}; career: {_metric_basis(payload.career_facts.key_ten_gods, locale)}; wealth: {_metric_basis(payload.wealth_facts.key_ten_gods, locale)}."
    )
    if love_group:
        voice = FACT_VOICES[love_group][locale]
        love.title = love.subtitle = voice[3]
        love.preview_paragraphs[0] = voice[4] + (
            " 약속을 잡는 날과 각자 쉬는 날을 나눠 생각해 보세요. 같은 연락도 바쁜 날과 여유로운 날에는 다르게 느껴질 수 있으니, 원하는 속도를 서로 말해보는 편이 도움이 됩니다."
            if ko else " Compare a day with plans together and a day spent recovering alone. The same message can feel different on a busy day and a quiet one, so name the pace you would each prefer."
        )
        love.user_takeaway = voice[5]
    else:
        love.title = love.subtitle = "내가 편한 관계는 어떤 모습일까?" if ko else "What does a comfortable bond look like for you?"
        love.preview_paragraphs[0] = (
            "현재 확인된 자료만으로 관계 습관 하나를 강하게 고르기는 어렵습니다. 연락의 속도나 만나는 횟수보다 함께 있을 때 편한 점과 불편한 점을 하나씩 말해보는 편이 좋습니다. 좋아하는 장소를 정하거나 쉬는 날을 맞춰보는 작은 선택에서도 서로 편한 방식이 어떻게 다른지 직접 확인할 수 있습니다."
            if ko else "The supplied facts do not support singling out one strong relationship habit. Instead of measuring message speed or meeting frequency, name one comfortable and one uncomfortable part of being together. Small choices, such as picking a place or arranging a quiet day, can show how your preferred ways differ."
        )
        love.user_takeaway = "편한 점과 불편한 점을 하나씩 말해보세요. 상대의 답은 직접 들어보세요." if ko else "Name one comfortable and one uncomfortable part. Hear the other person's answer directly."
    love.preview_paragraphs[1] = (
        ("관계를 보는 기본 단서가 확인되어, 기대와 책임을 어떻게 나누는지 함께 살펴봅니다. 데이트 날짜를 정할 때 한 사람만 계속 양보하는지, 일정이 바뀌면 다시 맞춰보는지 볼 만합니다. 평소 지킬 수 있는 작은 약속을 하나 정하고, 서로 힘든 날에도 그 약속을 조정할 수 있는지 확인해 보세요."
         if payload.love_facts.partner_star_count > 0 else
         "관계를 보는 기본 단서가 현재 확인된 자료에서는 두드러지지 않습니다. 이것을 연애 기회가 없거나 마음을 나누기 어렵다는 뜻으로 읽지는 않습니다. 실제 관계에서 내가 편해지는 대화와 불편해지는 상황을 하나씩 적어 보면, 문장만으로 알 수 없는 생활의 차이를 직접 확인할 수 있습니다.")
        if ko else
        ("The supplied facts include partner-related signals, so look at how expectations and responsibility are shared. When arranging a date, notice whether one person always yields or both help rearrange changed plans. Agree on one small promise that can be kept and check whether it can be adjusted together on a difficult day."
         if payload.love_facts.partner_star_count > 0 else
         "Partner-related signals are not prominent in the supplied facts. This does not mean having no chance to date or share affection. Record conversations that feel comfortable and situations that feel difficult in actual relationships, so everyday differences can be checked rather than guessed from a reading.")
    )
    love.basis_line = (
        f"배우자궁 십성 {payload.love_facts.spouse_house_ten_god or '미확인'}; {payload.love_facts.partner_star_label} {payload.love_facts.partner_star_count}개."
        if ko else f"Spouse-house signal: {payload.love_facts.spouse_house_ten_god or 'unavailable'}; {payload.love_facts.partner_star_label}: {payload.love_facts.partner_star_count}."
    )
    localized_star_labels = [
        label for label in payload.love_facts.active_star_labels
        if not contains_hanja(label) and (ko or not contains_hangul(label))
    ]
    if localized_star_labels:
        love.basis_line += (" 보조 단서 " if ko else " Supporting signals: ") + ", ".join(localized_star_labels) + "."
    love.preview_paragraphs[2] = (
        "사주만으로 상대의 속마음이나 관계의 결과를 알 수는 없습니다. 편한 관계를 찾으려면 기대하는 연락과 약속의 양을 말로 나눠 보는 편이 좋습니다. 작은 불편을 이야기했을 때 서로 고칠 방법을 찾을 수 있는지도 함께 확인해 보세요. 실제로 들은 대답과 반복되는 행동을 보면 혼자 해석하던 부분을 대화로 풀어볼 수 있습니다."
        if ko else "A chart cannot reveal another person's private feelings or decide a relationship outcome. Talk about the amount of contact and commitment each person expects, and see whether small difficulties can lead to shared adjustments. Actual answers and repeated behavior can bring a private interpretation into a conversation you can both take part in."
    )
    if not ko:
        love.preview_paragraphs[3] = "Think of a dinner plan that changes at the last minute. Does one person quietly absorb the inconvenience, or can both suggest a new plan? A short conversation about time, cost, and energy can make an ordinary evening easier than trying to decode every message. Notice which small adjustments leave both people more comfortable."
    core.user_takeaway = (
        f"강점은 {_dominant_strength_phrase(payload)}, 보완할 것은 {_support_need_phrase(payload)}입니다. 두 가지를 함께 쓸 수 있는 역할을 골라보세요."
        if ko else f"Review {_dominant_strength_phrase(payload)} alongside support for {_support_need_phrase(payload)}. Choose a role where both are sustainable."
    )
    if ko:
        core.preview_paragraphs[-1] += " 하루를 마칠 때 힘이 남은 일과 금방 소모된 일을 하나씩 적어보세요. 능력이 부족해서였는지, 요청이 바뀌거나 쉴 틈이 없어서였는지 나눠 보면 맡을 역할과 도움을 청할 부분을 더 구체적으로 찾을 수 있습니다."
    core.basis_line = (
        f"보이는 오행: 강한 부분 {_element_text(payload)}; 보완 신호 {_missing_element_text(payload)}."
        if ko else f"Supplied dominant elements: {_element_text(payload)}; missing elements: {_missing_element_text(payload)}."
    )
    timing_available = _has_confirmed_current_cycle(payload)
    if timing_available and payload.luck_flow_facts.now_action_tags:
        action = payload.luck_flow_facts.now_action_tags[0]
        luck.user_takeaway = f"먼저 살펴볼 일은 {action}입니다. 이번 주에 반복할 수 있는 작은 행동 하나로 줄여보세요." if ko else f"Start by reviewing {action}. Reduce it to one small action you can repeat this week."
    elif not timing_available:
        luck.subtitle = "시기보다 지금 확인할 수 있는 것" if ko else "What can be checked without confirmed timing"
        luck.preview_paragraphs[0] = (
            "출생시간이나 현재 시기 자료가 충분하지 않아 지금과 다음의 전환 시점을 확정하지 않았습니다. 특정 해에 무엇이 좋아진다고 말하는 대신, 현재 생활에서 확인할 수 있는 약속과 지출, 일의 부담을 나눠 살펴보세요. 바꿀 수 있는 작은 항목 하나부터 적으면 시기를 단정하지 않고도 오늘의 선택을 점검할 수 있습니다."
            if ko else "Birth-time or current-period facts are insufficient to confirm the current and next transition timing. Instead of assigning improvement to a particular year, examine the promises, expenses, and work demands visible in daily life. Start by writing down one small item you can change without making a timing claim."
        )
        luck.preview_paragraphs[1] = (
            "전환 시점이 확인되지 않았다고 선택을 멈출 필요는 없습니다. 생활에서 반복되는 부담과 편안한 상황을 구분하고, 이미 지키는 약속 중 너무 무거워진 것이 있는지 돌아볼 만합니다. 이 조언은 특정 시기의 유불리를 계산한 결론이 아니라 지금의 행동을 점검하는 일반적인 참고 질문입니다."
            if ko else "Unconfirmed timing does not require stopping every decision. Compare recurring demands with comfortable situations and examine whether an existing promise has become too heavy. This advice is a general action-check question, not a conclusion about the favorability of a calculated period."
        )
        luck.user_takeaway = "시기 판단은 보류하고, 지금 확인할 수 있는 부담 하나부터 점검해 보세요." if ko else "Leave timing unconfirmed and check one demand you can actually observe now."
        luck.basis_line = "현재·다음 대운 연결은 확정하지 않았으며, 시간에 의존하는 근거를 사용하지 않았습니다." if ko else "Current and next luck-cycle connections are unconfirmed; time-dependent evidence was not used."
        if not ko:
            luck.preview_paragraphs[2] = "Picture a day when several small requests arrive together. Before accepting them all, list what is already promised and which request can wait. A pause can help you choose from the demands you can actually observe, without treating the day as a favorable or unfavorable period."
            luck.preview_paragraphs[3] = "Pick one ordinary habit to review: an expense you repeat, a task you keep postponing, or a conversation you want to have. Make one small adjustment and check whether it helps during the week. Use the observed result to keep, change, or drop the adjustment rather than assigning it to a future cycle."
    for card in cards:
        card.basis_explanation = _card_basis_explanation(payload, card.key)
    # Pydantic may reuse model instances without checking fields changed after
    # construction. Validate the rendered values before the public response does.
    return [_model_validate(FreePreviewCard, _model_dump_json(card)) for card in cards]


def build_fallback_free_preview_report(payload: InterpretationPayload) -> FreePreviewReport:
    if _is_ko(payload):
        headline = _headline_ko(payload)
        strength = _dominant_strength_phrase(payload)
        support_need = _support_need_phrase(payload)
        now_actions = _join(
            _confirmed_action_tags(payload)[:3],
            fallback="생활 리듬, 지출, 관계의 경계",
        )
        hero_overview = [
            f"이 결과에서 먼저 보는 강점은 {strength}입니다.",
            f"반복해서 살필 부분은 {support_need}이며, 생활 속에서 어떻게 보완하는지가 중요합니다.",
            "강점은 역할과 우선순위가 분명할 때 더 안정적으로 쓰일 수 있습니다.",
            "환경과 책임 범위가 계속 바뀌면, 같은 강점도 피로로 이어지는지 함께 살피는 편이 좋습니다.",
            f"현재는 {now_actions}처럼 실제로 반복할 수 있는 행동을 작게 정리하는 데 의미가 있습니다.",
            "관계에서는 설렘의 크기만큼 대화, 약속, 생활 리듬이 이어지는지도 함께 보는 편이 좋습니다.",
            "일과 돈에서는 노력의 양보다 어떤 결과가 보상과 안정감으로 이어지는지 확인하는 일이 중요합니다.",
            "이 결과는 정해진 사건을 말하기보다, 편해지는 선택과 소모가 커지는 선택을 구분하는 참고 자료입니다.",
        ]
        diagnoses = _diagnoses_ko(payload)
        cards = _fact_aware_cards(payload, _cards_ko(payload))
    else:
        headlines = {
            "wood": "An explorer of possibilities and directions",
            "fire": "Energy through response and expression",
            "earth": "A steady anchor for practical tasks",
            "metal": "A person who separates essentials and finishes",
            "water": "A reader and coordinator of situations",
        }
        headline = next((headlines[item] for item in payload.signals.dominant_elements if item in headlines), "Finding a workable way through everyday choices")
        current_cycle = _cycle_name(payload, "current")
        next_cycle = _cycle_name(payload, "next")
        confirmed_timing = _has_confirmed_current_cycle(payload)
        hero_overview = [
            "This chart becomes stronger when clear standards are in place.",
            f"The main strength is the ability to respond and organize through the {_element_text(payload)} side of the chart.",
            "The repeating pattern is strong focus in a fitting environment and faster fatigue when standards are unclear.",
            (f"The supplied current period is {current_cycle}; compare its action points with actual work, money, and relationship choices."
             if confirmed_timing else "Current timing is unconfirmed, so work, money, and relationship habits are reviewed without a luck-cycle claim."),
            "The caution is that speed without structure can increase spending pressure and relationship strain.",
            "The best use of the chart is to turn strengths into results while supporting weaker parts through routine.",
            "In relationships, daily rhythm and responsibility matter more than quick certainty.",
            "In work and money, output, responsibility, and management rules become connected.",
            (f"The supplied next cycle is {next_cycle}; use it as reference context rather than an event prediction."
             if confirmed_timing and payload.current_flow.next_luck_cycle else "The next transition is unconfirmed; use routines and observed choices without assigning a future date."),
        ]
        diagnoses = _diagnoses_en(payload)
        cards = _fact_aware_cards(payload, _cards_en(payload))

    plan = apply_reading_plan(payload, cards)
    payload.reading_plan = plan
    return FreePreviewReport(
        provider="fallback",
        model="fallback",
        prompt_version=PROMPT_SPEC.version,
        headline=headline,
        hero_overview=hero_overview,
        core_diagnoses=diagnoses,
        cards=cards,
        question_capabilities=plan.question_capabilities,
        warnings=[flag.code for flag in payload.uncertainty_summary],
    )


def _parse_free_preview_output(output_text: str) -> FreePreviewLLMOutput:
    parsed_json = json.loads(output_text)
    return _model_validate(FreePreviewLLMOutput, parsed_json)


def _build_openai_report(parsed: FreePreviewLLMOutput) -> FreePreviewReport:
    return _build_provider_report(parsed, provider="openai")


def _build_provider_report(parsed: FreePreviewLLMOutput, *, provider: str) -> FreePreviewReport:
    return FreePreviewReport(
        provider=provider,  # type: ignore[arg-type]
        model=_provider_model(provider),
        prompt_version=PROMPT_SPEC.version,
        headline=parsed.headline,
        hero_overview=parsed.hero_overview,
        core_diagnoses=parsed.core_diagnoses,
        cards=[_model_validate(FreePreviewCard, {**_model_dump_json(card), "basis_explanation": None, "reading_structure": None}) for card in parsed.cards],
        warnings=[],
    )


def _call_openai_free_preview(
    payload: InterpretationPayload,
) -> Tuple[FreePreviewReport | None, InterpretationDiagnostics]:
    payload_json = json.dumps(_model_dump_json(payload), ensure_ascii=False)
    if OpenAI is None:
        return None, _make_diagnostics(
            final_provider="fallback",
            payload_json=payload_json,
            fallback_reason="openai_sdk_unavailable",
        )

    client = OpenAI(
        api_key=settings.openai_api_key,
        timeout=settings.llm_timeout_seconds,
        max_retries=0,
    )
    token_budgets = [
        max(4200, min(settings.llm_max_output_tokens, 6000)),
        max(5200, min(settings.llm_max_output_tokens * 2, 8000)),
    ]
    attempts: List[InterpretationAttemptDiagnostic] = []
    started = time.perf_counter()
    last_response_id: str | None = None
    fallback_reason = "openai_response_invalid"

    for attempt_index, token_budget in enumerate(
        token_budgets[: settings.llm_max_attempts],
        start=1,
    ):
        output_text = ""
        response = None
        try:
            response = client.responses.create(
                model=settings.openai_model,
                reasoning={"effort": settings.llm_reasoning_effort},
                store=settings.llm_store,
                max_output_tokens=token_budget,
                input=[
                    {"role": "developer", "content": PROMPT_SPEC.developer_prompt},
                    {"role": "user", "content": payload_json},
                ],
                text={
                    "format": _make_openai_json_schema_strict(
                        "saju_free_preview",
                        _model_json_schema(FreePreviewLLMOutput),
                    )
                },
            )
            last_response_id = getattr(response, "id", "unknown")
            output_text = getattr(response, "output_text", "") or ""
            parsed = _parse_free_preview_output(output_text)
            attempts.append(
                InterpretationAttemptDiagnostic(
                    attempt_index=attempt_index,
                    mode="generate",
                    token_budget=token_budget,
                    status="success",
                    response_id=last_response_id,
                    output_chars=len(output_text),
                    output_excerpt=_clean_excerpt(output_text),
                )
            )
            duration_ms = int((time.perf_counter() - started) * 1000)
            return _build_openai_report(parsed), _make_diagnostics(
                final_provider="openai",
                payload_json=payload_json,
                duration_ms=duration_ms,
                attempts=attempts,
                final_response_id=last_response_id,
            )
        except JSONDecodeError as exc:
            fallback_reason = "json_decode_error"
            attempts.append(
                InterpretationAttemptDiagnostic(
                    attempt_index=attempt_index,
                    mode="generate",
                    token_budget=token_budget,
                    status="json_invalid",
                    response_id=last_response_id,
                    output_chars=len(output_text),
                    output_excerpt=_clean_excerpt(output_text),
                    error_type=type(exc).__name__,
                    error_message=_clean_error_message(exc),
                )
            )
        except ValidationError as exc:
            fallback_reason = "schema_validation_error"
            attempts.append(
                InterpretationAttemptDiagnostic(
                    attempt_index=attempt_index,
                    mode="generate",
                    token_budget=token_budget,
                    status="validation_error",
                    response_id=last_response_id,
                    output_chars=len(output_text),
                    output_excerpt=_clean_excerpt(output_text),
                    error_type=type(exc).__name__,
                    error_message=_clean_error_message(exc),
                )
            )
        except Exception as exc:  # pragma: no cover - network/provider failure path
            fallback_reason = "provider_request_failed"
            attempts.append(
                InterpretationAttemptDiagnostic(
                    attempt_index=attempt_index,
                    mode="generate",
                    token_budget=token_budget,
                    status="provider_error",
                    response_id=getattr(response, "id", None) if response is not None else None,
                    output_chars=len(output_text),
                    output_excerpt=_clean_excerpt(output_text),
                    error_type=type(exc).__name__,
                    error_message=_clean_error_message(exc),
                )
            )
            break

    duration_ms = int((time.perf_counter() - started) * 1000)
    return None, _make_diagnostics(
        final_provider="fallback",
        payload_json=payload_json,
        duration_ms=duration_ms,
        attempts=attempts,
        final_response_id=last_response_id,
        fallback_reason=fallback_reason,
    )


def _call_codex_free_preview(
    payload: InterpretationPayload,
) -> Tuple[FreePreviewReport | None, InterpretationDiagnostics]:
    payload_json = json.dumps(_model_dump_json(payload), ensure_ascii=False)
    started = time.perf_counter()
    try:
        result = call_codex_json(
            developer_prompt=PROMPT_SPEC.developer_prompt,
            user_payload=_model_dump_json(payload),
            output_schema=_model_json_schema(FreePreviewLLMOutput),
            schema_name="saju_free_preview",
            extra_instructions=(
                "Use only the supplied saju payload. Do not calculate new pillars, scores, or events.",
                "The response object must contain headline, hero_overview, core_diagnoses, and cards only.",
                "Write exactly 8 hero_overview sentences.",
                "Each core_diagnoses body must be at least 100 Korean characters.",
                "Use reading_plan: answer in user_takeaway; three preview_paragraphs in scene, tradeoff, action order.",
                "Every paragraph must add its own information role. Never pad length or invent timing/comparison data.",
                "Do not expose scores, internal ids, Hanja, or deterministic event guarantees.",
            ),
        )
        parsed = _parse_free_preview_output(result.output_text)
        attempt = InterpretationAttemptDiagnostic(
            attempt_index=1,
            mode="generate",
            token_budget=max(settings.llm_max_output_tokens, 1),
            status="success",
            response_id=result.response_id,
            output_chars=len(result.output_text),
            output_excerpt=_clean_excerpt(result.output_text),
        )
        return _build_provider_report(parsed, provider="codex"), _make_diagnostics(
            final_provider="codex",
            payload_json=payload_json,
            duration_ms=result.duration_ms,
            attempts=[attempt],
            final_response_id=result.response_id,
        )
    except JSONDecodeError as exc:
        fallback_reason = "json_decode_error"
        attempt = InterpretationAttemptDiagnostic(
            attempt_index=1,
            mode="generate",
            token_budget=max(settings.llm_max_output_tokens, 1),
            status="json_invalid",
            output_chars=0,
            error_type=type(exc).__name__,
            error_message=_clean_error_message(exc),
            issues=["json_decode_error"],
        )
    except ValidationError as exc:
        fallback_reason = "schema_validation_error"
        attempt = InterpretationAttemptDiagnostic(
            attempt_index=1,
            mode="generate",
            token_budget=max(settings.llm_max_output_tokens, 1),
            status="validation_error",
            output_chars=0,
            error_type=type(exc).__name__,
            error_message=_clean_error_message(exc),
        )
    except CodexProviderError as exc:
        fallback_reason = exc.reason
        attempt = InterpretationAttemptDiagnostic(
            attempt_index=1,
            mode="generate",
            token_budget=max(settings.llm_max_output_tokens, 1),
            status="provider_error",
            output_chars=0,
            output_excerpt=exc.stdout_excerpt or None,
            error_type=type(exc).__name__,
            error_message=_clean_error_message(exc),
            issues=[exc.reason],
        )
    except Exception as exc:
        fallback_reason = "provider_request_failed"
        attempt = InterpretationAttemptDiagnostic(
            attempt_index=1,
            mode="generate",
            token_budget=max(settings.llm_max_output_tokens, 1),
            status="provider_error",
            output_chars=0,
            error_type=type(exc).__name__,
            error_message=_clean_error_message(exc),
            issues=["codex_request_failed"],
        )

    return None, _make_diagnostics(
        final_provider="fallback",
        payload_json=payload_json,
        duration_ms=int((time.perf_counter() - started) * 1000),
        attempts=[attempt],
        fallback_reason=fallback_reason,
    )


def _call_codex_repair_free_preview(
    *,
    payload: InterpretationPayload,
    broken_report: FreePreviewReport,
    issues: Sequence[str],
    attempt_index: int,
) -> Tuple[FreePreviewReport | None, InterpretationAttemptDiagnostic]:
    try:
        result = call_codex_json(
            developer_prompt=PROMPT_SPEC.repair_prompt,
            user_payload={
                "payload": _model_dump_json(payload),
                "broken_output": _model_dump_json(broken_report),
                "validation_issues": list(issues),
            },
            output_schema=_model_json_schema(FreePreviewLLMOutput),
            schema_name="saju_free_preview_repair",
            extra_instructions=(
                "Fix only the validation issues. Keep the same schema and do not add commentary.",
                "For missing/short roles, restore the scene, tradeoff and action from reading_plan without repeating or padding advice.",
                "For first_screen_jargon issues, rewrite the affected first-screen text in plain everyday Korean.",
                "Avoid first-screen technical saju terms such as 일간, 월주, 일주, 십성, 정관, 편관, 재성, 식상, 인성, 비겁, 대운, 세운, 용신, 도화, 홍염.",
                "Do not expose scores, internal ids, Hanja, or deterministic event guarantees.",
            ),
        )
        parsed = _parse_free_preview_output(result.output_text)
        return (
            _build_provider_report(parsed, provider="codex"),
            InterpretationAttemptDiagnostic(
                attempt_index=attempt_index,
                mode="repair",
                token_budget=max(settings.llm_max_output_tokens, 1),
                status="success",
                response_id=result.response_id,
                output_chars=len(result.output_text),
                output_excerpt=_clean_excerpt(result.output_text),
            ),
        )
    except JSONDecodeError as exc:
        return None, InterpretationAttemptDiagnostic(
            attempt_index=attempt_index,
            mode="repair",
            token_budget=max(settings.llm_max_output_tokens, 1),
            status="json_invalid",
            output_chars=0,
            error_type=type(exc).__name__,
            error_message=_clean_error_message(exc),
            issues=["json_decode_error"],
        )
    except ValidationError as exc:
        return None, InterpretationAttemptDiagnostic(
            attempt_index=attempt_index,
            mode="repair",
            token_budget=max(settings.llm_max_output_tokens, 1),
            status="validation_error",
            output_chars=0,
            error_type=type(exc).__name__,
            error_message=_clean_error_message(exc),
        )
    except CodexProviderError as exc:
        return None, InterpretationAttemptDiagnostic(
            attempt_index=attempt_index,
            mode="repair",
            token_budget=max(settings.llm_max_output_tokens, 1),
            status="provider_error",
            output_chars=0,
            output_excerpt=exc.stdout_excerpt or None,
            error_type=type(exc).__name__,
            error_message=_clean_error_message(exc),
            issues=[exc.reason],
        )
    except Exception as exc:
        return None, InterpretationAttemptDiagnostic(
            attempt_index=attempt_index,
            mode="repair",
            token_budget=max(settings.llm_max_output_tokens, 1),
            status="provider_error",
            output_chars=0,
            error_type=type(exc).__name__,
            error_message=_clean_error_message(exc),
            issues=["codex_repair_failed"],
        )


def _collect_user_texts(report: FreePreviewReport) -> List[str]:
    texts = [report.headline, *report.hero_overview]
    for diagnosis in report.core_diagnoses:
        texts.extend([diagnosis.title, diagnosis.body])
    for card in report.cards:
        texts.extend(
            [
                card.title,
                card.subtitle,
                *card.chips,
                *card.preview_paragraphs,
                card.user_takeaway,
                card.next_question,
                card.basis_line,
            ]
        )
    return texts


def _collect_first_screen_plain_texts(report: FreePreviewReport) -> List[str]:
    texts = [report.headline, *report.hero_overview]
    for diagnosis in report.core_diagnoses:
        texts.append(diagnosis.body)
    for card in report.cards:
        texts.extend(
            [
                card.title,
                card.subtitle,
                *card.chips,
                *card.preview_paragraphs,
                card.user_takeaway,
                card.next_question,
            ]
        )
    return texts


def _collect_hero_and_card_preview_text(report: FreePreviewReport) -> str:
    chunks = [report.headline, *report.hero_overview]
    for card in report.cards:
        chunks.extend([card.title, *card.preview_paragraphs])
    return "\n".join(chunks)


def _is_generic_headline(headline: str) -> bool:
    normalized = re.sub(r"\s+", "", headline)
    return any(normalized == re.sub(r"\s+", "", item) for item in PROMPT_SPEC.generic_headlines)


def _contains_internal_value(text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in INTERNAL_VALUE_PATTERNS)


def _first_screen_jargon_terms(text: str) -> List[str]:
    return [term for term in PROMPT_SPEC.first_screen_jargon_terms if term in text]


def _overused_abstract_terms(report: FreePreviewReport) -> List[str]:
    text = _collect_hero_and_card_preview_text(report)
    overused: List[str] = []
    for term in PROMPT_SPEC.first_screen_abstract_terms:
        if text.count(term) > 4:
            overused.append(term)
    return overused


def _card_preview_text(card: FreePreviewCard) -> str:
    return "\n".join(card.preview_paragraphs).strip()


def _validate_free_preview_language(report: FreePreviewReport, payload: InterpretationPayload) -> List[str]:
    issues: List[str] = []
    for text in _collect_user_texts(report):
        if _is_ko(payload):
            if contains_hanja(text):
                issues.append("language:contains_hanja")
        else:
            if contains_hangul(text):
                issues.append("language:contains_hangul")
            if contains_hanja(text):
                issues.append("language:contains_hanja")
    return issues


def _validate_free_preview_report(report: FreePreviewReport, payload: InterpretationPayload) -> List[str]:
    issues: List[str] = []
    headline = report.headline.strip()
    if not headline:
        issues.append("headline:missing")
    elif _is_generic_headline(headline):
        issues.append("headline:generic")
    elif len(re.sub(r"\s+", "", headline)) < 8 or len(re.sub(r"\s+", "", headline)) > 48:
        issues.append("headline:length_out_of_range")

    if len(report.hero_overview) < MIN_HERO_SENTENCES:
        issues.append("hero_overview:too_few_sentences")
    if len(report.hero_overview) > MAX_HERO_SENTENCES:
        issues.append("hero_overview:too_many_sentences")

    diagnosis_keys = [item.key for item in report.core_diagnoses]
    if diagnosis_keys != list(DIAGNOSIS_KEYS):
        issues.append("core_diagnoses:unexpected_keys")
    for diagnosis in report.core_diagnoses:
        if len(diagnosis.body.strip()) < 80:
            issues.append(f"core_diagnoses.{diagnosis.key}:too_short")

    card_keys = [item.key for item in report.cards]
    if card_keys != list(CARD_KEYS):
        issues.append("cards:unexpected_keys")
    planned_topics = build_reading_plan(payload).sections
    for card in report.cards:
        preview_text = _card_preview_text(card)
        issues.extend(validate_reading_structure(card, payload))
        if len(set(part.strip() for part in card.preview_paragraphs)) != len(card.preview_paragraphs):
            issues.append(f"cards.{card.key}:duplicate_paragraph_role")
        if len(card.chips) < 3 or len(card.chips) > 5:
            issues.append(f"cards.{card.key}:invalid_chip_count")
        if len(card.preview_paragraphs) < 3:
            issues.append(f"cards.{card.key}:too_few_preview_paragraphs")
        if card.key in planned_topics and len(card.preview_paragraphs) != 3:
            issues.append(f"cards.{card.key}:reading_role_count_mismatch")
        if len(preview_text) < MIN_CARD_PREVIEW_CHARS:
            issues.append(f"cards.{card.key}:preview_too_short")
        if len(preview_text) > MAX_CARD_PREVIEW_CHARS:
            issues.append(f"cards.{card.key}:preview_too_long")
        if not card.user_takeaway.strip():
            issues.append(f"cards.{card.key}:missing_takeaway")
        if not card.next_question.strip():
            issues.append(f"cards.{card.key}:missing_next_question")
        if not card.basis_line.strip():
            issues.append(f"cards.{card.key}:missing_basis_line")

    for text in _collect_user_texts(report):
        issues.extend(unsupported_claim_issues(text))
        if _contains_internal_value(text):
            issues.append("internal_value_exposed_in_user_text")
        for phrase in PLACEHOLDER_USER_PHRASES:
            if phrase in text:
                issues.append(f"placeholder_phrase:{phrase}")
        for phrase in PROMPT_SPEC.validation_banned_phrases:
            if phrase in text:
                issues.append(f"banned_phrase:{phrase}")

    for text in _collect_first_screen_plain_texts(report):
        for term in _first_screen_jargon_terms(text):
            issues.append(f"first_screen_jargon:{term}")
    for term in _overused_abstract_terms(report):
        issues.append(f"abstract_term_overused:{term}")

    issues.extend(_validate_free_preview_language(report, payload))
    return sorted(set(issues), key=issues.index)


def _sanitize_codex_first_screen_jargon(report: FreePreviewReport) -> FreePreviewReport:
    data = _model_dump_json(report)

    def clean_text(value: str) -> str:
        cleaned = value
        for term in PROMPT_SPEC.first_screen_jargon_terms:
            cleaned = cleaned.replace(term, "")
        return re.sub(r"\s+", " ", cleaned).strip()

    data["headline"] = clean_text(data.get("headline", ""))
    data["hero_overview"] = [clean_text(item) for item in data.get("hero_overview", [])]
    for diagnosis in data.get("core_diagnoses", []):
        diagnosis["title"] = clean_text(diagnosis.get("title", ""))
        diagnosis["body"] = clean_text(diagnosis.get("body", ""))
    for card in data.get("cards", []):
        card["title"] = clean_text(card.get("title", ""))
        card["subtitle"] = clean_text(card.get("subtitle", ""))
        card["chips"] = [clean_text(item) for item in card.get("chips", [])]
        card["preview_paragraphs"] = [
            clean_text(item) for item in card.get("preview_paragraphs", [])
        ]
        card["user_takeaway"] = clean_text(card.get("user_takeaway", ""))
        card["next_question"] = clean_text(card.get("next_question", ""))
    return _model_validate(FreePreviewReport, data)


def generate_free_preview_report(
    *,
    payload: InterpretationPayload,
    trace_id: str,
    service_name: str,
) -> FreePreviewReport:
    started = time.perf_counter()
    payload_json = json.dumps(_model_dump_json(payload), ensure_ascii=False)
    fallback_report = build_fallback_free_preview_report(payload)

    if settings.llm_provider not in {"openai", "codex"}:
        diagnostics = _make_diagnostics(
            final_provider="fallback",
            payload_json=payload_json,
            duration_ms=int((time.perf_counter() - started) * 1000),
            fallback_reason="provider_not_openai",
        )
        fallback_report = _attach_diagnostics(
            fallback_report,
            diagnostics,
            warnings=["llm_provider_disabled"],
            provider="fallback",
        )
        log_stage(
            service=service_name,
            trace_id=trace_id,
            stage="free_preview_formatting",
            event="fallback_used",
            duration_ms=int((time.perf_counter() - started) * 1000),
            meta={"reason": "provider_not_openai"},
        )
        return fallback_report

    if settings.llm_provider == "codex":
        report, diagnostics = _call_codex_free_preview(payload)
    elif settings.openai_api_key in {"", PLACEHOLDER_OPENAI_API_KEY}:
        diagnostics = _make_diagnostics(
            final_provider="fallback",
            payload_json=payload_json,
            duration_ms=int((time.perf_counter() - started) * 1000),
            fallback_reason="missing_api_key",
        )
        fallback_report = _attach_diagnostics(
            fallback_report,
            diagnostics,
            warnings=["openai_api_key_missing"],
            provider="fallback",
        )
        log_stage(
            service=service_name,
            trace_id=trace_id,
            stage="free_preview_formatting",
            event="fallback_used",
            duration_ms=int((time.perf_counter() - started) * 1000),
            meta={"reason": "missing_api_key"},
        )
        return fallback_report
    else:
        report, diagnostics = _call_openai_free_preview(payload)
    if report is None:
        warnings = [diagnostics.fallback_reason or "openai_response_invalid"]
        fallback_report = _attach_diagnostics(
            fallback_report,
            diagnostics,
            warnings=warnings,
            provider="fallback",
        )
        log_stage(
            service=service_name,
            trace_id=trace_id,
            stage="free_preview_formatting",
            event="fallback_used",
            duration_ms=int((time.perf_counter() - started) * 1000),
            error_code="free_preview_generation_failed",
            meta={"reason": diagnostics.fallback_reason or "openai_response_invalid"},
        )
        return fallback_report

    if settings.llm_provider == "codex":
        report = _sanitize_codex_first_screen_jargon(report)

    issues = _validate_free_preview_report(report, payload)
    if issues:
        if settings.llm_provider == "codex":
            repaired_report, repair_attempt = _call_codex_repair_free_preview(
                payload=payload,
                broken_report=report,
                issues=issues,
                attempt_index=len(diagnostics.attempts) + 1,
            )
            diagnostics = _model_copy(
                diagnostics,
                update={
                    "attempts": [*diagnostics.attempts, repair_attempt],
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                },
            )
            if repaired_report is not None:
                repaired_report = _sanitize_codex_first_screen_jargon(repaired_report)
                repaired_issues = _validate_free_preview_report(repaired_report, payload)
                if not repaired_issues:
                    repaired_report.question_capabilities = fallback_report.question_capabilities
                    repaired_report = _attach_diagnostics(
                        repaired_report,
                        diagnostics,
                        provider="codex",
                    )
                    log_stage(
                        service=service_name,
                        trace_id=trace_id,
                        stage="free_preview_formatting",
                        event="formatted",
                        duration_ms=int((time.perf_counter() - started) * 1000),
                        meta={
                            "provider": "codex",
                            "response_id": diagnostics.final_response_id,
                            "prompt_version": PROMPT_SPEC.version,
                        },
                    )
                    return repaired_report
                issues = repaired_issues

        diagnostics = _model_copy(
            diagnostics,
            update={
                "final_provider": "fallback",
                "fallback_reason": "validation_failed",
                "validation_issues": issues,
            },
        )
        fallback_report = _attach_diagnostics(
            fallback_report,
            diagnostics,
            warnings=issues,
            provider="fallback",
        )
        log_stage(
            service=service_name,
            trace_id=trace_id,
            stage="free_preview_formatting",
            event="fallback_used",
            duration_ms=int((time.perf_counter() - started) * 1000),
            meta={"reason": "validation_failed", "issues": issues},
        )
        return fallback_report

    final_provider = diagnostics.final_provider
    report.question_capabilities = fallback_report.question_capabilities
    report = _attach_diagnostics(report, diagnostics, provider=final_provider)
    log_stage(
        service=service_name,
        trace_id=trace_id,
        stage="free_preview_formatting",
        event="formatted",
        duration_ms=int((time.perf_counter() - started) * 1000),
        meta={
            "provider": final_provider,
            "response_id": diagnostics.final_response_id,
            "prompt_version": PROMPT_SPEC.version,
        },
    )
    return report
