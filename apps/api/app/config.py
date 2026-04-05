from dataclasses import dataclass
import os
from typing import List, Optional


def _parse_cors_origins(raw_value: str) -> List[str]:
    return [item.strip() for item in raw_value.split(",") if item.strip()]


@dataclass
class Settings:
    app_name: str = os.getenv("SAJU_APP_NAME", "suju-insight")
    api_version: str = os.getenv("SAJU_API_VERSION", "0.1.0")
    cors_origins: Optional[List[str]] = None

    def __post_init__(self) -> None:
        raw_origins = os.getenv("SAJU_CORS_ORIGINS", "http://localhost:5173")
        self.cors_origins = _parse_cors_origins(raw_origins)


settings = Settings()
