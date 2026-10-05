import type {
  FreePreviewCard,
  SajuPreviewResponse,
} from "../../../shared/api/contracts";
import type { Locale } from "../../../shared/copy";
import { readingTopics, type ReadingTopicKey } from "./experienceCopy";

export type ReadingCard = Omit<FreePreviewCard, "key"> & {
  key: ReadingTopicKey;
  periodLabel?: string;
};

export function getReadingCard(
  result: SajuPreviewResponse,
  key: ReadingTopicKey,
  locale: Locale,
): ReadingCard | null {
  if (key === "today") {
    const flow = result.period_flows.today;
    return {
      key,
      title: readingTopics.find((topic) => topic.key === key)!.label[locale],
      subtitle: flow.headline,
      periodLabel: flow.period_label,
      chips: flow.focus,
      preview_paragraphs: [flow.summary, ...flow.actions.slice(1)],
      user_takeaway: flow.actions[0] || flow.summary,
      next_question: "",
      basis_line: flow.evidence
        .map((item) => `${item.label}: ${item.value}`)
        .join(" · "),
      basis_explanation: flow.basis_explanation,
    };
  }
  const card = result.result.free_preview?.cards.find(
    (item) => item.key === key,
  );
  if (card) return card;
  const title = readingTopics.find((topic) => topic.key === key)!.label[locale];
  const interpretation = result.result.interpretation;
  const sections = {
    core: interpretation?.core_analysis.body || result.result.overview,
    love: interpretation?.love.body || result.result.love,
    work_money: [
      interpretation?.career.body || result.result.career,
      interpretation?.wealth.body || result.result.wealth,
    ]
      .filter(Boolean)
      .join("\n\n"),
    luck_flow: interpretation?.luck_flow.body || "",
  };
  const body = sections[key];
  if (!body.trim()) return null;
  return {
    key,
    title,
    subtitle: title,
    chips: [],
    preview_paragraphs: body.split(/\n\s*\n/).filter(Boolean),
    user_takeaway: result.result.action_advice,
    next_question: "",
    basis_line: "",
  };
}

export function getReadingHeadline(result: SajuPreviewResponse): string {
  return (
    result.result.free_preview?.headline?.trim() ||
    result.result.interpretation?.summary.headline?.trim() ||
    result.result.overview
  );
}
