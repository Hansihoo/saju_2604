import type { PreviewProgress, PreviewStage } from "../../../shared/api/previewProgress";
import type { Locale } from "../../../shared/copy";

export const waitingCopyVersion = "waiting-progress-2026-10-07.1";
export const waitingCopy = {
  ko: {
    stepsLabel: "풀이 준비 단계",
    steps: ["정보 접수", "사주 계산", "풀이 정리"],
    done: "완료", active: "진행 중", pending: "대기",
    sending: "출생 정보를 보내고 있어.",
    accepted: "출생 정보 잘 받았어.\n이제 사주부터 계산할게.",
    calculating: "태어난 곳과 출생 정보를 반영해서\n사주를 계산하고 있어.",
    writing: "사주 계산은 끝났어.\n이제 네 풀이를 정리하고 있어.",
    writingLong: "사주 계산은 끝났어.\n풀이를 정리하는 데 시간이 걸리고 있어.",
    waiting: "풀이 결과를 기다리고 있어.",
    longWait: "결과가 도착하면 바로 보여줄게.",
    connected: "응답 연결 유지 중", quiet: "응답 확인이 늦어지고 있어",
    elapsed: "기다린 시간",
  },
  en: {
    stepsLabel: "Reading preparation",
    steps: ["Details received", "Chart calculation", "Reading"],
    done: "Complete", active: "In progress", pending: "Waiting",
    sending: "Sending your birth details.",
    accepted: "Got your birth details.\nYour chart calculation is next.",
    calculating: "Calculating your chart\nwith your birth details and place.",
    writing: "Your chart is calculated.\nNow I'm writing your reading.",
    writingLong: "Your chart is calculated.\nI'm still preparing your reading.",
    waiting: "Waiting for your reading.",
    longWait: "I'll show the result as soon as it arrives.",
    connected: "Response connection active", quiet: "The next response is delayed",
    elapsed: "Time waiting",
  },
} as const;

export function waitingStepStates(stage: PreviewStage): Array<"done" | "active" | "pending"> {
  if (stage === "writing") return ["done", "done", "active"];
  if (stage === "calculating") return ["done", "active", "pending"];
  if (stage === "accepted") return ["done", "pending", "pending"];
  // The legacy JSON transport cannot confirm any intermediate completion.
  if (stage === "waiting") return ["pending", "pending", "pending"];
  return ["active", "pending", "pending"];
}

export function waitingMessage(progress: PreviewProgress, seconds: number, locale: Locale): string {
  const copy = waitingCopy[locale];
  if (progress.stage === "writing") return seconds >= 45 ? copy.writingLong : copy.writing;
  return copy[progress.stage];
}

export function formatWaitingElapsed(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds));
  return `${Math.floor(safe / 60)}:${String(safe % 60).padStart(2, "0")}`;
}

export function hasFreshWaitingSignal(progress: PreviewProgress, now: number): boolean {
  return progress.transport === "stream" && progress.lastSignalAt !== null && now - progress.lastSignalAt < 30_000;
}
