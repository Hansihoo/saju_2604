from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.api_version,
    summary="Saju web service backend bootstrap"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.get("/")
def read_root() -> Dict[str, str]:
    return {
        "service": settings.app_name,
        "message": "suju-insight API is running"
    }


@app.get("/health")
def read_health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.api_version,
        "message": "사주 해석 서비스의 첫 API 뼈대가 준비되었습니다.",
        "focus": ["mvp-bootstrap", "healthcheck", "service-metadata"],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
