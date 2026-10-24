"""Non-inference readiness check. Never expose credentials or CLI account output."""

import argparse
import importlib
import json
from pathlib import Path
import shutil
import subprocess

from app.config import PLACEHOLDER_OPENAI_API_KEY, settings
from app.domain.saju.services.codex_provider import _codex_executable_prefix


def _openai_sdk_available():
    try:
        return callable(getattr(importlib.import_module("openai"), "OpenAI", None))
    except Exception:
        return False


def inspect_provider(provider=None, *, check_auth=False, configuration=None):
    config = configuration or settings
    provider = provider or config.llm_provider
    checks = []

    def check(name, ok, reason):
        checks.append({"id": name, "ok": bool(ok), "reason": "ready" if ok else reason})

    auth_checked = False
    model = None
    effort = None
    if provider == "openai":
        model, effort = config.openai_model, config.llm_reasoning_effort
        key = (config.openai_api_key or "").strip()
        check("api_key", key not in {"", PLACEHOLDER_OPENAI_API_KEY}, "missing_api_key")
        check("sdk", _openai_sdk_available(), "openai_sdk_unavailable")
    elif provider == "codex":
        model, effort = config.codex_model, config.codex_reasoning_effort
        check("local_only", not config.is_production, "codex_local_only")
        prefix = _codex_executable_prefix(config)
        executable_ready = bool(shutil.which(prefix[0]) or Path(prefix[0]).is_file())
        check("cli", executable_ready, "codex_command_unavailable")
        if check_auth and executable_ready and not config.is_production:
            auth_checked = True
            try:
                probe = subprocess.run(prefix + ["login", "status"], capture_output=True,
                                       timeout=15, check=False, encoding="utf-8", errors="replace")
                check("login", probe.returncode == 0, "codex_login_required")
            except subprocess.TimeoutExpired:
                check("login", False, "codex_login_check_timeout")
            except OSError:
                check("login", False, "codex_command_unavailable")
    elif provider == "fallback":
        check("deterministic", True, "")
    else:
        check("provider", False, "unsupported_provider")
    return {
        "schema_version": "provider-readiness-v1", "provider": provider,
        "configured_provider": config.llm_provider, "model": model, "reasoning_effort": effort,
        "ready": all(item["ok"] for item in checks), "checks": checks,
        "auth_checked": auth_checked, "inference_calls": 0,
        "live_generation_verified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("openai", "codex", "fallback"))
    parser.add_argument("--check-auth", action="store_true", help="Check local Codex login without inference.")
    args = parser.parse_args()
    result = inspect_provider(args.provider, check_auth=args.check_auth)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
