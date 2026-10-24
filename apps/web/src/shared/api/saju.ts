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
import type { Locale } from "../copy";
import { getApiErrorMessage } from "./errorMessage";
import { requestProgressPreview, type PreviewProgress } from "./previewProgress";
import type { SajuBasicResponse, SajuQuestionResponse } from "./questionContracts";

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

async function parseJsonResponse<T>(response: Response, locale: Locale = "ko"): Promise<T> {
  if (!response.ok) {
    const rawBody = await response.text();
    let parsed: unknown;
    try {
      parsed = JSON.parse(rawBody);
    } catch (_error) {
      parsed = null;
    }
    throw new Error(getApiErrorMessage(response.status, parsed, locale));
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
  options?: { onProgress?: (progress: PreviewProgress) => void; signal?: AbortSignal },
): Promise<SajuPreviewResponse> {
  if (options?.onProgress) return requestProgressPreview({
    baseUrl: API_BASE_URL, payload, onProgress: options.onProgress, signal: options.signal,
  });
  const response = await fetch(`${API_BASE_URL}/saju/preview`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    signal: options?.signal,
  });

  return parseJsonResponse<SajuPreviewResponse>(response, payload.locale);
}

export async function createSajuBasic(
  payload: SajuPreviewRequest,
  options?: { signal?: AbortSignal },
): Promise<SajuBasicResponse> {
  const response = await fetch(`${API_BASE_URL}/saju/basic`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: options?.signal,
  });
  return parseJsonResponse<SajuBasicResponse>(response, payload.locale);
}

export async function createSajuReading(
  payload: SajuPreviewRequest,
  options?: { signal?: AbortSignal; onProgress?: (progress: PreviewProgress) => void },
): Promise<SajuBasicResponse> {
  if (options?.onProgress) return requestProgressPreview({
    baseUrl: API_BASE_URL, payload, endpoint: "/saju/reading", onProgress: options.onProgress,
    signal: options.signal,
  }) as Promise<SajuBasicResponse>;
  return parseJsonResponse<SajuBasicResponse>(await fetch(`${API_BASE_URL}/saju/reading`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload), signal: options?.signal,
  }), payload.locale);
}

export async function createSajuQuestion(
  payload: SajuPreviewRequest,
  questionId: string,
  options?: { signal?: AbortSignal; context?: string | null },
): Promise<SajuQuestionResponse> {
  const response = await fetch(`${API_BASE_URL}/saju/question`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ input: payload, question_id: questionId, context: options?.context ?? null }),
    signal: options?.signal,
  });
  return parseJsonResponse<SajuQuestionResponse>(response, payload.locale);
}

export async function createSajuFreeDetail(
  payload: SajuPreviewRequest,
): Promise<SajuFreeDetailResponse> {
  const response = await fetch(`${API_BASE_URL}/saju/free-detail`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  return parseJsonResponse<SajuFreeDetailResponse>(response, payload.locale);
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
    },
    body: JSON.stringify({
      input: payload,
      detail_type: detailType,
    }),
  });

  return parseJsonResponse<SajuDetailPrepareResponse>(response, payload.locale);
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
    },
    body: JSON.stringify({
      detail_type: detailType,
      input: payload,
      input_hash: inputHash,
      locale: payload.locale,
    }),
  });

  return parseJsonResponse<SajuDetailRenderResponse>(response, payload.locale);
}
