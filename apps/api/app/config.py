"""이 파일은 백엔드 실행 설정값을 읽고 정리한다."""

from dataclasses import dataclass
import os
import shutil
from pathlib import Path
from typing import List, Optional

PLACEHOLDER_OPENAI_API_KEY = "DEFINE_OPENAI_API_KEY"
APP_DIR = Path(__file__).resolve().parent
API_DIR = APP_DIR.parent
REPO_ROOT = API_DIR.parent.parent

def _default_codex_command() -> str:
    command_name = "codex.cmd" if os.name == "nt" else "codex"
    resolved = shutil.which(command_name) or shutil.which("codex")
    if resolved:
        return resolved
    if os.name == "nt":
        appdata = os.getenv("APPDATA")
        if appdata:
            candidate = Path(appdata) / "npm" / "codex.cmd"
            if candidate.exists():
                return str(candidate)
    return command_name


def _default_node_command() -> Optional[str]:
    resolved = shutil.which("node")
    if resolved:
        return resolved
    for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
        root = os.getenv(env_name)
        if not root:
            continue
        candidate = Path(root) / "nodejs" / "node.exe"
        if candidate.exists():
            return str(candidate)
    return None


def _default_codex_js_path() -> Optional[str]:
    appdata = os.getenv("APPDATA")
    if not appdata:
        return None
    candidate = Path(appdata) / "npm" / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
    return str(candidate) if candidate.exists() else None


DEFAULT_CODEX_COMMAND = _default_codex_command()
DEFAULT_CODEX_NODE_COMMAND = _default_node_command()
DEFAULT_CODEX_JS_PATH = _default_codex_js_path()


def _load_env_file(path: Path) -> None:
    """간단한 KEY=VALUE 형식의 로컬 env 파일을 읽는다."""
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        existing = os.environ.get(key)
        if key == "OPENAI_API_KEY":
            if existing in {None, "", PLACEHOLDER_OPENAI_API_KEY}:
                os.environ[key] = value
            continue

        os.environ.setdefault(key, value)


def _load_local_env_files() -> None:
    """repo root와 api 폴더의 로컬 env 파일을 순서대로 읽는다."""
    for candidate in (
        REPO_ROOT / ".env.local",
        API_DIR / ".env.local",
    ):
        _load_env_file(candidate)


_load_local_env_files()


def _parse_cors_origins(raw_value: str) -> List[str]:
    """cors origins를 파싱한다."""
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _parse_int_env(name: str, default: int, *, minimum: int = 0) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        value = int(raw_value)
    except ValueError:
        return default
    return max(minimum, value)


def _parse_bool_env(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value in {"1", "true", "TRUE", "yes", "YES", "on", "ON"}


@dataclass
class Settings:
    app_name: str = os.getenv("SAJU_APP_NAME", "suju-insight")
    api_version: str = os.getenv("SAJU_API_VERSION", "0.1.0")
    log_level: str = os.getenv("SAJU_LOG_LEVEL", "INFO")
    debug_enabled: bool = os.getenv("SAJU_DEBUG", "0") in {"1", "true", "TRUE", "yes", "YES"}
    llm_provider: str = os.getenv("SAJU_LLM_PROVIDER", "openai")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", PLACEHOLDER_OPENAI_API_KEY)
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-5.4")
    llm_reasoning_effort: str = os.getenv("SAJU_LLM_REASONING_EFFORT", "low")
    llm_store: bool = os.getenv("SAJU_LLM_STORE", "0") in {"1", "true", "TRUE", "yes", "YES"}
    llm_max_output_tokens: int = int(os.getenv("SAJU_LLM_MAX_OUTPUT_TOKENS", "7000"))
    codex_command: str = os.getenv("SAJU_CODEX_COMMAND", DEFAULT_CODEX_COMMAND)
    codex_node_command: Optional[str] = os.getenv("SAJU_CODEX_NODE_COMMAND") or DEFAULT_CODEX_NODE_COMMAND
    codex_js_path: Optional[str] = os.getenv("SAJU_CODEX_JS_PATH") or DEFAULT_CODEX_JS_PATH
    codex_model: Optional[str] = os.getenv("SAJU_CODEX_MODEL") or None
    codex_profile: Optional[str] = os.getenv("SAJU_CODEX_PROFILE") or None
    codex_sandbox: str = os.getenv("SAJU_CODEX_SANDBOX", "read-only")
    codex_timeout_seconds: int = _parse_int_env("SAJU_CODEX_TIMEOUT_SECONDS", 180, minimum=1)
    codex_workdir: str = os.getenv("SAJU_CODEX_WORKDIR", str(REPO_ROOT))
    request_log_enabled: bool = os.getenv("SAJU_REQUEST_LOG_ENABLED", "1") in {"1", "true", "TRUE", "yes", "YES"}
    request_log_path: str = os.getenv(
        "SAJU_REQUEST_LOG_PATH",
        str(REPO_ROOT / ".dev-runtime" / "saju-request-events.jsonl"),
    )
    request_log_max_bytes: int = _parse_int_env("SAJU_REQUEST_LOG_MAX_BYTES", 10 * 1024 * 1024)
    request_log_backup_count: int = _parse_int_env("SAJU_REQUEST_LOG_BACKUP_COUNT", 3)
    use_canonical_year_month_pillars: bool = _parse_bool_env(
        "SAJU_USE_CANONICAL_YEAR_MONTH_PILLARS",
        False,
    )
    cors_origins: Optional[List[str]] = None

    def __post_init__(self) -> None:
        """초기화 직후 파생 값을 정리한다."""
        raw_origins = os.getenv("SAJU_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
        self.cors_origins = _parse_cors_origins(raw_origins)


settings = Settings()
