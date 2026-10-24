import type { SajuPreviewResponse } from "../../../shared/api/contracts";
import type { SajuBasicResponse, SajuQuestionResponse, QuestionVersions } from "../../../shared/api/questionContracts";
import type { Locale } from "../../../shared/copy";
import type { ReadingShareContent } from "./shareCard";

export function hasQuestionFlow(result: SajuPreviewResponse): result is SajuBasicResponse {
  return "question_flow" in result && Boolean(result.question_flow);
}

export function matchesQuestionResponse(
  response: SajuQuestionResponse,
  questionId: string,
  versions: QuestionVersions,
): boolean {
  return response.question_id === questionId && response.response_mode === "question"
    && Object.entries(versions).every(([key, value]) => response.versions[key] === value);
}

export function questionShareContent(response: SajuQuestionResponse, locale: Locale): ReadingShareContent {
  return {
    topic: locale === "ko" ? "내 사주 한 장" : "My chart notes",
    title: response.question,
    takeaway: response.answer,
    limitation: response.notices.length ? response.notices.join(" · ") : undefined,
  };
}
