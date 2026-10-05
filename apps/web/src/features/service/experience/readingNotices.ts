import type { SajuPreviewResponse, UncertaintyFlag } from "../../../shared/api/contracts";
import type { Locale } from "../../../shared/copy";

const messages: Record<string, string> = {
  day_pillar_uncertain_due_to_unknown_time: "출생시간을 모르면 날짜 경계에 따라 하루 기준과 풀이가 달라질 수 있어요.",
  year_or_month_pillar_may_change: "절기가 바뀌는 시각에 가까워 일부 풀이가 달라질 수 있어요.",
  near_solar_term: "절기가 바뀌는 시각에 가까워 일부 풀이가 달라질 수 있어요.",
  midnight_rule_changes_day_pillar: "자정 전후의 계산 기준에 따라 하루 기준과 풀이가 달라질 수 있어요.",
  midnight_rule_changes_hour_pillar: "자정 전후의 계산 기준에 따라 시간에 따른 풀이가 달라질 수 있어요.",
  standard_vs_mean_solar_changes_hour_pillar: "출생지의 시간 보정 방식에 따라 시간에 따른 풀이가 달라질 수 있어요.",
  luck_cycle_start_age_changed: "계산 기준에 따라 대운이 시작되는 나이가 달라질 수 있어요.",
  primary_differs_from_candidate: "계산 기준에 따라 일부 풀이가 달라질 수 있어요.",
};

export function getUncertaintyMessage(flag: UncertaintyFlag, locale: Locale): string {
  if (locale === "en") return flag.user_message;
  return messages[flag.code] ?? "계산 기준에 따라 일부 풀이가 달라질 수 있어요.";
}

export function getReadingNotices(result: SajuPreviewResponse, locale: Locale): string[] {
  return [...new Set((result.result.uncertainty_summary ?? [])
    .filter((flag) => flag.severity === "warning" || flag.severity === "critical")
    .map((flag) => getUncertaintyMessage(flag, locale)))];
}

export function getPrimaryReadingNotice(result: SajuPreviewResponse, locale: Locale): string | undefined {
  const flags = (result.result.uncertainty_summary ?? [])
    .filter((flag) => flag.severity === "warning" || flag.severity === "critical");
  // Date uncertainty affects the reading directly; the rest stays in reference notes.
  const dateBoundary = flags.find((flag) => [
    "day_pillar_uncertain_due_to_unknown_time", "year_or_month_pillar_may_change",
    "midnight_rule_changes_day_pillar", "near_solar_term",
  ].includes(flag.code));
  if (dateBoundary) return getUncertaintyMessage(dateBoundary, locale);
  if (flags.length) return locale === "ko"
    ? "계산 기준에 따라 일부 풀이가 달라질 수 있어요."
    : "Some interpretations may change with calculation conventions.";
  return undefined;
}

export function getShareLimitation(result: SajuPreviewResponse, locale: Locale): string | undefined {
  const uncertain = getReadingNotices(result, locale).length > 0;
  if (!result.result.hour_pillar_enabled) return locale === "ko"
    ? "출생시간 미상 · 일부 풀이가 달라질 수 있어요."
    : "Birth time unknown · Some interpretations may change.";
  if (uncertain) return locale === "ko"
    ? "계산 기준에 따라 일부 풀이가 달라질 수 있어요."
    : "Some interpretations may change with calculation conventions.";
  return undefined;
}
