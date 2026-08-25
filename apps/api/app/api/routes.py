"""이 파일은 HTTP endpoint를 정의하고 service 계층으로 요청을 전달한다."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from app.config import settings
from app.diagnostics import capture_saju_request_event, to_json_safe
from app.domain.saju.schemas import (
    RegionSearchResponse,
    RegionSuggestion,
    SajuDetailPrepareRequest,
    SajuDetailPrepareResponse,
    SajuDetailRenderRequest,
    SajuDetailRenderResponse,
    SajuFreeDetailResponse,
    SajuPreviewRequest,
    SajuPreviewResponse,
)
from app.domain.saju.services.generate_detail_insights import (
    DETAIL_PROMPT_VERSION,
    DETAIL_TYPES,
    compute_detail_input_hash,
    get_cached_detail_bundle,
    prepare_detail_analysis_bundle,
    render_detail_insight,
)
from app.domain.saju.services.preview_orchestrator import create_saju_preview_response
from app.domain.saju.services.region_catalog import search_regions

router = APIRouter()


def _model_for_provider(provider: str) -> Optional[str]:
    if provider == "openai":
        return settings.openai_model
    if provider == "codex":
        return settings.codex_model or "codex-cli"
    return None


def _request_method(request: Request) -> str:
    return getattr(request, "method", "POST")


def _request_path(request: Request) -> str:
    request_url = getattr(request, "url", None)
    return getattr(request_url, "path", "/saju/preview")


def _is_http_request(request: Request) -> bool:
    return hasattr(request, "method") and hasattr(request, "url")


@router.get("/")
def read_root() -> Dict[str, str]:
    """루트 경로에서 API 기본 정보를 반환한다."""
    return {
        "service": settings.app_name,
        "message": "suju-insight API is running",
    }


@router.get("/health")
def read_health() -> Dict[str, Any]:
    """헬스 체크에 사용할 서비스 상태 정보를 반환한다."""
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.api_version,
        "message": "suju-insight API bootstrap is ready.",
        "focus": ["contracts", "trace", "time-correction", "calendar-normalization", "saju-engine"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/regions/search", response_model=RegionSearchResponse)
def search_regions_endpoint(
    request: Request,
    q: str = Query(default="", min_length=0),
    limit: int = Query(default=5, ge=1, le=10),
) -> RegionSearchResponse:
    """검색어에 맞는 지역 후보를 API 응답으로 반환한다."""
    items = [RegionSuggestion(**region) for region in search_regions(query=q, limit=limit)]
    return RegionSearchResponse(
        trace_id=request.state.trace_id,
        items=items,
        total=len(items),
    )


@router.post(
    "/saju/preview",
    response_model=SajuPreviewResponse,
    response_model_exclude_none=True,
)
def create_saju_preview(
    payload: SajuPreviewRequest,
    request: Request,
) -> SajuPreviewResponse:
    """사주 미리보기 요청을 받아 파이프라인을 실행한다."""
    payload_snapshot = to_json_safe(payload)
    request.state.saju_preview_payload = payload_snapshot
    response = create_saju_preview_response(
        payload=payload,
        trace_id=request.state.trace_id,
        debug_requested=request.state.debug_requested,
        service_name=settings.app_name,
        report_mode="free_preview",
    )
    if _is_http_request(request):
        capture_saju_request_event(
            enabled=settings.request_log_enabled,
            log_path=settings.request_log_path,
            max_bytes=settings.request_log_max_bytes,
            backup_count=settings.request_log_backup_count,
            service=settings.app_name,
            trace_id=request.state.trace_id,
            method=_request_method(request),
            path=_request_path(request),
            status_code=200,
            payload=payload_snapshot,
            debug_requested=request.state.debug_requested,
            include_input=settings.request_log_include_input,
            stage="completed",
            meta={"pipeline_status": response.pipeline_status},
        )
    return response


@router.post(
    "/saju/free-detail",
    response_model=SajuFreeDetailResponse,
    response_model_exclude_none=True,
)
def create_saju_free_detail(
    payload: SajuPreviewRequest,
    request: Request,
) -> SajuFreeDetailResponse:
    """Return the detailed interpretation as a lazy-loadable report."""
    payload_snapshot = to_json_safe(payload)
    request.state.saju_preview_payload = payload_snapshot
    preview_response = create_saju_preview_response(
        payload=payload,
        trace_id=request.state.trace_id,
        debug_requested=request.state.debug_requested,
        service_name=settings.app_name,
        report_mode="interpretation",
    )
    interpretation = preview_response.result.interpretation
    if interpretation is None:  # pragma: no cover - defensive guard; generator returns fallback on LLM failure.
        raise RuntimeError("detail interpretation was not generated")

    response = SajuFreeDetailResponse(
        trace_id=preview_response.trace_id,
        pipeline_status=preview_response.pipeline_status,
        interpretation=interpretation,
        detail_report=interpretation,
        debug_trace=preview_response.debug_trace,
    )
    if _is_http_request(request):
        capture_saju_request_event(
            enabled=settings.request_log_enabled,
            log_path=settings.request_log_path,
            max_bytes=settings.request_log_max_bytes,
            backup_count=settings.request_log_backup_count,
            service=settings.app_name,
            trace_id=request.state.trace_id,
            method=_request_method(request),
            path=_request_path(request),
            status_code=200,
            payload=payload_snapshot,
            debug_requested=request.state.debug_requested,
            include_input=settings.request_log_include_input,
            stage="completed",
            meta={"pipeline_status": response.pipeline_status},
        )
    return response


@router.post("/saju/reports/{report_id}/detail-prepare", response_model=SajuDetailPrepareResponse)
def prepare_saju_detail_bundle(
    report_id: str,
    payload: SajuDetailPrepareRequest,
    request: Request,
) -> SajuDetailPrepareResponse:
    """Prepare cacheable facts for section-level expandable insight details."""
    payload_snapshot = to_json_safe(payload.input)
    request.state.saju_preview_payload = payload_snapshot
    bundle, cached = prepare_detail_analysis_bundle(
        report_id=report_id,
        request_payload=payload.input,
        trace_id=request.state.trace_id,
        service_name=settings.app_name,
    )
    response = SajuDetailPrepareResponse(
        trace_id=request.state.trace_id,
        report_id=report_id,
        input_hash=bundle.input_hash,
        cached=cached,
        available_detail_types=list(DETAIL_TYPES),
        bundle=bundle,
    )
    if _is_http_request(request):
        capture_saju_request_event(
            enabled=settings.request_log_enabled,
            log_path=settings.request_log_path,
            max_bytes=settings.request_log_max_bytes,
            backup_count=settings.request_log_backup_count,
            service=settings.app_name,
            trace_id=request.state.trace_id,
            method=_request_method(request),
            path=_request_path(request),
            status_code=200,
            payload=payload_snapshot,
            debug_requested=request.state.debug_requested,
            include_input=settings.request_log_include_input,
            stage="completed",
            meta={
                "report_id": report_id,
                "input_hash": bundle.input_hash,
                "detail_cache": "hit" if cached else "miss",
            },
        )
    return response


@router.post("/saju/reports/{report_id}/detail-render", response_model=SajuDetailRenderResponse)
def render_saju_detail(
    report_id: str,
    payload: SajuDetailRenderRequest,
    request: Request,
) -> SajuDetailRenderResponse:
    """Render one expandable insight detail from prepared facts."""
    input_hash = payload.input_hash
    bundle = get_cached_detail_bundle(report_id, input_hash) if input_hash else None
    if bundle is None:
        if payload.input is None:
            raise HTTPException(
                status_code=400,
                detail="detail bundle is not prepared",
            )
        bundle, _ = prepare_detail_analysis_bundle(
            report_id=report_id,
            request_payload=payload.input,
            trace_id=request.state.trace_id,
            service_name=settings.app_name,
        )
        input_hash = bundle.input_hash
    if input_hash is None:
        input_hash = (
            compute_detail_input_hash(payload.input)
            if payload.input is not None
            else bundle.input_hash
        )

    report, cached, provider = render_detail_insight(
        report_id=report_id,
        input_hash=input_hash,
        detail_type=payload.detail_type,
        locale=payload.locale,
        bundle=bundle,
    )
    response = SajuDetailRenderResponse(
        trace_id=request.state.trace_id,
        report_id=report_id,
        input_hash=input_hash,
        detail_type=payload.detail_type,
        provider=provider,
        model=_model_for_provider(provider),
        prompt_version=DETAIL_PROMPT_VERSION,
        cached=cached,
        report=report,
        warnings=[],
    )
    if _is_http_request(request):
        capture_saju_request_event(
            enabled=settings.request_log_enabled,
            log_path=settings.request_log_path,
            max_bytes=settings.request_log_max_bytes,
            backup_count=settings.request_log_backup_count,
            service=settings.app_name,
            trace_id=request.state.trace_id,
            method=_request_method(request),
            path=_request_path(request),
            status_code=200,
            payload=to_json_safe(payload),
            debug_requested=request.state.debug_requested,
            include_input=settings.request_log_include_input,
            stage="completed",
            meta={
                "report_id": report_id,
                "input_hash": input_hash,
                "detail_type": payload.detail_type,
                "provider": provider,
            },
        )
    return response
