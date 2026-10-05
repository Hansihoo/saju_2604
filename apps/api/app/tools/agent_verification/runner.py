"""Optional composition of independent jobs. Injected transport, no global settings."""

import threading
import time
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .checks import aggregate_status, answer_checks, evaluate
from .contracts import AgentResult, CaseReport, Check, OUTPUT_MODELS, SupervisorReview, digest, wire
from .jobs import build_task, task_request, verified_answer
from .storage import markdown_report, write_artifact
from .transports import TransportError


@dataclass(frozen=True)
class RunLimits:
    concurrency: int = 3
    max_calls: int = 12
    call_seconds: float = 180
    case_seconds: float = 600
    run_seconds: float = 900
    max_repairs: int = 0

    def __post_init__(self):
        if any(not isinstance(value, int) or isinstance(value, bool) for value in
               (self.concurrency, self.max_calls, self.max_repairs)):
            raise ValueError("Call and worker bounds must be integers")
        if not 1 <= self.concurrency <= 3 or not 0 <= self.max_repairs <= 2:
            raise ValueError("Concurrency must be 1..3 and repairs 0..2")
        if self.max_calls < 1 or any(not math.isfinite(value) or value <= 0 for value in
                                    (self.call_seconds, self.case_seconds, self.run_seconds)):
            raise ValueError("Call count and time budgets must be positive")


class JobExecutor:
    def __init__(self, transport, limits=RunLimits(), *, run_id=None):
        self.transport, self.limits = transport, limits
        self.run_id = run_id or str(uuid4())
        self.deadline = time.monotonic() + limits.run_seconds
        self.slots = threading.BoundedSemaphore(limits.concurrency)
        self.lock = threading.Lock()
        self.calls = 0
        self.stopped = False
        self.stop_reason = "cleanup_failed_stop"
        self.unconfirmed_process_ids = []
        self.events = []

    def cancel(self):
        with self.lock:
            self.stopped = True
            self.stop_reason = "run_cancelled"
        cancel = getattr(self.transport, "cancel", None)
        if cancel:
            try:
                cancel()
            except TransportError as exc:
                with self.lock:
                    self.stop_reason = "process_cleanup_failed"
                    self.unconfirmed_process_ids = list(exc.process_ids)

    def execute(self, task, *, output_root, case_deadline=None):
        task_request(task)  # Validate contract/version before reserving a model call.
        started = time.monotonic()
        deadline = min(self.deadline, case_deadline if case_deadline is not None else self.deadline)
        attempt_id = str(uuid4())
        base = dict(run_id=self.run_id, attempt_id=attempt_id, task=wire(task), provider=self.transport.provider,
                    configured_model=self.transport.configured_model, duration_ms=0)
        remaining = deadline - time.monotonic()
        acquired = remaining > 0 and self.slots.acquire(timeout=remaining)
        if not acquired:
            return AgentResult(**base, execution_state="skipped", error_code="deadline_exceeded")
        try:
            with self.lock:
                remaining = deadline - time.monotonic()
                reason = self.stop_reason if self.stopped else "call_budget_exhausted" if self.calls >= self.limits.max_calls else "deadline_exceeded" if remaining <= 0 else None
                if reason:
                    return AgentResult(**base, execution_state="skipped", error_code=reason)
                self.calls += 1
                self.events.append(dict(attempt_id=attempt_id, role=task.role, case_id=task.case_id,
                                        stage="started", call_number=self.calls, monotonic=time.monotonic()))
            try:
                isolated_task = type(task)(**wire(task))
                reply = self.transport.execute(isolated_task, timeout=min(self.limits.call_seconds, remaining),
                                               attempt_dir=Path(output_root) / ("attempt-" + attempt_id))
                task_request(isolated_task)
                try:
                    OUTPUT_MODELS[task.role](**reply.output)
                    contract_state = "passed"
                except (ValueError, TypeError):
                    contract_state = "failed"
                result = AgentResult(**dict(base, duration_ms=reply.duration_ms), execution_state="completed",
                                     contract_state=contract_state, output=reply.output,
                                     output_hash=digest(reply.output), resolved_model=reply.resolved_model)
                event_types = list(reply.event_types)
            except TransportError as exc:
                if exc.code == "run_cancelled":
                    self.cancel()
                if exc.fatal:
                    with self.lock:
                        self.stopped = True
                        self.stop_reason = "cleanup_failed_stop"
                result = AgentResult(**dict(base, duration_ms=int((time.monotonic()-started)*1000)),
                                     execution_state="skipped" if exc.code == "run_cancelled" and self.stop_reason != "process_cleanup_failed" else "error",
                                     error_code=self.stop_reason if exc.code == "run_cancelled" else exc.code,
                                     unconfirmed_process_ids=list(exc.process_ids) or self.unconfirmed_process_ids)
                event_types = []
            except KeyboardInterrupt:
                self.cancel()
                result = AgentResult(**dict(base, duration_ms=int((time.monotonic()-started)*1000)),
                                     execution_state="error" if self.stop_reason == "process_cleanup_failed" else "skipped",
                                     error_code=self.stop_reason, unconfirmed_process_ids=self.unconfirmed_process_ids)
                event_types = []
            except Exception:
                # Do not expose exception messages containing input/credentials in summary logs.
                result = AgentResult(**dict(base, duration_ms=int((time.monotonic()-started)*1000)),
                                     execution_state="error", error_code="transport_unexpected_error")
                event_types = []
            with self.lock:
                self.events.append(dict(attempt_id=attempt_id, role=task.role, case_id=task.case_id,
                                        stage=result.execution_state, duration_ms=result.duration_ms,
                                        event_types=event_types, monotonic=time.monotonic()))
            return result
        finally:
            self.slots.release()


def run_case(snapshot, executor, output_root, roles):
    deadline = time.monotonic() + executor.limits.case_seconds
    folder = Path(output_root) / snapshot.case.case_id
    folder.mkdir(exist_ok=False)
    write_artifact(folder / "snapshot.json", snapshot)
    if snapshot.calculation_state != "passed":
        return evaluate(snapshot, [])
    if "answer" not in roles:
        raise ValueError("Batch run needs answer; execute saved review jobs for standalone user/supervisor")
    history = []
    repair = None
    for revision in range(executor.limits.max_repairs + 1):
        task = build_task(snapshot, "answer", repair=repair)
        answer = executor.execute(task, output_root=folder, case_deadline=deadline)
        write_artifact(folder / ("answer-%d.json" % revision), answer)
        current = [answer]
        try:
            verified_answer(snapshot, answer)
        except (ValueError, TypeError):
            report = evaluate(snapshot, current)
            history.append(wire(report))
            break
        code_checks = answer_checks(snapshot, answer)
        review_roles = [role for role in ("user", "supervisor") if role in roles]
        with ThreadPoolExecutor(max_workers=2) as pool:
            tasks = {role: build_task(snapshot, role, answer, code_checks=code_checks if role == "supervisor" else ())
                     for role in review_roles}
            futures = {pool.submit(executor.execute, task, output_root=folder, case_deadline=deadline): role
                       for role, task in tasks.items()}
            for future in as_completed(futures):
                role = futures[future]
                result = future.result()
                current.append(result)
                write_artifact(folder / ("%s-%d.json" % (role, revision)), result)
        current.sort(key=lambda result: ("answer", "user", "supervisor").index(result.task.role))
        report = evaluate(snapshot, current)
        history.append(wire(report))
        if report.status != "FAIL" or revision == executor.limits.max_repairs:
            break
        supervisor = next((r for r in current if r.task.role == "supervisor" and r.execution_state == "completed"), None)
        try:
            requests = SupervisorReview(**(supervisor.output or {})).repair_requests if supervisor else []
        except (ValueError, TypeError):
            requests = []
        failures = [wire(c) for c in report.checks if c.status == "FAIL"]
        repair = {"previous_answer": answer.output, "code_failures": failures, "requests": requests}
    write_artifact(folder / "history.json", history)
    write_artifact(folder / "report.json", report)
    return report


def isolated_case(snapshot, executor, output_root, roles):
    try:
        return run_case(snapshot, executor, output_root, roles)
    except Exception:
        # Preserve one defective case in the final report; other cases continue.
        return CaseReport(case_id=snapshot.case.case_id, snapshot_hash=snapshot.snapshot_hash, status="ERROR",
                          checks=[Check(name="case_execution", status="ERROR",
                                        detail="Case artifact, contract or processing failed; retained partial evidence must be inspected")],
                          results=[])


def run_snapshots(snapshots, transport, *, output_root, roles=("answer", "user", "supervisor"), limits=RunLimits()):
    output_root = Path(output_root)
    if not snapshots or len({s.case.case_id for s in snapshots}) != len(snapshots):
        raise ValueError("Require nonempty unique cases")
    if not roles or len(set(roles)) != len(roles) or set(roles) - {"answer", "user", "supervisor"} or "answer" not in roles:
        raise ValueError("Batch roles must be unique and include answer")
    output_root.mkdir(parents=False, exist_ok=False)
    executor = JobExecutor(transport, limits)
    reports = []
    pool = ThreadPoolExecutor(max_workers=limits.concurrency)
    futures = {pool.submit(isolated_case, s, executor, output_root, roles): s for s in snapshots}
    cancelled = False
    try:
        for future in as_completed(futures):
            reports.append(future.result())
    except KeyboardInterrupt:
        cancelled = True
        executor.cancel()
        for future in futures:
            future.cancel()
    finally:
        pool.shutdown(wait=True)
    seen = {r.case_id for r in reports}
    for future, snapshot in futures.items():
        if snapshot.case.case_id in seen:
            continue
        if future.cancelled():
            reports.append(CaseReport(case_id=snapshot.case.case_id, snapshot_hash=snapshot.snapshot_hash,
                                      status="HOLD", checks=[Check(name="case_cancelled", status="HOLD",
                                                                  detail="Cancelled before this case started")], results=[]))
        else:
            reports.append(future.result())
    reports.sort(key=lambda report: report.case_id)
    report = dict(schema_version="agent-run-v1", run_id=executor.run_id,
                  status=aggregate_status([Check(name=r.case_id, status=r.status, detail="Case result") for r in reports]
                         + ([Check(name="run_cancelled", status="ERROR" if executor.stop_reason == "process_cleanup_failed" else "HOLD",
                                   detail="Run cancellation recorded")] if cancelled else [])),
                  provider=transport.provider, calls=executor.calls, cancelled=cancelled,
                  unconfirmed_process_ids=executor.unconfirmed_process_ids,
                  limits=limits.__dict__, roles=list(roles),
                  cases=[wire(r) for r in reports], events=executor.events)
    write_artifact(output_root / "report.json", report)
    (output_root / "report.md").write_text(markdown_report(report), encoding="utf-8")
    return report
