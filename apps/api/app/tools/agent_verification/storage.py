"""Explicit artifacts and report rendering; no implicit agent or calculation calls."""

import json
from pathlib import Path

from .contracts import wire

MAX_ARTIFACT_BYTES = 4_000_000


def read_artifact(path, model):
    path = Path(path)
    if path.stat().st_size > MAX_ARTIFACT_BYTES:
        raise ValueError("Artifact exceeds the size limit")
    return model(**json.loads(path.read_text(encoding="utf-8")))


def write_artifact(path, value):
    path = Path(path)
    # Never overwrite evidence from an earlier run/revision.
    with path.open("x", encoding="utf-8") as stream:
        json.dump(wire(value), stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def markdown_report(report):
    lines = ["# Codex agent verification", "", "Run: `%s`" % report["run_id"],
             "Status: **%s**" % report["status"], "",
             "Content-only contract trial. Synthetic reactions are not measured user interest.",
             "Fixture outputs are plumbing checks, not live Codex or semantic verification.", "",
             "| Case | Status | Calculation | Answer / User / Supervisor |",
             "| --- | --- | --- | --- |"]
    for case in report["cases"]:
        value = wire(case)
        roles = {r["task"]["role"]: r["provider"] + ":" + r["execution_state"] for r in value["results"]}
        calc = next((c["status"] for c in value["checks"] if c["name"] == "calculation"), "not_observed")
        lines.append("| %s | %s | %s | %s |" % (value["case_id"], value["status"], calc,
                     " / ".join(roles.get(role, "not_run") for role in ("answer", "user", "supervisor"))))
    for case in report["cases"]:
        value = wire(case)
        lines += ["", "## " + value["case_id"], ""]
        for c in value["checks"]:
            if c["status"] != "PASS":
                lines.append("- **%s** `%s`: %s" % (c["status"], c["name"], c["detail"].replace("\n", " ")))
    return "\n".join(lines) + "\n"
