"""Wire contracts only: no engine, provider, HTTP, clock or disk dependencies."""

import hashlib
import json
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

Role = Literal["answer", "user", "supervisor"]
Status = Literal["PASS", "WARN", "HOLD", "FAIL", "ERROR"]
Grade = Literal["pass", "fail", "uncertain"]
PROMPT_VERSION = "agent-jobs-2026-10-05.2"
RUBRIC_VERSION = "reading-review-2026-10-05.2"


class Contract(BaseModel):
    class Config:
        extra = "forbid"
        allow_mutation = False


def wire(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return json.loads(value.json(ensure_ascii=False))
    return value


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(wire(value), ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def model_schema(cls) -> Dict[str, Any]:
    return cls.model_json_schema() if hasattr(cls, "model_json_schema") else cls.schema()


class CaseSpec(Contract):
    case_id: str
    synthetic: Literal[True] = True
    locale: Literal["ko", "en"]
    topic: Literal["today", "core", "love", "work_money", "luck_flow"]
    question_id: str
    question: str = Field(min_length=1, max_length=300)
    persona: str = Field(min_length=1, max_length=600)
    birth_input: Dict[str, Any]


class CaseSnapshot(Contract):
    schema_version: Literal["agent-snapshot-v1"] = "agent-snapshot-v1"
    case: CaseSpec
    as_of: str
    timezone: str
    source_revision: str
    source_hash: str
    versions: Dict[str, str]
    calculation_state: Literal["passed", "failed"]
    calculation_issue: Optional[str] = None
    payload: Dict[str, Any]
    reading_plan: Dict[str, Any]
    selected_section: Optional[Dict[str, Any]] = None
    visible: Dict[str, Any]
    snapshot_hash: str


class AgentTask(Contract):
    schema_version: Literal["agent-task-v1"] = "agent-task-v1"
    job_id: str
    role: Role
    case_id: str
    snapshot_hash: str
    answer_hash: Optional[str] = None
    prompt_version: str = PROMPT_VERSION
    rubric_version: str = RUBRIC_VERSION
    locale: Literal["ko", "en"]
    input: Dict[str, Any]
    task_hash: str


class ClaimRef(Contract):
    text_ref: Literal["answer", "scene", "tradeoff", "action", "analysis_note"]
    fact_ids: List[str] = Field(min_items=1)
    rule_ids: List[str] = Field(min_items=1)


class AnalysisNote(Contract):
    facts: List[str] = Field(max_items=3)
    reading: str = Field(max_length=600)


class AnswerDraft(Contract):
    question_id: str
    response_mode: Literal["supported", "scope_limited", "needs_input"]
    question: str = Field(min_length=1, max_length=300)
    answer: str = Field(min_length=1, max_length=600)
    scene: str = Field(max_length=600)
    tradeoff: str = Field(max_length=600)
    action: str = Field(max_length=600)
    analysis_note: AnalysisNote
    limitations: List[str] = Field(max_items=16)
    next_question: str = Field(max_length=300)
    claim_refs: List[ClaimRef] = Field(max_items=5)


class UserReview(Contract):
    evaluation_kind: Literal["synthetic_persona_review"]
    main_message: str = Field(min_length=1, max_length=600)
    action_understood: str = Field(max_length=600)
    limitations_understood: Grade
    interest: Literal["engaging", "flat", "uncertain"]
    confusing_phrases: List[str] = Field(max_items=8)
    quotes: List[str] = Field(min_items=1, max_items=8)
    follow_up: str = Field(max_length=300)
    share_intent: Literal["yes", "no", "unsure"]


class ReviewItem(Contract):
    name: Literal["fact_fidelity", "question_fit", "scope", "voice", "note_consistency"]
    grade: Grade
    quote: str = Field(max_length=600)
    reason: str = Field(min_length=1, max_length=900)
    fact_ids: List[str]
    rule_ids: List[str]


class SupervisorReview(Contract):
    items: List[ReviewItem] = Field(min_items=5, max_items=5)
    repair_requests: List[str] = Field(max_items=8)


OUTPUT_MODELS = {"answer": AnswerDraft, "user": UserReview, "supervisor": SupervisorReview}
REVIEW_NAMES = {"fact_fidelity", "question_fit", "scope", "voice", "note_consistency"}


class AgentResult(Contract):
    schema_version: Literal["agent-result-v1"] = "agent-result-v1"
    run_id: str
    attempt_id: str
    task: AgentTask
    provider: Literal["codex", "fixture"]
    configured_model: Optional[str] = None
    resolved_model: Optional[str] = None
    execution_state: Literal["completed", "error", "skipped"]
    contract_state: Literal["passed", "failed", "not_checked"] = "not_checked"
    error_code: Optional[str] = None
    unconfirmed_process_ids: List[int] = Field(default_factory=list)
    duration_ms: int = Field(ge=0)
    output: Optional[Dict[str, Any]] = None
    output_hash: Optional[str] = None


class Check(Contract):
    name: str
    status: Status
    detail: str


class CaseReport(Contract):
    case_id: str
    snapshot_hash: str
    execution_mode: Literal["contract_trial"] = "contract_trial"
    observation_scope: Literal["content_only"] = "content_only"
    blindness: Literal["input_blind_only"] = "input_blind_only"
    status: Status
    checks: List[Check]
    results: List[AgentResult]


def assert_digest(model: Contract, field: str) -> None:
    value = wire(model)
    expected = value.pop(field)
    if digest(value) != expected:
        raise ValueError("%s mismatch" % field)
