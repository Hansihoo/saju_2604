"""Interchangeable one-call transports; no application settings or saju imports."""

import json
import os
import signal
import subprocess
import time
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol, Tuple

from .contracts import AgentTask, REVIEW_NAMES
from .jobs import task_request


class TransportError(RuntimeError):
    def __init__(self, code, *, fatal=False, process_ids=()):
        super().__init__(code)
        self.code = code
        self.fatal = fatal
        self.process_ids = tuple(pid for pid in process_ids if isinstance(pid, int) and pid > 0)


@dataclass(frozen=True)
class TransportReply:
    output: dict
    duration_ms: int
    resolved_model: Optional[str] = None
    event_types: Tuple[str, ...] = ()


class Transport(Protocol):
    provider: str
    configured_model: Optional[str]

    def execute(self, task: AgentTask, *, timeout: float, attempt_dir: Path) -> TransportReply: ...


@dataclass(frozen=True)
class CodexConfig:
    executable: Tuple[str, ...]
    workdir: str
    model: Optional[str] = None
    profile: Optional[str] = None


class CodexTransport:
    provider = "codex"

    def __init__(self, config: CodexConfig):
        if not config.executable:
            raise ValueError("Codex executable is required")
        self.config = config
        self.configured_model = config.model
        self.cancelled = threading.Event()
        self.active_lock = threading.RLock()
        self.active = {}
        self.cleanup_state = {}

    def stop_process(self, process):
        with self.active_lock:
            if self.cleanup_state.get(id(process)) == "confirmed":
                return
            try:
                self.stop_owned_tree(process)
                self.cleanup_state[id(process)] = "confirmed"
            except TransportError as exc:
                self.cleanup_state[id(process)] = "unconfirmed"
                raise TransportError(exc.code, fatal=True, process_ids=(process.pid,))

    def cancel(self):
        self.cancelled.set()
        cleanup_failed = False
        with self.active_lock:
            for process in list(self.active.values()):
                try:
                    self.stop_process(process)
                except TransportError:
                    cleanup_failed = True
            unconfirmed = tuple(p.pid for p in self.active.values()
                                if self.cleanup_state.get(id(p)) != "confirmed")
        if cleanup_failed:
            raise TransportError("process_cleanup_failed", fatal=True, process_ids=unconfirmed)

    def command(self, schema_path: Path, output_path: Path):
        command = [*self.config.executable, "exec", "--cd", self.config.workdir,
                   "--sandbox", "read-only", "--color", "never", "--ephemeral", "--json",
                   "--output-schema", str(schema_path), "--output-last-message", str(output_path)]
        if self.config.model:
            command += ["--model", self.config.model]
        if self.config.profile:
            command += ["--profile", self.config.profile]
        return command + ["-"]

    @staticmethod
    def stop_owned_tree(process):
        if process.poll() is not None:
            # A timeout after parent exit can mean a descendant still owns the pipes.
            # Never certify cleanup or start another call without confirming that tree.
            raise TransportError("process_cleanup_unconfirmed", fatal=True)
        try:
            if os.name == "nt":
                killed = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                        capture_output=True, timeout=10, check=False)
                if killed.returncode and process.poll() is None:
                    raise TransportError("process_cleanup_failed", fatal=True)
            else:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)
        except TransportError:
            raise
        except (OSError, subprocess.SubprocessError):
            raise TransportError("process_cleanup_failed", fatal=True)
        if process.poll() is None:
            raise TransportError("process_cleanup_failed", fatal=True)

    def execute(self, task, *, timeout, attempt_dir):
        prompt, payload, schema = task_request(task)
        attempt_dir.mkdir(parents=True, exist_ok=False)
        schema_path, output_path = attempt_dir / "schema.json", attempt_dir / "output.json"
        schema_path.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")
        stdin = prompt + "\n\nInput JSON:\n" + json.dumps(payload, ensure_ascii=False)
        options = {"stdin": subprocess.PIPE, "stdout": subprocess.PIPE, "stderr": subprocess.PIPE,
                   "encoding": "utf-8", "errors": "replace"}
        if os.name == "nt":
            options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        else:
            options["start_new_session"] = True
        started = time.monotonic()
        with self.active_lock:
            if self.cancelled.is_set():
                raise TransportError("run_cancelled")
            try:
                process = subprocess.Popen(self.command(schema_path, output_path), **options)
            except OSError:
                raise TransportError("codex_command_unavailable")
            self.active[id(process)] = process
            self.cleanup_state[id(process)] = "pending"
        needs_cleanup = True
        try:
            stdout, _stderr = process.communicate(stdin, timeout=timeout)
            needs_cleanup = False
        except subprocess.TimeoutExpired:
            with self.active_lock:
                self.stop_process(process)
            raise TransportError("codex_timeout")
        except KeyboardInterrupt:
            self.stop_process(process)
            raise TransportError("run_cancelled")
        except BaseException:
            with self.active_lock:
                self.stop_process(process)
            raise
        finally:
            with self.active_lock:
                if not needs_cleanup or self.cleanup_state.get(id(process)) == "confirmed":
                    self.active.pop(id(process), None)
        if self.cancelled.is_set():
            raise TransportError("run_cancelled")
        if process.returncode:
            raise TransportError("codex_exit_nonzero")
        if not output_path.is_file() or output_path.stat().st_size > 1_000_000:
            raise TransportError("codex_output_missing_or_oversized")
        try:
            output = json.loads(output_path.read_text(encoding="utf-8"))
            if not isinstance(output, dict):
                raise ValueError("object required")
        except (OSError, ValueError):
            raise TransportError("codex_invalid_json")
        # Keep only event type names, never agent reasoning, prompts or stderr in summary logs.
        event_types = []
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
                kind = event.get("type")
                if isinstance(kind, str) and len(kind) <= 80:
                    event_types.append(kind)
            except (ValueError, AttributeError):
                continue
        return TransportReply(output, int((time.monotonic() - started) * 1000), event_types=tuple(event_types))


class FixtureTransport:
    """Deterministic plumbing fixture. Never emits a semantic PASS judgment."""
    provider = "fixture"
    configured_model = None

    def execute(self, task, *, timeout, attempt_dir):
        task_request(task)
        # Fixture output must not alias the immutable task/snapshot dictionaries.
        data = json.loads(json.dumps(task.input, ensure_ascii=False))
        if task.role == "answer":
            section = data["selected_section"]
            ko = task.locale == "ko"
            limits = list(data["limitations"])
            if data["capability"]:
                limit = ("이 질문에 답할 기간 자료나 검토된 해석 기준이 아직 없어."
                         if ko else "The period data or reviewed interpretation criteria needed for this question are not available yet.")
                limits.append(limit)
                output = dict(question_id=data["question_id"], question=data["question"],
                              response_mode="scope_limited", answer=limit, scene="", tradeoff="",
                              action=("이 질문에 필요한 자료와 해석 기준부터 검토해야 해." if ko else
                                      "Review the data and interpretation criteria required for this question first."),
                              analysis_note={"facts": [], "reading": ""}, limitations=limits,
                              next_question="", claim_refs=[])
            elif section:
                roles = {block["role"]: block["text"] for block in section["blocks"]}
                output = dict(question_id=data["question_id"], question=data["question"],
                              response_mode="supported", **roles,
                              analysis_note=section["analysis_note"], limitations=limits,
                              next_question=section["policy_rule"]["wording"][task.locale]["next_question"],
                              claim_refs=[{"text_ref": role, "fact_ids": [f["id"] for f in section["facts"]],
                                           "rule_ids": [section["rule_id"]]} for role in
                                          ("answer", "scene", "tradeoff", "action", "analysis_note")])
            else:
                message = ("이 질문을 읽을 수 있는 확인된 해석 규칙이 없어. 계산에서 제외된 항목부터 확인해줘."
                           if ko else "No confirmed interpretation rule supports this question. Check the excluded inputs first.")
                mode = "needs_input"
                if "period" in data["visible_reference"]:
                    message = data["visible_reference"]["answer"]
                    mode = "scope_limited"
                    limits.append("Legacy today output is present; the question-reading contract has not been migrated.")
                output = dict(question_id=data["question_id"], question=data["question"], response_mode=mode,
                              answer=message, scene="", tradeoff="", action="", analysis_note={"facts": [], "reading": ""},
                              limitations=limits, next_question="", claim_refs=[])
        elif task.role == "user":
            visible = data["visible"]
            output = dict(evaluation_kind="synthetic_persona_review", main_message="Fixture: no reader inference performed.",
                          action_understood="", limitations_understood="uncertain", interest="uncertain",
                          confusing_phrases=[], quotes=[visible["answer"]], follow_up="", share_intent="unsure")
        else:
            output = {"items": [{"name": name, "grade": "uncertain", "quote": data["answer"]["answer"],
                                 "reason": "Fixture: semantic evaluation requires an actual independent reviewer.",
                                 "fact_ids": [], "rule_ids": []} for name in sorted(REVIEW_NAMES)], "repair_requests": []}
        return TransportReply(output, 0)
