import type { Locale } from "../../shared/copy";

export const dokkaebiExpressions = [
  { id: "smile", label: { ko: "방긋", en: "Smile" } },
  { id: "smirk", label: { ko: "능청", en: "Smirk" } },
  { id: "laugh", label: { ko: "폭소", en: "Laugh" } },
  { id: "surprised", label: { ko: "깜짝", en: "Surprised" } },
  { id: "shy", label: { ko: "수줍", en: "Shy" } },
  { id: "unimpressed", label: { ko: "시큰둥", en: "Unimpressed" } },
  { id: "cry", label: { ko: "울먹", en: "Teary" } },
  { id: "sleepy", label: { ko: "졸림", en: "Sleepy" } },
  { id: "wink", label: { ko: "윙크", en: "Wink" } },
] as const;

export type DokkaebiExpression = (typeof dokkaebiExpressions)[number]["id"];

// These describe interface moods, never a judgment about the user's saju.
export const dokkaebiMoods = {
  greeting: "smile",
  reading: "smirk",
  waiting: "sleepy",
  ready: "wink",
  error: "cry",
} as const satisfies Record<string, DokkaebiExpression>;

export const dokkaebiAssetBase = `${import.meta.env.BASE_URL}characters/dokkaebi/`;

export function isDokkaebiExpression(value: unknown): value is DokkaebiExpression {
  return typeof value === "string" && dokkaebiExpressions.some((item) => item.id === value);
}

export function getDokkaebiLabel(expression: DokkaebiExpression, locale: Locale): string {
  return dokkaebiExpressions.find((item) => item.id === expression)!.label[locale];
}

export function getDokkaebiAssetUrl(expression: DokkaebiExpression): string {
  return `${dokkaebiAssetBase}${expression}.png`;
}
