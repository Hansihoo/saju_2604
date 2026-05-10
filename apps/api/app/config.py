"""이 파일은 백엔드 실행 설정값을 읽고 정리한다."""

from dataclasses import dataclass
import os
from pathlib import Path
from typing import List, Optional

PLACEHOLDER_OPENAI_API_KEY = "DEFINE_OPENAI_API_KEY"
APP_DIR = Path(__file__).resolve().parent
API_DIR = APP_DIR.parent
REPO_ROOT = API_DIR.parent.parent


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
    request_log_enabled: bool = os.getenv("SAJU_REQUEST_LOG_ENABLED", "1") in {"1", "true", "TRUE", "yes", "YES"}
    request_log_path: str = os.getenv(
        "SAJU_REQUEST_LOG_PATH",
        str(REPO_ROOT / ".dev-runtime" / "saju-request-events.jsonl"),
    )
    cors_origins: Optional[List[str]] = None

    def __post_init__(self) -> None:
        """초기화 직후 파생 값을 정리한다."""
        raw_origins = os.getenv("SAJU_CORS_ORIGINS", "http://localhost:5173")
        self.cors_origins = _parse_cors_origins(raw_origins)


settings = Settings()
