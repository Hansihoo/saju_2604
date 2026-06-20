"""Local Codex CLI provider helpers for LLM-style JSON rendering."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Dict, Sequence

from app.config import settings


@dataclass(frozen=True)
class CodexProviderResult:
    output_text: str
    response_id: str
    duration_ms: int
    stdout_excerpt: str = ""
    stderr_excerpt: str = ""


class CodexProviderError(RuntimeError):
    def __init__(
        self,
        reason: str,
        message: str,
        *,
        stdout_excerpt: str = "",
        stderr_excerpt: str = "",
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.stdout_excerpt = stdout_excerpt
        self.stderr_excerpt = stderr_excerpt


def _excerpt(text: str, limit: int = 320) -> str:
    compact = " ".join(text.split())
    return compact[:limit]


def _codex_executable_prefix() -> list[str]:
    if os.name == "nt" and settings.codex_node_command and settings.codex_js_path:
        if Path(settings.codex_node_command).exists() and Path(settings.codex_js_path).exists():
            return [settings.codex_node_command, settings.codex_js_path]
    return [settings.codex_command]


def _codex_command(output_path: Path) -> list[str]:
    command = [
        *_codex_executable_prefix(),
        "exec",
        "--cd",
        settings.codex_workdir,
        "--sandbox",
        settings.codex_sandbox,
        "--color",
        "never",
        "--output-last-message",
        str(output_path),
    ]
    if settings.codex_model:
        command.extend(["--model", settings.codex_model])
    if settings.codex_profile:
        command.extend(["--profile", settings.codex_profile])
    command.append("-")
    return command


def _extract_json_text(raw_text: str) -> str:
    text = raw_text.strip()
    if not text:
        raise JSONDecodeError("empty codex output", raw_text, 0)
    try:
        json.loads(text)
        return text
    except JSONDecodeError:
        pass

    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            fenced = "\n".join(lines[1:-1]).strip()
            json.loads(fenced)
            return fenced

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        candidate = text[start : end + 1]
        json.loads(candidate)
        return candidate
    raise JSONDecodeError("codex output does not contain JSON", raw_text, 0)


def call_codex_json(
    *,
    developer_prompt: str,
    user_payload: Dict[str, Any],
    output_schema: Dict[str, Any],
    schema_name: str,
    extra_instructions: Sequence[str] = (),
) -> CodexProviderResult:
    prompt = "\n\n".join(
        [
            developer_prompt.strip(),
            "Return only valid JSON matching the provided output schema. Do not include markdown fences or commentary.",
            *[item.strip() for item in extra_instructions if item.strip()],
            "Output JSON Schema:",
            json.dumps(output_schema, ensure_ascii=False),
            "Input JSON:",
            json.dumps(user_payload, ensure_ascii=False),
        ]
    )

    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="saju-codex-") as temp_dir:
        temp_path = Path(temp_dir)
        output_path = temp_path / f"{schema_name}.output.json"

        try:
            completed = subprocess.run(
                _codex_command(output_path),
                input=prompt,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=settings.codex_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise CodexProviderError(
                "codex_timeout",
                f"Codex CLI timed out after {settings.codex_timeout_seconds}s",
                stdout_excerpt=_excerpt(exc.stdout or ""),
                stderr_excerpt=_excerpt(exc.stderr or ""),
            ) from exc
        except OSError as exc:
            raise CodexProviderError("codex_command_unavailable", str(exc)) from exc

        stdout_excerpt = _excerpt(completed.stdout or "")
        stderr_excerpt = _excerpt(completed.stderr or "")
        if completed.returncode != 0:
            detail = stderr_excerpt or stdout_excerpt
            message = f"Codex CLI exited with code {completed.returncode}"
            if detail:
                message = f"{message}: {detail}"
            raise CodexProviderError(
                "codex_request_failed",
                message,
                stdout_excerpt=stdout_excerpt,
                stderr_excerpt=stderr_excerpt,
            )

        raw_output = output_path.read_text(encoding="utf-8") if output_path.exists() else completed.stdout
        try:
            output_text = _extract_json_text(raw_output)
        except JSONDecodeError as exc:
            raise CodexProviderError(
                "json_decode_error",
                str(exc),
                stdout_excerpt=stdout_excerpt,
                stderr_excerpt=stderr_excerpt,
            ) from exc

    duration_ms = int((time.perf_counter() - started) * 1000)
    return CodexProviderResult(
        output_text=output_text,
        response_id=f"codex-cli:{int(started * 1000)}",
        duration_ms=duration_ms,
        stdout_excerpt=stdout_excerpt,
        stderr_excerpt=stderr_excerpt,
    )
