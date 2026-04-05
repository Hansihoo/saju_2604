export type RegionSuggestion = {
  id: string;
  display_name: string;
  country: string;
  city: string;
  tzid: string;
};

export type RegionSearchResponse = {
  trace_id: string;
  items: RegionSuggestion[];
  total: number;
};

export type SajuPreviewRequest = {
  calendar_type: "solar" | "lunar";
  birth_date: string;
  birth_time: string;
  is_birth_time_estimated: boolean;
  is_lunar_leap_month: boolean;
  gender: "male" | "female";
  region_id: string;
  debug: boolean;
};

export type PipelineStatus = {
  input_validation: string;
  region_resolution: string;
  time_correction: string;
  calendar_normalization: string;
  saju_calculation: string;
  analysis_engine: string;
  llm_formatting: string;
};

export type EvidenceSection = {
  title: string;
  status: "ready" | "disabled" | "coming_soon";
  summary: string;
};

export type TimeCorrectionSummary = {
  tzid: string;
  source_local_datetime: string;
  normalized_local_datetime: string;
  normalized_utc_datetime: string;
  offset_minutes: number;
  ambiguous: boolean;
  fold: number;
};

export type SajuPreviewResponse = {
  trace_id: string;
  response_mode: "mock";
  pipeline_status: PipelineStatus;
  region: RegionSuggestion;
  time_correction: TimeCorrectionSummary;
  calendar_normalization: {
    calendar_type: "solar" | "lunar";
    is_lunar_leap_month: boolean;
    input_date: string;
    input_time: string;
    normalized_solar_datetime: string;
    normalized_lunar_datetime: string;
    solar_year: number;
    solar_month: number;
    solar_day: number;
    solar_hour: number;
    solar_minute: number;
    lunar_year: number;
    lunar_month: number;
    lunar_day: number;
  };
  result: {
    overview: string;
    strengths: string[];
    cautions: string[];
    love: string;
    career: string;
    wealth: string;
    action_advice: string;
    limitations: string[];
    disabled_sections: string[];
    evidence_sections: Record<string, EvidenceSection>;
    hour_pillar_enabled: boolean;
  };
  debug_trace?: {
    stage_order: string[];
    failed_stage?: string | null;
    checkpoints: Array<{
      stage: string;
      status: string;
      note?: string | null;
      error_code?: string | null;
    }>;
    request_echo: Record<string, string>;
  } | null;
};

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
