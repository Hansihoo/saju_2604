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
)
from app.domain.saju.llm_payload import InterpretationPayload
from app.domain.saju.localization import contains_hangul, contains_hanja
from app.domain.saju.prompts.free_preview_report import get_free_preview_report_prompt
from app.domain.saju.services.codex_provider import CodexProviderError, call_codex_json

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - import guard for local test envs
    OpenAI = None


PROMPT_SPEC = get_free_preview_report_prompt()
MIN_HERO_SENTENCES = 7
MAX_HERO_SENTENCES = 9
MIN_CARD_PREVIEW_CHARS = 480
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
            "warnings": list(warnings or []),
            "diagnostics": diagnostics,
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


def _dominant_strength_phrase(payload: InterpretationPayload) -> str:
    if not _is_ko(payload):
        return "quickly read a situation, organize priorities, and move with clear standards"

    phrases = {
        "wood": "유연하게 넓히고 가능성을 찾아가는 힘",
        "fire": "빠르게 반응하고 표현하는 힘",
        "earth": "현실을 붙잡고 안정적으로 정리하는 힘",
        "metal": "필요한 것과 아닌 것을 골라내는 힘",
        "water": "상황을 읽고 조율하는 힘",
    }
    values = [
        phrases[item]
        for item in payload.signals.dominant_elements
        if item in phrases
    ]
    return _join(values[:2], fallback="상황을 파악하고 필요한 일을 정리하는 힘")


def _support_need_phrase(payload: InterpretationPayload) -> str:
    if not _is_ko(payload):
        return "the parts that need routine and environmental support"

    phrases = {
        "wood": "유연하게 넓히는 힘",
        "fire": "표현하고 활기를 되살리는 힘",
        "earth": "생활을 안정시키고 중심을 잡는 힘",
        "metal": "경계를 세우고 끝맺는 힘",
        "water": "상황을 읽고 조율하는 힘",
    }
    values = [
        phrases[item]
        for item in payload.signals.missing_elements
        if item in phrases
    ]
    return _join(values[:2], fallback="회복 루틴과 주변 환경")


def _diagnoses_ko(payload: InterpretationPayload) -> List[FreePreviewDiagnosis]:
    strength = _dominant_strength_phrase(payload)
    support_need = _support_need_phrase(payload)
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
                "지금은 새 일을 크게 벌리기보다 나를 계속 소모시키는 선택을 줄이는 일이 중요합니다. "
                "생활 리듬과 돈 쓰는 습관, 사람을 대하는 거리를 조금씩 가볍게 만들면 다음 변화 앞에서 덜 흔들릴 수 있습니다."
            ),
        ),
    ]


def _diagnoses_en(payload: InterpretationPayload) -> List[FreePreviewDiagnosis]:
    current_cycle = _cycle_name(payload, "current")
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
                f"The current period is shaped by {current_cycle}, so the practical task is to organize standards rather than expand everything at once. "
                "The routines built now can make the next cycle easier to use."
            ),
        ),
    ]


def _cards_ko(payload: InterpretationPayload) -> List[FreePreviewCard]:
    now_actions = _join(payload.luck_flow_facts.now_action_tags[:4], fallback="관계 거리 조절, 지출 점검, 생활 루틴")
    limitation = (
        "출생시간이 추정값이라 시간에 따라 달라지는 세부 판단은 조금 보수적으로 보는 편이 좋습니다. "
        if payload.profile.is_birth_time_estimated
        else ""
    )
    return [
        FreePreviewCard(
            key="core",
            title="괜찮다고 말해도 마음속 계산이 많은 타입",
            subtitle="혼자 판단하고 혼자 지치는 패턴",
            chips=["속마음 계산", "책임 범위", "피로 지점", "생활 리듬"],
            preview_paragraphs=[
                "겉으로는 꽤 담담해 보여도 안에서는 상황을 계속 계산하는 편입니다. 해야 할 일과 아닌 일을 스스로 나누려 하기 때문에, 다른 사람이 흘려보낸 작은 변화도 내 안에서는 이미 할 일의 목록으로 바뀌기 쉽습니다.",
                "맞는 환경에서는 처리 속도가 빨라지고 책임감도 선명해집니다. 이때는 기대받는 만큼 더 잘하려는 마음이 커져서, 쉬는 순간에도 머리가 쉽게 꺼지지 않고 쉬어도 쉰 것 같지 않은 날이 생깁니다.",
                f"문제는 지치는 순간에도 티를 늦게 낸다는 점입니다. {limitation}특히 부탁을 거절하지 못한 일이 쌓이면, 어느 날 갑자기 거리 두기나 침묵으로 반응할 수 있고 그 침묵은 무심함보다 과부하에 가깝습니다.",
                "지금 살펴볼 포인트는 내가 편해지는 자리와 금방 소모되는 자리를 구분하는 것입니다. 내가 잘하는 방식과 계속 버티게 되는 방식을 구분하면, 같은 노력도 훨씬 덜 무겁고 오래 가는 힘은 부담을 나누는 방식에서 나오며, 이 감각이 잡히면 관계와 일에서 스스로를 덜 몰아붙이게 됩니다.",
            ],
            user_takeaway="지금 필요한 건 더 많이 버티는 힘이 아니라, 어디까지 맡을지 알아차리는 감각입니다.",
            next_question="왜 어떤 자리에서는 잘해내는데, 어떤 자리에서는 금방 지칠까요?",
            basis_line="성향 구조, 오행 균형, 현재 시기 신호를 함께 봤습니다.",
        ),
        FreePreviewCard(
            key="work_money",
            title="일은 잘하는데 왜 피로가 먼저 쌓일까?",
            subtitle="성과보다 먼저 봐야 할 새는 지점",
            chips=["역할 피로", "돈의 체감", "새는 지점", "남는 결과"],
            preview_paragraphs=[
                "일에서는 능력이 없는 쪽이 아니라, 애매한 역할을 오래 맡을 때 피로가 커지는 쪽에 가깝습니다. 무엇을 해내야 하는지가 분명하면 속도와 책임감이 함께 살아나지만, 누가 결정하고 어디까지 맡는지가 흐리면 에너지가 빠르게 빠집니다.",
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
            title="좋아해도 쉽게 기대지 못하는 이유",
            subtitle="설렘보다 반복되는 태도를 보는 관계",
            chips=["느린 신뢰", "약속의 무게", "표현 속도", "편한 거리"],
            preview_paragraphs=[
                "관계에서는 마음이 없는 게 아니라, 쉽게 기대기 전까지 오래 관찰하는 편입니다. 말보다 반복되는 태도와 약속을 지키는 방식을 보고 마음을 여는 쪽이라, 시간이 지나도 태도가 크게 달라지지 않는 사람에게 안심하기 쉽습니다.",
                "처음의 설렘이 커도 생활 리듬이 맞지 않으면 금방 피곤해질 수 있습니다. 관계가 안정되려면 좋아하는 감정만큼 서로의 하루를 방해하지 않는 방식도 중요하고, 작은 약속이 지켜질 때 마음이 천천히 깊어집니다.",
                "주의할 점은 혼자 괜찮은 척하다가 서운함을 늦게 꺼내는 패턴입니다. 작게 말하지 못한 감정은 나중에 한꺼번에 무겁게 터질 수 있고, 그때는 상대가 아니라 나도 내 감정을 늦게 알아차린 것일 수 있습니다.",
                "지금 보면 좋은 것은 누가 더 끌리는가보다 누구와 있을 때 내 생활이 무너지지 않는가입니다. 나를 불안하게 만드는 설렘과 편안하게 만드는 애정을 구분하면 관계 선택이 훨씬 선명해지고, 감정이 편안하게 머무는 자리가 오래 남습니다.",
            ],
            user_takeaway="마음이 깊어지는 속도보다, 함께 있을 때 내가 덜 무너지는지가 더 오래 남습니다.",
            next_question="왜 어떤 관계에서는 편한데, 어떤 관계에서는 금방 지칠까요?",
            basis_line="관계 성향과 현재 시기의 변화를 함께 봤습니다.",
        ),
        FreePreviewCard(
            key="luck_flow",
            title="지금은 넓히는 때보다 덜어내는 때입니다",
            subtitle="지금 시기와 다음 변화",
            chips=["덜어낼 것", "생활 패턴", "다음 변화", "감정 소모"],
            preview_paragraphs=[
                "지금은 많은 것을 새로 벌이기보다, 나를 계속 피곤하게 만드는 선택을 줄여야 하는 때에 가깝습니다. 새로운 일을 전부 막으라는 뜻이 아니라, 이미 무거운 것 위에 또 얹지 않는 선택이 필요하고 지금의 피로를 모른 척하면 다음 선택도 비슷한 무게로 시작될 수 있습니다.",
                f"생활에서는 작은 약속을 지키는 힘이 중요합니다. {now_actions} 같은 행동이 쌓이면 다음 변화 앞에서 덜 흔들릴 수 있고, 하루를 망가뜨리는 습관 하나만 줄여도 마음의 여유가 돌아올 수 있습니다.",
                "주의할 점은 불안해서 더 많이 붙잡는 패턴입니다. 특히 책임감 때문에 놓지 못한 일은 실제보다 더 크게 느껴질 수 있고, 내려놓는 일이 실패처럼 보여도 실제로는 에너지를 되찾는 과정일 수 있습니다.",
                "지금 볼 것은 운이 좋고 나쁨이 아니라 무엇을 남기고 무엇을 내려놓을지입니다. 가벼워진 자리에서 새 선택이 들어올 공간도 생기고, 작아 보이는 선택이 앞으로의 속도를 바꿉니다.",
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
    now_actions = _join(payload.luck_flow_facts.now_action_tags[:4], fallback="relationship sorting, spending review, daily routines")
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


def build_fallback_free_preview_report(payload: InterpretationPayload) -> FreePreviewReport:
    if _is_ko(payload):
        headline = "괜찮다고 말하지만 혼자 많이 계산하는 사람"
        hero_overview = [
            "겉으로는 괜찮아 보여도 속으로는 이미 여러 경우의 수를 계산하고 있을 가능성이 큽니다.",
            "사람이나 일을 쉽게 믿기보다, 반복되는 태도와 결과를 보고 마음을 여는 편입니다.",
            "강점은 급한 상황에서도 해야 할 일과 미뤄도 되는 일을 빨리 가르는 감각입니다.",
            "다만 역할이 애매하거나 책임이 계속 얹히면 말없이 버티다가 갑자기 지칠 수 있습니다.",
            "지금은 더 많이 벌이기보다 나를 계속 소모시키는 선택을 줄이는 쪽이 중요합니다.",
            "관계에서는 설렘보다 약속을 지키는 태도와 생활 리듬이 오래 남습니다.",
            "일과 돈에서는 열심히 하는 양보다 어떤 일이 실제 보상으로 이어지는지가 핵심입니다.",
            "지금은 내가 편해지는 선택과 반복해서 피곤해지는 선택을 구분해서 보는 것이 좋습니다.",
        ]
        diagnoses = _diagnoses_ko(payload)
        cards = _cards_ko(payload)
    else:
        headline = "A steady builder of clear standards"
        current_cycle = _cycle_name(payload, "current")
        next_cycle = _cycle_name(payload, "next")
        hero_overview = [
            "This chart becomes stronger when clear standards are in place.",
            f"The main strength is the ability to respond and organize through the {_element_text(payload)} side of the chart.",
            "The repeating pattern is strong focus in a fitting environment and faster fatigue when standards are unclear.",
            f"The current period is influenced by {current_cycle}, making it useful to reorganize work, money, and relationship standards.",
            "The caution is that speed without structure can increase spending pressure and relationship strain.",
            "The best use of the chart is to turn strengths into results while supporting weaker parts through routine.",
            "In relationships, daily rhythm and responsibility matter more than quick certainty.",
            "In work and money, output, responsibility, and management rules become connected.",
            f"The next flow moves toward {next_cycle}, so the standards built now can make later choices clearer.",
        ]
        diagnoses = _diagnoses_en(payload)
        cards = _cards_en(payload)

    return FreePreviewReport(
        provider="fallback",
        model="fallback",
        prompt_version=PROMPT_SPEC.version,
        headline=headline,
        hero_overview=hero_overview,
        core_diagnoses=diagnoses,
        cards=cards,
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
        cards=parsed.cards,
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
                "Each card must have 4 preview_paragraphs. The combined preview_paragraphs text for each card must be between 760 and 1200 Korean characters.",
                "Each preview paragraph should be 190 to 260 Korean characters. If any card has less than 760 Korean characters in preview_paragraphs, the answer is invalid.",
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
                "For cards.*:preview_too_short, expand that card to 4 preview_paragraphs with 190 to 260 Korean characters each.",
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
    for card in report.cards:
        preview_text = _card_preview_text(card)
        if len(card.chips) < 3 or len(card.chips) > 5:
            issues.append(f"cards.{card.key}:invalid_chip_count")
        if len(card.preview_paragraphs) < 3:
            issues.append(f"cards.{card.key}:too_few_preview_paragraphs")
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
        if _contains_internal_value(text):
            issues.append("internal_value_exposed_in_user_text")
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
