"""Thin composition boundary; individual job modules never import application config."""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

from .cases import DEFAULT_AS_OF, cases
from .checks import answer_checks, evaluate
from .contracts import AgentResult, AgentTask, CaseSnapshot, wire
from .jobs import build_task
from .runner import JobExecutor, RunLimits, run_snapshots
from .storage import read_artifact, write_artifact
from .transports import CodexConfig, CodexTransport, FixtureTransport


def make_transport(name):
    if name == "fixture":
        return FixtureTransport()
    # Capture once at the CLI boundary. No per-job mutation of settings/provider.
    from app.config import settings
    if os.name == "nt" and settings.codex_node_command and settings.codex_js_path and (
            Path(settings.codex_node_command).exists() and Path(settings.codex_js_path).exists()):
        executable = (settings.codex_node_command, settings.codex_js_path)
    else:
        executable = (settings.codex_command,)
    return CodexTransport(CodexConfig(executable=executable, workdir=settings.codex_workdir,
                                    model=settings.codex_model, profile=settings.codex_profile))


def parser():
    p = argparse.ArgumentParser(description="Independent artifact-based saju verification jobs; fixture transport by default.")
    sub = p.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare", help="Capture one synthetic calculation snapshot; no model calls")
    prepare.add_argument("--case", choices=tuple(cases()), required=True)
    prepare.add_argument("--as-of", default=DEFAULT_AS_OF)
    prepare.add_argument("--output", type=Path, required=True)
    task = sub.add_parser("task", help="Prepare one self-contained role task; no model calls")
    task.add_argument("--snapshot", type=Path, required=True)
    task.add_argument("--role", choices=("answer", "user", "supervisor"), required=True)
    task.add_argument("--answer", type=Path)
    task.add_argument("--output", type=Path, required=True)
    execute = sub.add_parser("execute", help="Execute exactly one role job; no hidden retries/other agents")
    execute.add_argument("--task", type=Path, required=True)
    execute.add_argument("--output-dir", type=Path, required=True)
    evaluate_cmd = sub.add_parser("evaluate", help="Merge saved results; missing reviews remain HOLD")
    evaluate_cmd.add_argument("--snapshot", type=Path, required=True)
    evaluate_cmd.add_argument("--results", type=Path, nargs="+", required=True)
    evaluate_cmd.add_argument("--output", type=Path, required=True)
    run = sub.add_parser("run", help="Optionally compose fixed jobs; does not change the HTTP provider")
    run.add_argument("--cases", default="S2,S3,S5")
    run.add_argument("--as-of", default=DEFAULT_AS_OF)
    run.add_argument("--roles", default="answer,user,supervisor")
    run.add_argument("--output-dir", type=Path, required=True)
    for cmd in (execute, run):
        cmd.add_argument("--transport", choices=("fixture", "codex"), default="fixture",
                         help="Codex inference is only invoked when explicitly selected")
        cmd.add_argument("--max-calls", type=int, default=12 if cmd is run else 1)
        cmd.add_argument("--concurrency", type=int, default=3 if cmd is run else 1)
        cmd.add_argument("--call-seconds", type=float, default=180)
        cmd.add_argument("--case-seconds", type=float, default=600)
        cmd.add_argument("--run-seconds", type=float, default=900)
    run.add_argument("--max-repairs", type=int, default=0)
    return p


def limits_from(args):
    return RunLimits(concurrency=args.concurrency, max_calls=args.max_calls,
                     call_seconds=args.call_seconds, case_seconds=args.case_seconds,
                     run_seconds=args.run_seconds, max_repairs=getattr(args, "max_repairs", 0))


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "prepare":
            from .calculation_adapter import prepare_snapshot
            snapshot = prepare_snapshot(cases()[args.case], args.as_of)
            write_artifact(args.output, snapshot)
            print(json.dumps({"case_id": args.case, "calculation": snapshot.calculation_state, "output": str(args.output)}))
            return 0 if snapshot.calculation_state == "passed" else 1
        if args.command == "task":
            snapshot = read_artifact(args.snapshot, CaseSnapshot)
            answer = read_artifact(args.answer, AgentResult) if args.answer else None
            checks = answer_checks(snapshot, answer) if args.role == "supervisor" and answer else ()
            task = build_task(snapshot, args.role, answer, code_checks=checks)
            write_artifact(args.output, task)
            print(json.dumps({"role": task.role, "job_id": task.job_id, "output": str(args.output)}))
            return 0
        if args.command == "execute":
            task = read_artifact(args.task, AgentTask)
            args.output_dir.mkdir(parents=False, exist_ok=False)
            executor = JobExecutor(make_transport(args.transport), limits_from(args))
            result = executor.execute(task, output_root=args.output_dir,
                                      case_deadline=time.monotonic() + args.case_seconds)
            write_artifact(args.output_dir / "result.json", result)
            write_artifact(args.output_dir / "events.json", executor.events)
            print(json.dumps({"role": task.role, "provider": result.provider,
                              "execution": result.execution_state, "contract": result.contract_state, "calls": executor.calls}))
            return 2 if result.execution_state != "completed" else 1 if result.contract_state == "failed" else 0
        if args.command == "evaluate":
            snapshot = read_artifact(args.snapshot, CaseSnapshot)
            results = [read_artifact(path, AgentResult) for path in args.results]
            report = evaluate(snapshot, results)
            write_artifact(args.output, report)
            print(json.dumps({"case_id": report.case_id, "status": report.status}))
            return 1 if report.status in {"ERROR", "FAIL"} else 0
        from .calculation_adapter import prepare_snapshot
        catalog = cases()
        names, roles = re.split(r"[,\s]+", args.cases.strip()), tuple(re.split(r"[,\s]+", args.roles.strip()))
        if len(set(names)) != len(names) or any(name not in catalog for name in names):
            raise ValueError("Unknown or duplicate case")
        limits = limits_from(args)
        snapshots = [prepare_snapshot(catalog[name], args.as_of) for name in names]
        report = run_snapshots(snapshots, make_transport(args.transport), output_root=args.output_dir, roles=roles, limits=limits)
        print(json.dumps({"run_id": report["run_id"], "provider": report["provider"], "status": report["status"],
                          "calls": report["calls"], "cases": {c["case_id"]: c["status"] for c in report["cases"]},
                          "report": str(args.output_dir / "report.md")}, ensure_ascii=False))
        return 2 if report["cancelled"] else 1 if report["status"] in {"ERROR", "FAIL"} else 0
    except (ValueError, TypeError, OSError) as exc:
        # Input artifacts may contain personal data; never print validation values.
        print("Verification stopped: %s. Check input contracts and explicit output paths." % type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
