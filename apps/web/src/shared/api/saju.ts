import {
  ApiHealth,
  RegionSearchResponse,
  RegionSuggestion,
  SajuDetailPrepareResponse,
  SajuDetailRenderResponse,
  SajuDetailType,
  SajuFreeDetailResponse,
  SajuPreviewRequest,
  SajuPreviewResponse,
} from "./contracts";

export type {
  ApiHealth,
  RegionSuggestion,
  RegionSearchResponse,
  SajuPreviewRequest,
  SajuPreviewResponse,
  SajuFreeDetailResponse,
  SajuDetailPrepareResponse,
  SajuDetailRenderResponse,
  SajuDetailType,
} from "./contracts";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

async function parseJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const rawBody = await response.text();
    try {
      const parsed = JSON.parse(rawBody) as { message?: string; error_code?: string };
      throw new Error(parsed.message ?? parsed.error_code ?? `Request failed with ${response.status}`);
    } catch (_error) {
      throw new Error(rawBody || `Request failed with ${response.status}`);
    }
  }

  return (await response.json()) as T;
}

export async function getApiHealth(): Promise<ApiHealth> {
  const response = await fetch(`${API_BASE_URL}/health`);
  return parseJsonResponse<ApiHealth>(response);
}

export async function searchRegionSuggestions(query: string): Promise<RegionSuggestion[]> {
  const searchParams = new URLSearchParams({ q: query, limit: "6" });
  const response = await fetch(`${API_BASE_URL}/regions/search?${searchParams.toString()}`);
  const data = await parseJsonResponse<RegionSearchResponse>(response);
  return data.items;
}

export async function createSajuPreview(
  payload: SajuPreviewRequest,
  debug: boolean,
): Promise<SajuPreviewResponse> {
  const response = await fetch(`${API_BASE_URL}/saju/preview`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(debug ? { "X-Saju-Debug": "1" } : {}),
    },
    body: JSON.stringify(payload),
  });

  return parseJsonResponse<SajuPreviewResponse>(response);
}

export async function createSajuFreeDetail(
  payload: SajuPreviewRequest,
  debug: boolean,
): Promise<SajuFreeDetailResponse> {
  const response = await fetch(`${API_BASE_URL}/saju/free-detail`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(debug ? { "X-Saju-Debug": "1" } : {}),
    },
    body: JSON.stringify(payload),
  });

  return parseJsonResponse<SajuFreeDetailResponse>(response);
}

export async function prepareSajuDetailBundle(
  reportId: string,
  payload: SajuPreviewRequest,
  detailType?: SajuDetailType,
): Promise<SajuDetailPrepareResponse> {
  const response = await fetch(`${API_BASE_URL}/saju/reports/${encodeURIComponent(reportId)}/detail-prepare`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(payload.debug ? { "X-Saju-Debug": "1" } : {}),
    },
    body: JSON.stringify({
      input: payload,
      detail_type: detailType,
    }),
  });

  return parseJsonResponse<SajuDetailPrepareResponse>(response);
}

export async function renderSajuDetailInsight(
  reportId: string,
  payload: SajuPreviewRequest,
  detailType: SajuDetailType,
  inputHash?: string,
): Promise<SajuDetailRenderResponse> {
  const response = await fetch(`${API_BASE_URL}/saju/reports/${encodeURIComponent(reportId)}/detail-render`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(payload.debug ? { "X-Saju-Debug": "1" } : {}),
    },
    body: JSON.stringify({
      detail_type: detailType,
      input: payload,
      input_hash: inputHash,
      locale: payload.locale,
    }),
  });

  return parseJsonResponse<SajuDetailRenderResponse>(response);
}
