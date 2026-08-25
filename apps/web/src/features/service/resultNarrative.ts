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

function getBalanceTone(locale: Locale, missingElements: string[]) {
  if (locale === "ko") {
    if (!missingElements.length) return "여러 기운이 함께 드러나는 흐름입니다.";
    if (missingElements.length === 1) return "한 기운을 생활 리듬으로 보완해 볼 수 있는 흐름입니다.";
    return "강한 부분과 보완할 부분을 함께 살피는 흐름입니다.";
  }

  if (!missingElements.length) return "Several elements appear together in the visible flow.";
  if (missingElements.length === 1) return "One element can be supported through practical routine.";
  return "The visible flow has both strengths and areas to support.";
}

function describeDomain(locale: Locale, domain: "love" | "career" | "wealth") {
  if (locale === "ko") {
    if (domain === "love") return "관계는 배우자궁과 반복되는 생활 리듬을 함께 살펴봅니다.";
    if (domain === "career") return "일은 월주와 십성의 역할 신호를 함께 살펴봅니다.";
    return "재물은 재성·식상 신호와 실제 소비 습관을 함께 살펴봅니다.";
  }

  if (domain === "love") return "Relationships are considered through spouse-house facts and repeated daily rhythm.";
  if (domain === "career") return "Work is considered through the month pillar and Ten-God role signals.";
  return "Wealth is considered through wealth/output signals and practical spending habits.";
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
      ? `${getBalanceTone(locale, signals.missing_elements)} 현재 보이는 기둥은 ${pillars}입니다.`
      : `${getBalanceTone(locale, signals.missing_elements)} Visible pillars are ${pillars}.`;

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
    love: describeDomain(locale, "love"),
    career: describeDomain(locale, "career"),
    wealth: describeDomain(locale, "wealth"),
    action,
  };
}
