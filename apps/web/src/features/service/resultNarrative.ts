import { SajuPreviewResponse } from "../../shared/api/contracts";
import { Locale } from "../../shared/copy";
import { formatManseText } from "../shared/manseDisplay";

const elementLabels = {
  ko: {
    wood: "목",
    fire: "화",
    earth: "토",
    metal: "금",
    water: "수",
  },
  en: {
    wood: "Wood",
    fire: "Fire",
    earth: "Earth",
    metal: "Metal",
    water: "Water",
  },
} as const;

type ResultNarrative = {
  overview: string;
  strength: string;
  caution: string;
  love: string;
  career: string;
  wealth: string;
  action: string;
};

function getElementList(locale: Locale, values: string[]) {
  const labels = elementLabels[locale];
  return values.map((value) => labels[value as keyof typeof labels]).join(", ");
}

function getBalanceTone(locale: Locale, score: number) {
  if (locale === "ko") {
    if (score >= 80) return "전반적으로 안정적인 흐름입니다.";
    if (score >= 60) return "비교적 고른 흐름을 보입니다.";
    if (score >= 40) return "강약이 함께 드러나는 흐름입니다.";
    return "한쪽으로 치우치기 쉬운 흐름입니다.";
  }

  if (score >= 80) return "The overall flow is stable.";
  if (score >= 60) return "The overall flow is fairly balanced.";
  if (score >= 40) return "The overall flow shows both strengths and swings.";
  return "The overall flow leans to one side.";
}

function describeScore(locale: Locale, score: number, domain: "love" | "career" | "wealth") {
  const koLabels = {
    love: "관계",
    career: "일",
    wealth: "재물",
  };
  const enLabels = {
    love: "relationships",
    career: "work",
    wealth: "money",
  };

  const label = locale === "ko" ? koLabels[domain] : enLabels[domain];

  if (locale === "ko") {
    if (score >= 75) return `${label} 쪽 강점이 비교적 또렷합니다.`;
    if (score >= 55) return `${label} 쪽 흐름은 무난한 편입니다.`;
    return `${label} 쪽은 신중하게 접근하는 편이 좋습니다.`;
  }

  if (score >= 75) return `There is a clear strength in ${label}.`;
  if (score >= 55) return `The flow in ${label} is fairly steady.`;
  return `A more careful approach is better in ${label}.`;
}

export function buildResultNarrative(
  locale: Locale,
  response: SajuPreviewResponse,
): ResultNarrative {
  const { signals } = response.result;
  const dominant = getElementList(locale, signals.dominant_elements);
  const missing = getElementList(locale, signals.missing_elements);
  const pillars = response.manse.meta.visible_pillar_keys
    .map((key) => formatManseText(response.manse.pillars[key].gan_zhi, locale))
    .filter(Boolean)
    .join(" / ");

  const overview =
    locale === "ko"
      ? `${getBalanceTone(locale, signals.balance_score)} 현재 보이는 기둥은 ${pillars}입니다.`
      : `${getBalanceTone(locale, signals.balance_score)} Visible pillars are ${pillars}.`;

  const strength =
    locale === "ko"
      ? dominant
        ? `${dominant} 기운이 중심을 잡아주는 편입니다.`
        : "두드러지는 강점은 추가 해석 단계에서 더 정교하게 정리됩니다."
      : dominant
        ? `${dominant} leads the visible balance.`
        : "Clear strengths will be refined in the next interpretation stage.";

  const caution =
    locale === "ko"
      ? missing
        ? `${missing} 기운이 약해 한쪽으로 기울 수 있습니다.`
        : "큰 결핍은 없지만 상황에 따라 기복이 생길 수 있습니다."
      : missing
        ? `${missing} is relatively weak, so the flow can lean to one side.`
        : "No major deficiency stands out, but the flow can still fluctuate by context.";

  const action =
    locale === "ko"
      ? missing
        ? `${missing} 기운을 보완하는 생활 리듬과 선택을 의식하면 균형을 잡는 데 도움이 됩니다.`
        : "강한 기운을 유지하되 한쪽으로 과도하게 치우치지 않도록 리듬을 조절하는 것이 좋습니다."
      : missing
        ? `Support ${missing} in your routines and decisions to improve balance.`
        : "Keep your strengths steady while avoiding over-reliance on one side.";

  return {
    overview,
    strength,
    caution,
    love: describeScore(locale, signals.charm_score, "love"),
    career: describeScore(locale, signals.career_score, "career"),
    wealth: describeScore(locale, signals.wealth_score, "wealth"),
    action,
  };
}
