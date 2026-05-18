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

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - import guard for local test envs
    OpenAI = None


PROMPT_SPEC = get_free_preview_report_prompt()
MIN_HERO_SENTENCES = 8
MAX_HERO_SENTENCES = 10
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
        model=settings.openai_model if settings.llm_provider == "openai" else None,
        prompt_version=PROMPT_SPEC.version,
        payload_chars=len(payload_json),
        duration_ms=duration_ms,
        final_response_id=final_response_id,
        fallback_reason=fallback_reason,
        validation_issues=list(validation_issues or []),
        attempts=list(attempts or []),
    )


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
            "model": settings.openai_model if provider == "openai" else "fallback",
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


def _diagnoses_ko(payload: InterpretationPayload) -> List[FreePreviewDiagnosis]:
    current_cycle = _cycle_name(payload, "current")
    return [
        FreePreviewDiagnosis(
            key="strongest_point",
            title="가장 강한 점",
            body=(
                f"이 사주는 {payload.day_master} 일간을 중심으로 { _element_text(payload) } 쪽의 반응이 잘 살아납니다. "
                "상황을 빠르게 읽고 기준을 세우면, 해야 할 일과 미뤄도 되는 일을 비교적 선명하게 나누는 힘이 있습니다."
            ),
        ),
        FreePreviewDiagnosis(
            key="repeating_pattern",
            title="반복되는 패턴",
            body=(
                f"반복되는 패턴은 강한 부분으로 속도를 내다가 {_missing_element_text(payload)} 쪽 보완이 늦어질 때 피로가 쌓인다는 점입니다. "
                "일, 돈, 관계의 기준이 한꺼번에 섞이면 판단이 급해질 수 있어 순서를 나누는 편이 좋습니다."
            ),
        ),
        FreePreviewDiagnosis(
            key="current_task",
            title="지금 시기 과제",
            body=(
                f"현재는 {current_cycle} 대운의 영향을 받는 시기라 새 일을 크게 벌리기보다 기준을 정리하는 일이 중요합니다. "
                "지금 만든 생활 리듬과 선택 기준이 다음 흐름에서 더 분명한 판단으로 이어질 수 있습니다."
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
    current_cycle = _cycle_name(payload, "current")
    next_cycle = _cycle_name(payload, "next")
    current_period = _period_text(payload, "current")
    next_period = _period_text(payload, "next")
    love_stars = _star_text(payload, payload.love_facts.active_star_labels)
    career_stars = _star_text(payload, payload.career_facts.active_star_labels)
    wealth_stars = _star_text(payload, payload.wealth_facts.active_star_labels)
    now_actions = _join(payload.luck_flow_facts.now_action_tags[:4], fallback="관계 정리, 지출 점검, 생활 루틴")
    limitation = (
        "출생시간이 추정값이라 시간 기둥과 관련된 해석은 보수적으로 보아야 합니다. "
        if payload.profile.is_birth_time_estimated
        else ""
    )
    return [
        FreePreviewCard(
            key="core",
            title="내 사주 특징",
            subtitle="성향, 강점, 반복되는 패턴",
            chips=["기준", "강점", "반복 패턴", "생활 리듬"],
            preview_paragraphs=[
                f"이 사주는 {payload.day_master} 일간을 중심으로 자기 기준이 분명해질수록 힘이 살아나는 타입입니다. { _element_text(payload) } 쪽 신호가 두드러져 빠르게 반응하고 정리하는 장점이 있지만, {_missing_element_text(payload)} 쪽은 생활 속에서 의식적으로 보완할 필요가 있습니다.",
                "평균적으로 무난하게 넓게 퍼지는 사주라기보다, 맞는 자리와 맞지 않는 자리가 비교적 선명하게 갈리는 편입니다. 환경이 맞으면 집중력이 빨리 살아나고, 스스로 해야 할 일의 순서를 잡는 힘도 좋아집니다.",
                f"다만 기준이 흐려진 상태에서 오래 버티면 장점이 고집이나 과한 몰입처럼 보일 수 있습니다. {limitation}이 사주는 강한 부분을 성과로 쓰되, 약한 부분은 루틴과 주변 환경으로 보완할 때 가장 안정적으로 작동합니다.",
                "무료 리포트에서 가장 먼저 볼 부분은 이 사람이 어떤 선택 방식으로 편해지고 지치는지입니다. 스스로 납득되는 기준을 찾으면 관계, 일, 돈의 판단이 덜 흔들리고, 반대로 기준이 없을 때는 작은 일도 크게 소모될 수 있습니다. 그래서 강점을 쓰는 방식만큼 회복하는 방식도 함께 봐야 합니다.",
            ],
            user_takeaway="지금 필요한 것은 더 많은 선택지가 아니라 오래 유지할 수 있는 기준을 먼저 세우는 일입니다.",
            next_question="내 강점을 일과 관계에서 어떻게 다르게 써야 할까요?",
            basis_line="일간, 오행 균형, 십성 구조, 현재 대운을 함께 반영했습니다.",
        ),
        FreePreviewCard(
            key="work_money",
            title="일과 돈의 흐름",
            subtitle="일하는 방식과 돈이 쌓이는 구조",
            chips=["일하는 방식", "수입 구조", "관리 포인트", "새는 지점"],
            preview_paragraphs=[
                f"일에서는 {payload.career_facts.month_pillar_label}와 {payload.career_facts.month_stem_ten_god} 신호가 보여 주듯, 역할과 기준이 분명할수록 실력이 잘 드러나는 편입니다. {career_stars} 같은 보조 신호는 문서화, 학습, 정리, 신뢰를 만드는 방식과 잘 연결됩니다.",
                "돈의 흐름은 일을 통해 만든 결과물과 책임이 수입의 단서가 되는 구조에 가깝습니다. 한 번에 크게 키우는 방식보다 들어온 흐름을 남기고 지키는 기준이 중요하며, 관계 비용이나 급한 선택이 지출로 이어지는지 점검하는 편이 좋습니다.",
                f"금전 쪽에서는 {wealth_stars} 흐름을 참고하되, 수익을 단정하기보다 관리 방식에 초점을 두어야 합니다. 일에서 결과물, 생산성, 역할이 분명해질수록 돈의 흐름도 이해하기 쉬워지고, 지금은 지출 규칙과 반복 수입의 기반을 정리하기 좋은 시기입니다.",
                "일과 돈을 따로 보면 방향이 흐려질 수 있습니다. 어떤 업무가 신뢰를 만들고, 어떤 결과물이 다시 기회로 이어지며, 어떤 지출이 마음의 부담으로 남는지를 함께 보면 지금의 선택 기준이 훨씬 현실적으로 정리됩니다.",
            ],
            user_takeaway="일의 기준과 돈의 기준을 따로 보지 말고, 어떤 결과물이 수입으로 이어지는지부터 정리하세요.",
            next_question="지금 직장이나 일의 방향을 바꿔도 괜찮을까요?",
            basis_line="직장운과 금전운을 연결해서 해석했습니다.",
        ),
        FreePreviewCard(
            key="love",
            title="연애와 결혼 흐름",
            subtitle="관계 스타일과 장기 관계 성향",
            chips=["관계 스타일", "잘 맞는 상대", "장기 관계", "현재 조언"],
            preview_paragraphs=[
                f"관계에서는 빠른 확정보다 오래 유지될 수 있는 기준이 더 중요하게 보입니다. {payload.love_facts.spouse_house_label}과 {payload.love_facts.partner_star_label} 신호는 끌림 자체보다 실제 생활 리듬과 책임감이 맞는지를 보게 합니다.",
                f"{love_stars} 같은 보조 신호는 매력이나 사회적 주목을 뜻하는 참고 자료로만 보는 편이 안전합니다. 호감이 생기는 속도와 관계가 깊어지는 속도는 다를 수 있으므로, 상대의 말보다 반복되는 태도와 약속을 지키는 방식을 보는 것이 좋습니다.",
                f"현재 {current_cycle} 구간에서는 관계를 넓히는 일보다 마음이 덜 소모되는 관계 기준을 정리하는 쪽이 더 현실적입니다. 장기 관계는 결과를 단정하기보다 서로의 생활 방식과 책임의 균형이 맞을 때 안정적으로 이어질 가능성이 커집니다.",
                "이 리포트는 특정 사람과의 결과를 정해 주는 방식이 아니라, 내가 어떤 관계에서 편안하고 어떤 관계에서 금방 지치는지를 보여 주는 데 초점을 둡니다. 그래서 관계를 볼 때는 설렘의 크기와 함께 대화의 안정감, 생활 리듬, 책임의 균형을 같이 보는 편이 좋습니다.",
            ],
            user_takeaway="관계의 답을 빨리 정하려 하기보다, 함께 있을 때 생활이 안정되는 사람인지 확인하세요.",
            next_question="나와 오래 맞는 사람은 어떤 관계 패턴을 가진 사람일까요?",
            basis_line="배우자궁, 관계 신호, 현재 흐름을 함께 봅니다.",
        ),
        FreePreviewCard(
            key="luck_flow",
            title="현재 운과 대운 흐름",
            subtitle="지금 시기와 다음 변화",
            chips=["현재 시기", "다음 변화", "준비할 것", "선택 기준"],
            preview_paragraphs=[
                f"현재는 {current_period}의 {current_cycle} 구간을 기준으로 보며, 사건이 정해진 시기라기보다 선택 기준을 다듬는 시간에 가깝습니다. 지금은 {now_actions} 같은 실제 행동을 통해 다음 선택의 기반을 만드는 일이 중요합니다.",
                f"다음 흐름은 {next_period}의 {next_cycle} 구간으로 이어집니다. 지금 만든 기준과 루틴이 다음 시기에 역할, 관계, 돈의 판단을 더 선명하게 만드는 데 도움을 줄 수 있습니다.",
                "대운은 어떤 일이 확정된다는 뜻이 아니라, 어떤 태도와 선택이 더 잘 작동하는지를 보는 시간표입니다. 지금은 속도를 내기보다 정리하고, 관계와 일과 돈의 경계를 나누며, 반복 가능한 생활 기준을 만드는 쪽이 유리합니다.",
                "특히 현재 흐름에서는 감정이 올라올 때 바로 결론을 내리기보다, 내가 계속 유지할 수 있는 선택인지 확인하는 태도가 중요합니다. 다음 시기를 잘 쓰려면 지금부터 생활 루틴, 지출 규칙, 관계의 경계를 작게라도 정리해 두는 것이 도움이 됩니다.",
            ],
            user_takeaway="현재 운은 결과를 기다리는 시간이 아니라 다음 변화를 받기 위한 기준을 만드는 시간입니다.",
            next_question="다음 대운을 잘 쓰려면 지금 무엇을 준비해야 할까요?",
            basis_line="현재 대운과 다음 대운의 변화를 중심으로 봅니다.",
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
        headline = "기준을 세우고 오래 밀고 가는 사람"
        current_cycle = _cycle_name(payload, "current")
        next_cycle = _cycle_name(payload, "next")
        hero_overview = [
            "이 사주는 기준이 분명해질수록 힘이 살아나는 사람으로 읽습니다.",
            f"강점은 { _element_text(payload) } 쪽 신호처럼 빠르게 반응하고 필요한 일을 정리하는 힘입니다.",
            "반복되는 패턴은 맞는 환경에서는 몰입이 살아나지만 기준이 흐려지면 피로가 먼저 커진다는 점입니다.",
            f"현재는 {current_cycle} 구간의 영향을 받는 시기라 관계와 일과 돈의 기준을 다시 정리하는 의미가 큽니다.",
            "주의할 점은 속도만 믿고 움직이면 지출과 관계 부담이 함께 커질 수 있다는 것입니다.",
            "잘 쓰는 방향은 강한 부분을 성과에 쓰고 약한 부분은 루틴과 환경으로 보완하는 것입니다.",
            "관계에서는 빠른 확정보다 오래 유지될 수 있는 생활 기준을 확인하는 편이 좋습니다.",
            "일과 돈에서는 결과물, 책임, 관리 기준이 서로 이어질 때 안정감이 커질 수 있습니다.",
            f"다음 흐름은 {next_cycle} 구간으로 이어지므로 지금 만든 기준이 나중의 선택을 더 선명하게 만들 수 있습니다.",
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
    return FreePreviewReport(
        provider="openai",
        model=settings.openai_model,
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

    client = OpenAI(api_key=settings.openai_api_key)
    token_budgets = [
        max(4200, min(settings.llm_max_output_tokens, 6000)),
        max(5200, min(settings.llm_max_output_tokens * 2, 8000)),
    ]
    attempts: List[InterpretationAttemptDiagnostic] = []
    started = time.perf_counter()
    last_response_id: str | None = None
    fallback_reason = "openai_response_invalid"

    for attempt_index, token_budget in enumerate(token_budgets, start=1):
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


def _is_generic_headline(headline: str) -> bool:
    normalized = re.sub(r"\s+", "", headline)
    return any(normalized == re.sub(r"\s+", "", item) for item in PROMPT_SPEC.generic_headlines)


def _contains_internal_value(text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in INTERNAL_VALUE_PATTERNS)


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

    issues.extend(_validate_free_preview_language(report, payload))
    return sorted(set(issues), key=issues.index)


def generate_free_preview_report(
    *,
    payload: InterpretationPayload,
    trace_id: str,
    service_name: str,
) -> FreePreviewReport:
    started = time.perf_counter()
    payload_json = json.dumps(_model_dump_json(payload), ensure_ascii=False)
    fallback_report = build_fallback_free_preview_report(payload)

    if settings.llm_provider != "openai":
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

    if settings.openai_api_key in {"", PLACEHOLDER_OPENAI_API_KEY}:
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

    issues = _validate_free_preview_report(report, payload)
    if issues:
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

    report = _attach_diagnostics(report, diagnostics, provider="openai")
    log_stage(
        service=service_name,
        trace_id=trace_id,
        stage="free_preview_formatting",
        event="formatted",
        duration_ms=int((time.perf_counter() - started) * 1000),
        meta={
            "provider": "openai",
            "response_id": diagnostics.final_response_id,
            "prompt_version": PROMPT_SPEC.version,
        },
    )
    return report
