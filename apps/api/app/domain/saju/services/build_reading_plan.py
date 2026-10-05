"""Apply bounded, versioned project policies to supplied facts; never predict events."""

import json
import re
from string import Formatter
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Tuple

from app.domain.saju.localization import TEN_GOD_ENGLISH, localize_ten_god
from app.domain.saju.pydantic_compat import model_to_dict, model_validate_compat
from app.domain.saju.reading_knowledge import (
    KnowledgeBundle, QuestionCapability, ReadingAnalysisNote, ReadingBlock, ReadingFact, ReadingPlan,
    ReadingStructure,
)

if TYPE_CHECKING:
    from app.domain.saju.llm_payload import InterpretationPayload

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "reading_knowledge" / "catalog.json"
ROLE_ORDER = ("answer", "scene", "tradeoff", "action")
ROLE_KIND = {"answer": "interpretation", "scene": "illustration", "tradeoff": "interpretation", "action": "advice"}
FEATURE_TOPICS = {"love.spouse_house_ten_god": "love", "career.month_stem_ten_god": "work_money",
                  "core.dominant_element": "core", "luck.current_stem_ten_god": "luck_flow"}
FEATURE_EXCLUSIONS = {
    "love.spouse_house_ten_god": {"missing_or_unrecognized_fact", "critical_calculation_uncertainty"},
    "career.month_stem_ten_god": {"missing_or_unrecognized_fact", "critical_calculation_uncertainty"},
    "core.dominant_element": {"missing_or_inconsistent_element_counts", "critical_calculation_uncertainty"},
    "luck.current_stem_ten_god": {"unknown_birth_time", "disabled_luck_flow", "missing_confirmed_current_cycle", "critical_calculation_uncertainty"},
}
NOTE_FIELDS = {
    "love.spouse_house_ten_god": {"feature_label"},
    "career.month_stem_ten_god": {"feature_label"},
    "core.dominant_element": {"dominant_label"},
    "luck.current_stem_ten_god": {"period", "feature_label"},
}
ELEMENT_LABELS = {"ko": dict(zip(("wood", "fire", "earth", "metal", "water"), ("목", "화", "토", "금", "수"))),
                  "en": dict(zip(("wood", "fire", "earth", "metal", "water"), ("Wood", "Fire", "Earth", "Metal", "Water")))}


def load_reading_knowledge(path: Path = CATALOG_PATH) -> KnowledgeBundle:
    bundle = model_validate_compat(KnowledgeBundle, json.loads(path.read_text(encoding="utf-8")))
    for values, name in ((bundle.sources, "source"), (bundle.rules, "rule"), (bundle.questions, "question")):
        ids = [item.id for item in values]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate reading knowledge " + name)
    sources = {source.id for source in bundle.sources}
    matches = set()
    for rule in bundle.rules:
        if rule.source_id not in sources:
            raise ValueError("reading rule source is missing: " + rule.id)
        if set(rule.wording) != {"ko", "en"}:
            raise ValueError("reading rule needs both locales: " + rule.id)
        if rule.topic != FEATURE_TOPICS[rule.feature] or set(rule.exclusions) != FEATURE_EXCLUSIONS[rule.feature]:
            raise ValueError("reading rule feature or exclusion contract is unsupported: " + rule.id)
        for wording in rule.wording.values():
            for role in (*ROLE_ORDER, "analysis_note"):
                parts = list(Formatter().parse(getattr(wording, role)))
                fields = {field for _, field, _, _ in parts if field is not None}
                allowed = NOTE_FIELDS[rule.feature] if role == "analysis_note" else (
                    {"period"} if rule.feature == "luck.current_stem_ten_god" else set())
                if not fields <= allowed or any(spec or conversion for _, _, spec, conversion in parts):
                    raise ValueError("unsupported reading placeholder: " + rule.id)
        if rule.status != "active_project_policy":
            continue
        for value in rule.any_of:
            match = (rule.topic, rule.feature, value)
            if match in matches:
                raise ValueError("ambiguous reading rules: " + rule.id)
            matches.add(match)
    if any(set(policy.question) != {"ko", "en"} for policy in bundle.questions):
        raise ValueError("reading question needs both locales")
    return bundle


def _canonical_ten_god(label: str) -> str:
    return {value: key for key, value in TEN_GOD_ENGLISH.items()}.get(label, localize_ten_god(label, "ko"))


def _fact(id: str, value: str, path: str) -> ReadingFact:
    return ReadingFact(id=id, value=value, source_path=path)


def _features(payload: "InterpretationPayload") -> Dict[str, Tuple[str, List[ReadingFact]]]:
    if any(flag.severity == "critical" for flag in payload.uncertainty_summary):
        return {}
    result = {}
    for feature, label, path in (
        ("love.spouse_house_ten_god", payload.love_facts.spouse_house_ten_god, "love_facts.spouse_house_ten_god"),
        ("career.month_stem_ten_god", payload.career_facts.month_stem_ten_god, "career_facts.month_stem_ten_god"),
    ):
        if label.strip():
            result[feature] = (_canonical_ten_god(label), [_fact(feature, label, path)])
    dominant = payload.signals.dominant_elements
    counts = payload.element_counts
    valid_counts = (set(counts) == {"wood", "fire", "earth", "metal", "water"} and
                    all(count >= 0 for count in counts.values()) and max(counts.values(), default=0) > 0)
    expected_dominant = {element for element, count in counts.items() if count == max(counts.values(), default=0)}
    if dominant and valid_counts and len(dominant) == len(set(dominant)) and set(dominant) == expected_dominant:
        result["core.dominant_element"] = (
            dominant[0] if len(dominant) == 1 else "mixed",
            [_fact("core.dominant_elements", ", ".join(dominant), "signals.dominant_elements"),
             _fact("core.element_counts", json.dumps(payload.element_counts, sort_keys=True), "element_counts")],
        )
    cycle = payload.current_flow.active_luck_cycle
    confirmed = (not payload.profile.is_birth_time_estimated and
                 not {"luck_cycles", "luck_flow"}.intersection(payload.disabled_sections) and cycle is not None and
                 not any(item.key == "luck_cycles" and item.status == "disabled" for item in payload.evidence) and
                 any(item.gan_zhi == cycle.gan_zhi and item.start_year == cycle.start_year and
                     item.end_year == cycle.end_year for item in payload.luck_cycles))
    matched = next(((index, item) for index, item in enumerate(payload.luck_cycle_analysis) if confirmed and
                    item.display_gan_zhi == cycle.display_gan_zhi and item.start_year == cycle.start_year and
                    item.end_year == cycle.end_year), None)
    analysis = matched[1] if matched else None
    if analysis is not None:
        result["luck.current_stem_ten_god"] = (
            _canonical_ten_god(analysis.stem_ten_god),
            [_fact("luck.current_gan_zhi", cycle.display_gan_zhi, "current_flow.active_luck_cycle.display_gan_zhi"),
             _fact("luck.current_period", analysis.period, "luck_cycle_analysis[" + str(matched[0]) + "].period"),
             _fact("luck.current_stem_ten_god", analysis.stem_ten_god, "luck_cycle_analysis[" + str(matched[0]) + "].stem_ten_god")],
        )
    return result


def _analysis_note(payload: "InterpretationPayload", feature: str, facts: List[ReadingFact], template: str) -> ReadingAnalysisNote:
    """Render only selected-rule inputs, not a separate legacy interpretation."""
    ko = payload.profile.locale == "ko"
    values = {fact.id: fact.value for fact in facts}
    if feature == "core.dominant_element":
        labels = ELEMENT_LABELS[payload.profile.locale]
        counts = json.loads(values["core.element_counts"])
        dominant = ", ".join(labels[element] for element in values["core.dominant_elements"].split(", "))
        distribution = " · ".join((f"{labels[element]} {counts[element]}개" if ko else f"{labels[element].lower()} {counts[element]}") for element in labels)
        note_facts = [("보이는 오행 분포: " if ko else "Visible element counts: ") + distribution,
                      ("최다 오행: " if ko else "Most frequent visible elements: ") + dominant]
        reading = template.format(dominant_label=dominant)
        if payload.profile.is_birth_time_estimated:
            note_facts.append("출생시간 미상: 시주 제외" if ko else "Unknown birth time: hour pillar excluded")
    elif feature == "luck.current_stem_ten_god":
        period, label = values["luck.current_period"], values["luck.current_stem_ten_god"]
        cycle = values["luck.current_gan_zhi"]
        note_facts = [(f"현재 대운: {cycle} · {period}" if ko else f"Current cycle: {cycle} · {period}"),
                      (f"현재 대운 천간 십성: {label}" if ko else f"Current cycle stem ten-god: {label}")]
        reading = template.format(period=period, feature_label=label)
    else:
        label = values[feature]
        prefix = ("배우자궁 십성: " if ko else "Spouse-house ten-god: ") if feature.startswith("love.") else (
            "월간 십성: " if ko else "Month-stem ten-god: ")
        note_facts = [prefix + label]
        reading = template.format(feature_label=label)
    return ReadingAnalysisNote(facts=note_facts, reading=reading)


def build_reading_plan(payload: "InterpretationPayload", bundle: KnowledgeBundle = None) -> ReadingPlan:
    bundle = bundle or load_reading_knowledge()
    features = _features(payload)
    sections = {}
    locale = payload.profile.locale
    for rule in bundle.rules:
        if rule.status != "active_project_policy" or rule.feature not in features:
            continue
        value, facts = features[rule.feature]
        if value not in rule.any_of:
            continue
        if rule.topic in sections:
            raise ValueError("multiple rules selected for a reading topic")
        copy = rule.wording[locale]
        substitutions = {"period": next((fact.value for fact in facts if fact.id == "luck.current_period"), "")}
        sections[rule.topic] = ReadingStructure(
            knowledge_version=bundle.knowledge_version, copy_version=bundle.copy_version,
            question=copy.question, source_id=rule.source_id, rule_id=rule.id, rule_version=rule.version,
            facts=facts,
            blocks=[ReadingBlock(role=role, kind=ROLE_KIND[role], text=getattr(copy, role).format(**substitutions),
                                 fact_ids=[fact.id for fact in facts], rule_id=rule.id) for role in ROLE_ORDER],
            analysis_note=_analysis_note(payload, rule.feature, facts, copy.analysis_note),
        )
    return ReadingPlan(
        knowledge_version=bundle.knowledge_version, sections=sections,
        unclassified_topics=[topic for topic in ("core", "work_money", "love", "luck_flow") if topic not in sections],
        question_capabilities=[QuestionCapability(
            question_id=policy.id, question=policy.question[locale], status=policy.status,
            supported_scope=policy.supported_scope, missing_requirements=list(policy.required_data),
            forbidden_claims=list(policy.forbidden_claims),
        ) for policy in bundle.questions],
    )


def apply_reading_plan(payload: "InterpretationPayload", cards):
    """Only deterministic fallback text receives a server-verified provenance marker."""
    from app.domain.saju.interpretation import ReadingBasisExplanation

    bundle = load_reading_knowledge()
    plan = build_reading_plan(payload, bundle)
    rules = {rule.id: rule for rule in bundle.rules}
    for card in cards:
        structure = plan.sections.get(card.key)
        if structure is None:
            continue
        copy = rules[structure.rule_id].wording[payload.profile.locale]
        card.title = card.subtitle = structure.question
        card.user_takeaway = structure.blocks[0].text
        card.preview_paragraphs = [block.text for block in structure.blocks[1:]]
        card.next_question = copy.next_question
        card.reading_structure = structure
        card.basis_explanation = ReadingBasisExplanation(**model_to_dict(structure.analysis_note))
        card.basis_line = " · ".join(structure.analysis_note.facts)
    return plan


def validate_reading_structure(card, payload: "InterpretationPayload") -> List[str]:
    if card.reading_structure is None:
        return []
    expected = build_reading_plan(payload).sections.get(card.key)
    if expected is None or model_to_dict(card.reading_structure) != model_to_dict(expected):
        return ["cards." + card.key + ":reading_structure_fact_or_rule_mismatch"]
    if (card.title != expected.question or card.subtitle != expected.question or
        card.user_takeaway != expected.blocks[0].text or
        card.preview_paragraphs != [block.text for block in expected.blocks[1:]]):
        return ["cards." + card.key + ":reading_structure_text_mismatch"]
    if card.basis_explanation is None or model_to_dict(card.basis_explanation) != model_to_dict(expected.analysis_note):
        return ["cards." + card.key + ":reading_structure_note_mismatch"]
    if card.basis_line != " · ".join(expected.analysis_note.facts):
        return ["cards." + card.key + ":reading_structure_basis_line_mismatch"]
    return []


def unsupported_claim_issues(text: str) -> List[str]:
    """Bounded wording checks, not a proof of all generated text's meaning."""
    issues = []
    if re.search(r"\d+(?:\.\d+)?\s*%|(?:상위|하위)\s*\d|\b(?:percentile|probability of|chance of)\b", text, re.I):
        issues.append("unsupported_probability_or_population_comparison")
    patterns = (
        r"상대(?:는|가).{0,16}(?:좋아하고 있|좋아해|연락할 거)",
        r"(?:취업|승진|연애 시작|연인을 만나).{0,12}(?:확정|보장)",
        r"(?:면접|시험).{0,10}(?:꼭|반드시).{0,5}(?:붙|합격)",
        r"합격 소식을.{0,8}(?:듣게 될|받게 될)",
        r"(?:승진|취업)하게 될 거",
        r"연인을 만나게 될 거",
        r"(?:사주 )?전문가가 검증한 (?:정확한|해석|풀이)",
        r"(?:partner|ex).{0,20}(?:secretly loves|will contact)",
        r"(?:guaranteed|certain).{0,16}(?:job|promotion|relationship)",
        r"\byou will (?:get (?:the |a )?job|be promoted|meet your (?:partner|soulmate))\b",
        r"\bexpect a signed offer\b",
        r"\b(?:expert[- ]verified|expert[- ]certified|validated by (?:saju )?experts)\b",
        r"\bverified by (?:a |an )?(?:saju )?expert\b",
    )
    if any(re.search(pattern, text, re.I) for pattern in patterns):
        issues.append("unsupported_event_or_partner_feelings")
    return issues
