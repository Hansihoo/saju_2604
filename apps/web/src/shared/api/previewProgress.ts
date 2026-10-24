import type { SajuPreviewRequest, SajuPreviewResponse } from "./contracts";
import type { Locale } from "../copy";
import { getApiErrorMessage } from "./errorMessage";

export const previewProgressVersion = "saju-preview-progress-v1";
export type PreviewStage = "sending" | "accepted" | "calculating" | "writing" | "waiting";
export type PreviewProgress = {
  stage: PreviewStage;
  // Only a frame received from this request updates the connection signal.
  lastSignalAt: number | null;
  transport: "stream" | "legacy";
};

type ProgressCallback = (progress: PreviewProgress) => void;
const stages = ["accepted", "calculating", "writing"] as const;

function streamError(locale: Locale): Error {
  return new Error(locale === "ko"
    ? "풀이 연결이 끊겼어요. 잠시 뒤 다시 시도해 주세요."
    : "The reading connection ended. Please try again shortly.");
}

export async function readPreviewStream(
  body: ReadableStream<Uint8Array>,
  locale: Locale,
  onProgress: ProgressCallback,
): Promise<SajuPreviewResponse> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let pending = "";
  let stageIndex = -1;
  function consume(line: string): SajuPreviewResponse | undefined {
    if (!line.trim()) return;
    let frame: Record<string, unknown>;
    try { frame = JSON.parse(line); } catch { throw streamError(locale); }
    if (!frame || typeof frame !== "object" || frame.version !== previewProgressVersion)
      throw streamError(locale);
    if (frame.type === "stage") {
      const next = stages.indexOf(frame.stage as typeof stages[number]);
      if (next !== stageIndex + 1) throw streamError(locale);
      stageIndex = next;
      onProgress({ stage: stages[next], lastSignalAt: Date.now(), transport: "stream" });
    } else if (frame.type === "heartbeat") {
      if (stageIndex < 0) throw streamError(locale);
      onProgress({ stage: stages[stageIndex], lastSignalAt: Date.now(), transport: "stream" });
    } else if (frame.type === "error") {
      throw new Error(getApiErrorMessage(typeof frame.status === "number" ? frame.status : 500, frame.error, locale));
    } else if (frame.type === "result") {
      const data = frame.data as SajuPreviewResponse | undefined;
      if (stageIndex !== stages.length - 1 || !data || typeof data.trace_id !== "string" || !data.result || !data.pipeline_status)
        throw streamError(locale);
      return data;
    } else {
      throw streamError(locale);
    }
  }
  try {
    while (true) {
      const { value, done } = await reader.read();
      pending += done ? decoder.decode() : decoder.decode(value, { stream: true });
      // Bound an incomplete/malformed frame without limiting a valid full report.
      if (pending.length > 16 * 1024 * 1024) throw streamError(locale);
      let newline = pending.indexOf("\n");
      while (newline >= 0) {
        const line = pending.slice(0, newline);
        pending = pending.slice(newline + 1);
        const result = consume(line);
        if (result) return result;
        newline = pending.indexOf("\n");
      }
      if (done) {
        if (pending.trim()) {
          const result = consume(pending);
          if (result) return result;
        }
        throw streamError(locale);
      }
    }
  } finally {
    // No automatic retry: a disconnected generation might still be running.
    try { await reader.cancel(); } catch { /* The connection may already be closed. */ }
    reader.releaseLock();
  }
}

async function readJson(response: Response, locale: Locale): Promise<SajuPreviewResponse> {
  if (!response.ok) {
    let body: unknown = null;
    try { body = await response.json(); } catch { /* Keep diagnostics out of UI. */ }
    throw new Error(getApiErrorMessage(response.status, body, locale));
  }
  return response.json() as Promise<SajuPreviewResponse>;
}

export async function requestProgressPreview({
  baseUrl, payload, onProgress, signal, fetcher = fetch, endpoint = "/saju/preview",
}: {
  baseUrl: string;
  payload: SajuPreviewRequest;
  onProgress: ProgressCallback;
  signal?: AbortSignal;
  fetcher?: typeof fetch;
  endpoint?: "/saju/preview" | "/saju/reading";
}): Promise<SajuPreviewResponse> {
  const options: RequestInit = {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/x-ndjson" },
    body: JSON.stringify(payload), signal,
  };
  const response = await fetcher(`${baseUrl}${endpoint}-stream`, options);
  // Only a missing/unsupported endpoint can fall back; network/stream/provider
  // failures must never trigger another generation automatically.
  if (response.status === 404 || response.status === 405) {
    await response.body?.cancel();
    onProgress({ stage: "waiting", lastSignalAt: null, transport: "legacy" });
    return readJson(await fetcher(`${baseUrl}${endpoint}`, {
      ...options, headers: { "Content-Type": "application/json" },
    }), payload.locale);
  }
  if (!response.ok) return readJson(response, payload.locale);
  if (!response.body || !response.headers.get("content-type")?.includes("application/x-ndjson"))
    throw streamError(payload.locale);
  return readPreviewStream(response.body, payload.locale, onProgress);
}
