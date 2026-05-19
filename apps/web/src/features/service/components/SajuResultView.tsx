import {
  type MouseEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  FreePreviewCard,
  FreePreviewDiagnosis,
  FreePreviewDiagnosisKey,
  InterpretationNarrativeSection,
  InterpretationReport,
  ManseLuckCycle,
  SajuDetailRenderedReport,
  SajuDetailType,
  SajuPreviewRequest,
  SajuPreviewResponse,
} from "../../../shared/api/contracts";
import {
  createSajuFreeDetail,
  prepareSajuDetailBundle,
  renderSajuDetailInsight,
} from "../../../shared/api/saju";
import { Locale, getCopy } from "../../../shared/copy";
import { formatManseText } from "../../shared/manseDisplay";

type SajuResultViewProps = {
  locale: Locale;
  result: SajuPreviewResponse;
  detailPayload?: SajuPreviewRequest | null;
  onReset: () => void;
};

type SectionKey = "core_analysis" | "love" | "career" | "wealth" | "luck_flow";
type VisiblePillarKey = "year" | "month" | "day" | "time";
type ElementKey = "wood" | "fire" | "earth" | "metal" | "water";
type DetailLoadState = "idle" | "loading" | "ready" | "error";
type InsightLoadState = "idle" | "loading" | "ready" | "error";

const visiblePillarKeys = ["year", "month", "day", "time"] as const;
const elementKeys: ElementKey[] = ["wood", "fire", "earth", "metal", "water"];

const elementVisualMeta: Record<
  ElementKey,
  {
    color: string;
    ko: string;
    en: string;
  }
> = {
  wood: { color: "#2f9e44", ko: "목", en: "Wood" },
  fire: { color: "#e03131", ko: "화", en: "Fire" },
  earth: { color: "#c98219", ko: "토", en: "Earth" },
  metal: { color: "#64748b", ko: "금", en: "Metal" },
  water: { color: "#1c7ed6", ko: "수", en: "Water" },
};

const elementBalanceCopy: Record<
  Locale,
  {
    title: string;
    subtitle: string;
    dayMaster: string;
    balance: string;
    dominant: string;
    missing: string;
    none: string;
    countUnit: string;
    averageLine: string;
    strong: string;
    empty: string;
    normal: string;
  }
> = {
  ko: {
    title: "오행 밸런스",
    subtitle: "원국에 보이는 목, 화, 토, 금, 수 비율을 계산값 그대로 시각화했습니다.",
    dayMaster: "내 일간",
    balance: "균형",
    dominant: "강한 오행",
    missing: "부족한 오행",
    none: "없음",
    countUnit: "개",
    averageLine: "균형 기준 20%",
    strong: "강함",
    empty: "비어 있음",
    normal: "보통",
  },
  en: {
    title: "Element balance",
    subtitle: "A direct visualization of the Wood, Fire, Earth, Metal, and Water ratios.",
    dayMaster: "Day master",
    balance: "Balance",
    dominant: "Dominant",
    missing: "Missing",
    none: "None",
    countUnit: "",
    averageLine: "20% balance line",
    strong: "Strong",
    empty: "Missing",
    normal: "Normal",
  },
};

const sectionViewCopy: Record<
  Locale,
  {
    summaryLabel: string;
    outlineLabel: string;
    basisLabel: string;
    basisItems: string[];
    uncertaintyTitle: string;
    uncertaintyIntro: string;
    severityLabels: Record<"warning" | "critical", string>;
    sectionLabels: Record<SectionKey, string>;
    heroLabel: string;
    solarTermBadge: string;
    timeCorrectionBadge: string;
    birthTimeWarningBadge: string;
    boundaryWarningBadge: string;
    generalWarningBadge: string;
    coreDiagnosisLabel: string;
    insightLabel: string;
    previewFallback: string;
    cards: {
      core: { title: string; subtitle: string; cta: string };
      workMoney: { title: string; subtitle: string; cta: string };
      love: { title: string; subtitle: string; cta: string };
      luck: { title: string; subtitle: string; cta: string };
    };
  }
> = {
  ko: {
    summaryLabel: "핵심 요약",
    outlineLabel: "빠르게 보기",
    basisLabel: "이 풀이가 보는 것",
    uncertaintyTitle: "확인 필요 항목",
    uncertaintyIntro: "입력값이나 시간 기준 때문에 확정하기 어려운 항목만 표시합니다.",
    severityLabels: {
      warning: "주의",
      critical: "중요",
    },
    basisItems: [
      "만세력 계산을 먼저 확인한 뒤 해석합니다.",
      "강점과 약점을 함께 보여주도록 구성했습니다.",
      "내 사주 특징, 연애운, 직장운, 금전운, 흐름 순서로 읽을 수 있습니다.",
    ],
    sectionLabels: {
      core_analysis: "내 사주 특징",
      love: "연애운",
      career: "직장운",
      wealth: "금전운",
      luck_flow: "대운 흐름",
    },
    heroLabel: "정밀 사주 리포트",
    solarTermBadge: "절기 기준",
    timeCorrectionBadge: "시간대 보정",
    birthTimeWarningBadge: "출생시간 확인 필요",
    boundaryWarningBadge: "경계값 확인 필요",
    generalWarningBadge: "확인 필요 항목 있음",
    coreDiagnosisLabel: "핵심 진단",
    insightLabel: "핵심 카드",
    previewFallback: "상세 해석을 준비 중입니다.",
    cards: {
      core: {
        title: "내 사주 특징",
        subtitle: "성향, 강점, 반복되는 패턴",
        cta: "내 성향 자세히 보기",
      },
      workMoney: {
        title: "일과 돈의 흐름",
        subtitle: "일하는 방식과 돈이 쌓이는 구조",
        cta: "일과 돈의 흐름 보기",
      },
      love: {
        title: "연애와 결혼 흐름",
        subtitle: "관계 스타일과 장기 관계 성향",
        cta: "관계 패턴 보기",
      },
      luck: {
        title: "현재 운과 대운 흐름",
        subtitle: "지금 시기와 다음 변화",
        cta: "지금 시기 보기",
      },
    },
  },
  en: {
    summaryLabel: "Quick summary",
    outlineLabel: "Jump to section",
    basisLabel: "What this reading uses",
    uncertaintyTitle: "Items to confirm",
    uncertaintyIntro: "Only user-relevant uncertainty from the provided inputs is shown here.",
    severityLabels: {
      warning: "Warning",
      critical: "Important",
    },
    basisItems: [
      "The manse calculation is checked before the interpretation is written.",
      "The reading is designed to show both strengths and weak points.",
      "You can read it in order: core traits, love, career, wealth, and luck flow.",
    ],
    sectionLabels: {
      core_analysis: "Core traits",
      love: "Love",
      career: "Career",
      wealth: "Wealth",
      luck_flow: "Luck flow",
    },
    heroLabel: "Precision saju report",
    solarTermBadge: "Solar-term basis",
    timeCorrectionBadge: "Time-zone corrected",
    birthTimeWarningBadge: "Birth time needs review",
    boundaryWarningBadge: "Boundary needs review",
    generalWarningBadge: "Items need review",
    coreDiagnosisLabel: "Core diagnosis",
    insightLabel: "Quick insight cards",
    previewFallback: "The detailed reading is being prepared.",
    cards: {
      core: {
        title: "Core traits",
        subtitle: "Tendencies, strengths, and repeating patterns",
        cta: "Read core traits",
      },
      workMoney: {
        title: "Work and money flow",
        subtitle: "Work style and how money can accumulate",
        cta: "View work and money",
      },
      love: {
        title: "Love and long-term relationships",
        subtitle: "Relationship style and long-term patterns",
        cta: "View relationship pattern",
      },
      luck: {
        title: "Current and next luck flow",
        subtitle: "Current timing and the next shift",
        cta: "View current timing",
      },
    },
  },
};

const insightCardMeta: Record<
  Locale,
  Record<
    "core" | "workMoney" | "love" | "luck",
    {
      chips: string[];
      basis: string;
    }
  >
> = {
  ko: {
    core: {
      chips: ["기준", "강점", "반복 패턴"],
      basis: "일간·오행·십성 구조를 함께 반영했습니다.",
    },
    workMoney: {
      chips: ["일하는 방식", "수입 구조", "관리 포인트"],
      basis: "직장운과 금전운을 연결해서 해석했습니다.",
    },
    love: {
      chips: ["관계 스타일", "잘 맞는 상대", "장기 관계"],
      basis: "배우자궁·관계 신호·현재 흐름을 함께 봅니다.",
    },
    luck: {
      chips: ["현재 시기", "다음 변화", "준비할 것"],
      basis: "현재 대운과 다음 대운의 변화를 중심으로 봅니다.",
    },
  },
  en: {
    core: {
      chips: ["Standards", "Strengths", "Patterns"],
      basis: "Reflects the day master, five elements, and ten-god structure together.",
    },
    workMoney: {
      chips: ["Work style", "Income structure", "Management point"],
      basis: "Connects the career and wealth readings instead of treating them separately.",
    },
    love: {
      chips: ["Relationship style", "Good fit", "Long-term bond"],
      basis: "Reviews spouse-house, relationship signals, and the current flow together.",
    },
    luck: {
      chips: ["Current timing", "Next shift", "Preparation"],
      basis: "Centers on the current luck cycle and the next luck-cycle transition.",
    },
  },
};

const diagnosisTitleByKey: Record<Locale, Record<FreePreviewDiagnosisKey, string>> = {
  ko: {
    strongest_point: "가장 강한 점",
    repeating_pattern: "반복되는 패턴",
    current_task: "지금 시기 과제",
  },
  en: {
    strongest_point: "Strongest point",
    repeating_pattern: "Repeating pattern",
    current_task: "Current task",
  },
};

const detailLazyCopy: Record<
  Locale,
  {
    label: string;
    title: string;
    body: string;
    button: string;
    loadingTitle: string;
    loadingBody: string;
    fallbackNotice: string;
    errorTitle: string;
  }
> = {
  ko: {
    label: "상세 리포트",
    title: "상세 리포트를 이어서 읽을 수 있습니다",
    body: "첫 화면 요약을 먼저 읽은 뒤, 내 사주 특징과 일과 돈, 관계, 대운 흐름을 더 자세히 펼쳐 봅니다.",
    button: "상세 리포트 불러오기",
    loadingTitle: "상세 리포트를 불러오는 중입니다",
    loadingBody:
      "앞에서 계산한 사주 정보를 바탕으로 상세 해석을 준비하고 있습니다. 내용이 길어 시간이 조금 오래 걸릴 수 있습니다.",
    fallbackNotice: "상세 리포트 호출이 지연되어 기본 상세 결과를 표시합니다.",
    errorTitle: "상세 리포트를 불러오지 못했습니다",
  },
  en: {
    label: "Detailed report",
    title: "Continue with the detailed report",
    body: "After the first-screen preview, load the detailed reading for core traits, work and money, relationships, and luck flow.",
    button: "Load detailed report",
    loadingTitle: "Loading the detailed report",
    loadingBody:
      "The detailed reading is being prepared from the chart information already calculated. Longer reports can take a little more time.",
    fallbackNotice: "The detail request was delayed, so the embedded detail report is shown instead.",
    errorTitle: "Could not load the detailed report",
  },
};

type SectionInsightCopy = {
  detailType: SajuDetailType;
  title: string;
  description: string;
};

const sectionInsightCopy: Record<
  Locale,
  {
    headings: {
      core: string;
      career: string;
      wealth: string;
      love: string;
      luck: string;
    };
    status: {
      loading: string;
      error: string;
      compatibilityTitle: string;
      compatibilityBody: string;
    };
    items: Record<SajuDetailType, SectionInsightCopy>;
  }
> = {
  ko: {
    headings: {
      core: "생활에서 더 살펴볼 부분",
      career: "더 살펴볼 일의 흐름",
      wealth: "더 살펴볼 돈의 흐름",
      love: "더 살펴볼 관계 흐름",
      luck: "올해와 월별 흐름",
    },
    status: {
      loading: "확장 해석을 준비하고 있습니다. 내용에 따라 시간이 조금 걸릴 수 있습니다.",
      error: "지금은 확장 해석을 불러오지 못했습니다. 잠시 후 다시 열어 주세요.",
      compatibilityTitle: "상대 정보가 필요합니다",
      compatibilityBody: "상대의 생년월일, 출생시간, 성별, 출생지역을 입력하면 두 사람의 관계 흐름을 따로 비교할 수 있습니다.",
    },
    items: {
      relationship_support: {
        detailType: "relationship_support",
        title: "인간관계와 귀인 보기",
        description: "도움 되는 사람과 피로해지기 쉬운 관계 패턴을 봅니다.",
      },
      health_condition: {
        detailType: "health_condition",
        title: "건강과 컨디션 보기",
        description: "오행 균형과 현재 흐름을 바탕으로 생활 리듬 관리 포인트를 봅니다.",
      },
      career_timing: {
        detailType: "career_timing",
        title: "이직과 커리어 전환 시기 보기",
        description: "움직임을 검토하기 좋은 시기와 보수적으로 봐야 할 시기를 나눠 봅니다.",
      },
      wealth_timing: {
        detailType: "wealth_timing",
        title: "금전 흐름이 좋아지는 시기 보기",
        description: "수입 기회와 지출 누수가 함께 보이는 시기를 봅니다.",
      },
      love_timing: {
        detailType: "love_timing",
        title: "연애운이 좋아지는 시기 보기",
        description: "관계 기회가 늘기 쉬운 시기를 세운과 월운 기준으로 봅니다.",
      },
      ideal_partner: {
        detailType: "ideal_partner",
        title: "나와 잘 맞는 사람 유형 보기",
        description: "내 사주 구조를 편하게 해주는 상대 유형을 봅니다.",
      },
      compatibility_compare: {
        detailType: "compatibility_compare",
        title: "상대와 궁합 비교하기",
        description: "상대 정보를 입력하면 두 사람의 관계 흐름을 비교합니다.",
      },
      yearly_caution: {
        detailType: "yearly_caution",
        title: "올해 조심할 흐름 보기",
        description: "올해 관계, 일, 돈에서 조심할 흐름을 정리합니다.",
      },
      monthly_flow: {
        detailType: "monthly_flow",
        title: "월별 흐름 보기",
        description: "체감하기 쉬운 월별 실행 타이밍을 봅니다.",
      },
    },
  },
  en: {
    headings: {
      core: "More to review in daily life",
      career: "More about work timing",
      wealth: "More about money flow",
      love: "More relationship timing",
      luck: "This year and monthly flow",
    },
    status: {
      loading: "Preparing the expanded insight. Longer details can take a little more time.",
      error: "The expanded insight could not be loaded. Try opening it again in a moment.",
      compatibilityTitle: "Partner information is needed",
      compatibilityBody: "Enter the other person's birth date, time, gender, and region to compare the relationship flow separately.",
    },
    items: {
      relationship_support: {
        detailType: "relationship_support",
        title: "View helpful relationships",
        description: "See people who can help and patterns that may become tiring.",
      },
      health_condition: {
        detailType: "health_condition",
        title: "View condition and rhythm",
        description: "Review lifestyle rhythm points from element balance and current timing.",
      },
      career_timing: {
        detailType: "career_timing",
        title: "View career transition timing",
        description: "Separate timing for movement from timing that should stay conservative.",
      },
      wealth_timing: {
        detailType: "wealth_timing",
        title: "View money-flow timing",
        description: "Review periods where income opportunity and leakage both need attention.",
      },
      love_timing: {
        detailType: "love_timing",
        title: "View relationship timing",
        description: "Review periods when relationship openings can become easier.",
      },
      ideal_partner: {
        detailType: "ideal_partner",
        title: "View a fitting person type",
        description: "See traits that may feel less draining for your structure.",
      },
      compatibility_compare: {
        detailType: "compatibility_compare",
        title: "Compare with another person",
        description: "Enter partner information to compare the relationship flow.",
      },
      yearly_caution: {
        detailType: "yearly_caution",
        title: "View what to watch this year",
        description: "Review caution points in relationships, work, and money.",
      },
      monthly_flow: {
        detailType: "monthly_flow",
        title: "View monthly flow",
        description: "See practical month-by-month timing points.",
      },
    },
  },
};

const resultDataCopy: Record<
  Locale,
  {
    pillarTitle: string;
    pillarSubtitle: string;
    correctedTimeLabel: string;
    ganZhiRow: string;
    stemRow: string;
    branchRow: string;
    luckTimelineTitle: string;
    luckTimelineSubtitle: string;
    luckPillarColumn: string;
    luckStartColumn: string;
    luckChangeColumn: string;
    luckCurrentLabel: string;
    luckNextLabel: string;
    luckAgeRangeLabel: string;
    luckPeriodLabel: string;
    luckCurrentHelp: string;
    luckNextHelp: string;
    unavailable: string;
    pillarColumns: Record<VisiblePillarKey, string>;
  }
> = {
  ko: {
    pillarTitle: "사주팔자",
    pillarSubtitle: "만세력 기준 핵심 기둥",
    correctedTimeLabel: "보정 기준",
    ganZhiRow: "간지",
    stemRow: "천간",
    branchRow: "지지",
    luckTimelineTitle: "대운 전환 시점",
    luckTimelineSubtitle: "대운의 시작과 다음 전환 시점을 년/월 기준으로 정리했습니다.",
    luckPillarColumn: "대운",
    luckStartColumn: "시작 시점",
    luckChangeColumn: "변경 시점",
    luckCurrentLabel: "현재 대운",
    luckNextLabel: "다음 대운",
    luckAgeRangeLabel: "나이",
    luckPeriodLabel: "기간",
    luckCurrentHelp: "지금 해석의 중심이 되는 흐름입니다.",
    luckNextHelp: "다음 전환에서 달라지는 흐름입니다.",
    unavailable: "-",
    pillarColumns: {
      year: "년주",
      month: "월주",
      day: "일주",
      time: "시주",
    },
  },
  en: {
    pillarTitle: "Four pillars",
    pillarSubtitle: "Core pillars from the manse data",
    correctedTimeLabel: "Corrected base",
    ganZhiRow: "Ganji",
    stemRow: "Stem",
    branchRow: "Branch",
    luckTimelineTitle: "Luck-cycle transition points",
    luckTimelineSubtitle: "Luck-cycle starts and transitions are shown by year and month.",
    luckPillarColumn: "Cycle",
    luckStartColumn: "Starts",
    luckChangeColumn: "Changes",
    luckCurrentLabel: "Current cycle",
    luckNextLabel: "Next cycle",
    luckAgeRangeLabel: "Age",
    luckPeriodLabel: "Period",
    luckCurrentHelp: "This is the main timing context for the current reading.",
    luckNextHelp: "This is the next visible timing shift.",
    unavailable: "-",
    pillarColumns: {
      year: "Year",
      month: "Month",
      day: "Day",
      time: "Time",
    },
  },
};

const disabledStateCopy: Record<
  Locale,
  {
    disabledBadge: string;
    disabledValue: string;
    unknownTimeNoticeTitle: string;
    unknownTimeNoticeBody: string;
    unknownTimeMetaLabel: string;
    unknownTimeMetaValue: string;
    timePillarDisabledNote: string;
    luckTimelineDisabledNote: string;
  }
> = {
  ko: {
    disabledBadge: "비활성화",
    disabledValue: "비활성화",
    unknownTimeNoticeTitle: "출생시간을 몰라 시주 기반 항목을 비활성화했어요.",
    unknownTimeNoticeBody:
      "시주, 시주 기반 대운, 시간 의존 해석은 숨기지 않고 비활성 상태로 표시합니다. 정확한 시간이 확인되면 다시 계산해 전체 결과를 열 수 있어요.",
    unknownTimeMetaLabel: "출생시간 상태",
    unknownTimeMetaValue: "시간 모름",
    timePillarDisabledNote: "시주는 정확한 출생시간이 확인되면 다시 열립니다.",
    luckTimelineDisabledNote: "대운 시작 시점과 흐름은 출생시간이 확인되면 다시 계산됩니다.",
  },
  en: {
    disabledBadge: "Disabled",
    disabledValue: "Disabled",
    unknownTimeNoticeTitle: "Birth time is unknown, so hour-based items are disabled.",
    unknownTimeNoticeBody:
      "The time pillar, hour-based luck-cycle details, and time-dependent interpretation stay visible in a disabled state until the real birth time is known.",
    unknownTimeMetaLabel: "Birth-time status",
    unknownTimeMetaValue: "Unknown time",
    timePillarDisabledNote: "The time pillar will unlock after the birth time is confirmed.",
    luckTimelineDisabledNote:
      "Luck-cycle start points and transitions will be recalculated after the birth time is confirmed.",
  },
};

type PillarEntry = {
  key: VisiblePillarKey;
  label: string;
  pillar: SajuPreviewResponse["manse"]["pillars"][VisiblePillarKey];
};

function getPillarEntries(result: SajuPreviewResponse, locale: Locale): PillarEntry[] {
  const labels = resultDataCopy[locale].pillarColumns;
  return visiblePillarKeys.map((key) => ({
    key,
    label: labels[key],
    pillar: result.manse.pillars[key],
  }));
}

function getDisabledClassName(enabled: boolean) {
  return enabled ? undefined : "is-disabled";
}

function renderPillarValue(
  value: string | null | undefined,
  options: {
    locale: Locale;
    enabled: boolean;
  },
) {
  if (!options.enabled) {
    return disabledStateCopy[options.locale].disabledValue;
  }

  return formatManseText(value, options.locale);
}

function formatYearMonth(value: string | null | undefined, locale: Locale) {
  if (!value) {
    return resultDataCopy[locale].unavailable;
  }

  const match = value.match(/^(\d{4})-(\d{2})/);
  if (!match) {
    return value;
  }

  const year = match[1];
  const month = String(Number(match[2]));

  if (locale === "ko") {
    return `${year}년 ${month}월`;
  }

  const monthNames = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
  ];
  return `${monthNames[Number(month) - 1]} ${year}`;
}

function parseOptionalDate(value: string | null | undefined) {
  if (!value) {
    return null;
  }

  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function isCycleActive(cycle: ManseLuckCycle, now: Date) {
  const start = parseOptionalDate(cycle.start_datetime);
  const change = parseOptionalDate(cycle.change_datetime);

  if (start && change) {
    return now >= start && now < change;
  }

  const currentYear = now.getFullYear();
  return currentYear >= cycle.start_year && currentYear <= cycle.end_year;
}

function findLuckCycleFocus(cycles: ManseLuckCycle[]) {
  if (!cycles.length) {
    return { current: null, next: null };
  }

  const now = new Date();
  const currentIndex = cycles.findIndex((cycle) => isCycleActive(cycle, now));

  if (currentIndex >= 0) {
    return {
      current: cycles[currentIndex],
      next: cycles[currentIndex + 1] ?? null,
    };
  }

  const futureIndex = cycles.findIndex((cycle) => {
    const start = parseOptionalDate(cycle.start_datetime);
    return start ? start > now : cycle.start_year > now.getFullYear();
  });

  if (futureIndex >= 0) {
    return {
      current: null,
      next: cycles[futureIndex],
    };
  }

  return {
    current: cycles[cycles.length - 1],
    next: null,
  };
}

function isSameLuckCycle(left: ManseLuckCycle | null, right: ManseLuckCycle) {
  return Boolean(left && left.index === right.index && left.gan_zhi === right.gan_zhi);
}

function getElementLabel(key: ElementKey, locale: Locale) {
  return elementVisualMeta[key][locale];
}

function getElementListText(values: ElementKey[], locale: Locale) {
  if (!values.length) {
    return elementBalanceCopy[locale].none;
  }

  return values.map((value) => getElementLabel(value, locale)).join(", ");
}

function getElementStatus(
  key: ElementKey,
  dominantElements: ElementKey[],
  missingElements: ElementKey[],
  locale: Locale,
) {
  const text = elementBalanceCopy[locale];

  if (missingElements.includes(key)) {
    return text.empty;
  }

  if (dominantElements.includes(key)) {
    return text.strong;
  }

  return text.normal;
}

function getRadarPoints(values: number[], maxValue: number) {
  const size = 190;
  const center = size / 2;
  const radius = 66;

  return values
    .map((value, index) => {
      const angle = (-90 + index * 72) * (Math.PI / 180);
      const ratio = Math.max(0.08, Math.min(1, value / maxValue));
      const x = center + Math.cos(angle) * radius * ratio;
      const y = center + Math.sin(angle) * radius * ratio;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

function getAxisPoint(index: number, radius: number) {
  const size = 190;
  const center = size / 2;
  const angle = (-90 + index * 72) * (Math.PI / 180);

  return {
    x: center + Math.cos(angle) * radius,
    y: center + Math.sin(angle) * radius,
  };
}

function ElementBalanceCard({ locale, result }: { locale: Locale; result: SajuPreviewResponse }) {
  const text = elementBalanceCopy[locale];
  const percentages = result.manse.analysis.element_percentages;
  const counts = result.manse.elements;
  const dominantElements = result.manse.analysis.dominant_elements;
  const missingElements = result.manse.analysis.missing_elements;
  const maxPercentage = Math.max(20, ...elementKeys.map((key) => percentages[key]));
  const outerPentagon = getRadarPoints([maxPercentage, maxPercentage, maxPercentage, maxPercentage, maxPercentage], maxPercentage);
  const averagePentagon = getRadarPoints([20, 20, 20, 20, 20], maxPercentage);
  const dataPentagon = getRadarPoints(
    elementKeys.map((key) => percentages[key]),
    maxPercentage,
  );

  const items = elementKeys.map((key) => ({
    key,
    label: getElementLabel(key, locale),
    color: elementVisualMeta[key].color,
    percentage: percentages[key],
    count: counts[key],
    status: getElementStatus(key, dominantElements, missingElements, locale),
  }));

  return (
    <section className="element-balance-card">
      <div className="element-balance-head">
        <div>
          <p className="result-panel-label">{text.title}</p>
          <p className="reading-data-card-note">{text.subtitle}</p>
        </div>
        <div className="element-balance-meta">
          <span>{text.dayMaster}</span>
          <strong>{formatManseText(result.manse.meta.day_master, locale)}</strong>
        </div>
      </div>

      <div className="element-balance-body">
        <div className="element-radar-wrap" aria-label={text.title}>
          <svg className="element-radar" viewBox="0 0 190 190" role="img">
            <polygon className="element-radar-outer" points={outerPentagon} />
            <polygon className="element-radar-average" points={averagePentagon} />
            {elementKeys.map((key, index) => {
              const point = getAxisPoint(index, 72);
              const labelPoint = getAxisPoint(index, 84);
              return (
                <g key={key}>
                  <line className="element-radar-axis" x1="95" y1="95" x2={point.x} y2={point.y} />
                  <text className="element-radar-label" x={labelPoint.x} y={labelPoint.y}>
                    {getElementLabel(key, locale)}
                  </text>
                </g>
              );
            })}
            <polygon className="element-radar-data" points={dataPentagon} />
          </svg>
          <span>{text.averageLine}</span>
        </div>

        <div className="element-balance-bars">
          {items.map((item) => (
            <div
              className={`element-balance-row${missingElements.includes(item.key) ? " is-missing" : ""}`}
              key={item.key}
            >
              <div className="element-balance-row-head">
                <span>
                  <i style={{ backgroundColor: item.color }} />
                  {item.label}
                </span>
                <strong>
                  {locale === "ko" ? `${item.count}${text.countUnit}` : `${item.count}`}
                </strong>
              </div>
              <div className="element-balance-track">
                <span className="element-balance-average-marker" />
                <span
                  className="element-balance-fill"
                  style={{ backgroundColor: item.color, width: `${Math.min(item.percentage, 100)}%` }}
                />
              </div>
              <small>
                {locale === "ko" ? `${item.count}${text.countUnit}` : `${item.count}`}
                {" · "}
                {item.status}
              </small>
            </div>
          ))}
        </div>
      </div>

      <div className="element-balance-chips">
        <span>
          {text.dominant} <strong>{getElementListText(dominantElements, locale)}</strong>
        </span>
        <span>
          {text.missing} <strong>{getElementListText(missingElements, locale)}</strong>
        </span>
      </div>
    </section>
  );
}

function formatAgeRange(cycle: ManseLuckCycle, locale: Locale) {
  if (
    cycle.start_age_years != null &&
    cycle.start_age_months != null &&
    cycle.change_age_years != null &&
    cycle.change_age_months != null
  ) {
    if (locale === "ko") {
      return `${cycle.start_age_years}세 ${cycle.start_age_months}개월-${cycle.change_age_years}세 ${cycle.change_age_months}개월`;
    }

    return `Age ${cycle.start_age_years}y ${cycle.start_age_months}m-${cycle.change_age_years}y ${cycle.change_age_months}m`;
  }

  if (locale === "ko") {
    return `${cycle.start_age}세-${cycle.end_age}세`;
  }

  return `Age ${cycle.start_age}-${cycle.end_age}`;
}

function formatLuckPeriod(cycle: ManseLuckCycle, locale: Locale) {
  return `${formatYearMonth(cycle.start_datetime, locale)} - ${formatYearMonth(
    cycle.change_datetime,
    locale,
  )}`;
}

function CompactPillarTable({
  locale,
  result,
}: {
  locale: Locale;
  result: SajuPreviewResponse;
}) {
  const ui = resultDataCopy[locale];
  const statusTexts = disabledStateCopy[locale];
  const pillars = getPillarEntries(result, locale);
  const isBirthTimeUnknown = !result.result.hour_pillar_enabled;

  return (
    <section className="result-pillar-overview">
      <div className="result-pillar-overview-head">
        <div>
          <p className="result-panel-label">{ui.pillarTitle}</p>
          <p className="result-pillar-overview-note">{ui.pillarSubtitle}</p>
        </div>
        <div className={`result-pillar-overview-meta${isBirthTimeUnknown ? " is-disabled" : ""}`}>
          <span>{isBirthTimeUnknown ? statusTexts.unknownTimeMetaLabel : ui.correctedTimeLabel}</span>
          <strong>
            {isBirthTimeUnknown
              ? statusTexts.unknownTimeMetaValue
              : result.regional_solar_correction.corrected_solar_datetime}
          </strong>
          {isBirthTimeUnknown ? <small>{statusTexts.timePillarDisabledNote}</small> : null}
        </div>
      </div>

      <div className="reading-table-wrap">
        <table className="reading-table result-pillar-table compact">
          <thead>
            <tr>
              {pillars.map(({ key, label, pillar }) => (
                <th key={key} className={getDisabledClassName(pillar.enabled)}>
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              {pillars.map(({ key, pillar }) => (
                <td key={key} className={getDisabledClassName(pillar.enabled)}>
                  <strong>
                    {renderPillarValue(pillar.gan_zhi, {
                      locale,
                      enabled: pillar.enabled,
                    })}
                  </strong>
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  );
}

function DetailedPillarTable({
  locale,
  result,
}: {
  locale: Locale;
  result: SajuPreviewResponse;
}) {
  const ui = resultDataCopy[locale];
  const pillars = getPillarEntries(result, locale);

  return (
    <div className="reading-data-card">
      <div className="reading-data-card-head">
        <div>
          <p className="result-panel-label">{ui.pillarTitle}</p>
          <p className="reading-data-card-note">{ui.pillarSubtitle}</p>
        </div>
      </div>

      <div className="reading-table-wrap">
        <table className="reading-table result-pillar-table">
          <thead>
            <tr>
              <th />
              {pillars.map(({ key, label, pillar }) => (
                <th key={key} className={getDisabledClassName(pillar.enabled)}>
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <th>{ui.ganZhiRow}</th>
              {pillars.map(({ key, pillar }) => (
                <td key={key} className={getDisabledClassName(pillar.enabled)}>
                  <strong>
                    {renderPillarValue(pillar.gan_zhi, {
                      locale,
                      enabled: pillar.enabled,
                    })}
                  </strong>
                </td>
              ))}
            </tr>
            <tr>
              <th>{ui.stemRow}</th>
              {pillars.map(({ key, pillar }) => (
                <td key={key} className={getDisabledClassName(pillar.enabled)}>
                  {renderPillarValue(pillar.stem, {
                    locale,
                    enabled: pillar.enabled,
                  })}
                </td>
              ))}
            </tr>
            <tr>
              <th>{ui.branchRow}</th>
              {pillars.map(({ key, pillar }) => (
                <td key={key} className={getDisabledClassName(pillar.enabled)}>
                  {renderPillarValue(pillar.branch, {
                    locale,
                    enabled: pillar.enabled,
                  })}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

function LuckFocusCard({
  label,
  help,
  cycle,
  locale,
}: {
  label: string;
  help: string;
  cycle: ManseLuckCycle | null;
  locale: Locale;
}) {
  const ui = resultDataCopy[locale];
  const statusTexts = disabledStateCopy[locale];

  return (
    <article className={`luck-focus-card${cycle ? "" : " is-disabled"}`}>
      <span className="luck-focus-label">{label}</span>
      <strong>{cycle ? formatManseText(cycle.gan_zhi, locale) : statusTexts.disabledValue}</strong>
      {cycle ? (
        <dl>
          <div>
            <dt>{ui.luckAgeRangeLabel}</dt>
            <dd>{formatAgeRange(cycle, locale)}</dd>
          </div>
          <div>
            <dt>{ui.luckPeriodLabel}</dt>
            <dd>{formatLuckPeriod(cycle, locale)}</dd>
          </div>
        </dl>
      ) : null}
      <p>{cycle ? help : statusTexts.luckTimelineDisabledNote}</p>
    </article>
  );
}

function LuckTimelineTable({
  locale,
  result,
}: {
  locale: Locale;
  result: SajuPreviewResponse;
}) {
  const ui = resultDataCopy[locale];
  const statusTexts = disabledStateCopy[locale];
  const isDisabled = !result.manse.luck_cycles_enabled || !result.manse.luck_cycles.length;
  const focus = isDisabled
    ? { current: null, next: null }
    : findLuckCycleFocus(result.manse.luck_cycles);

  return (
    <div className={`reading-data-card${isDisabled ? " is-disabled" : ""}`}>
      <div className="reading-data-card-head">
        <div>
          <p className="result-panel-label">{ui.luckTimelineTitle}</p>
          <p className="reading-data-card-note">{ui.luckTimelineSubtitle}</p>
        </div>
      </div>

      <div className="luck-focus-grid">
        <LuckFocusCard
          label={ui.luckCurrentLabel}
          help={ui.luckCurrentHelp}
          cycle={focus.current}
          locale={locale}
        />
        <LuckFocusCard
          label={ui.luckNextLabel}
          help={ui.luckNextHelp}
          cycle={focus.next}
          locale={locale}
        />
      </div>

      <div className="reading-table-wrap">
        <table className="reading-table result-luck-table">
          <thead>
            <tr>
              <th>{ui.luckPillarColumn}</th>
              <th>{ui.luckStartColumn}</th>
              <th>{ui.luckChangeColumn}</th>
            </tr>
          </thead>
          <tbody>
            {isDisabled ? (
              <tr>
                <td className="is-disabled">
                  <strong>{statusTexts.disabledValue}</strong>
                </td>
                <td className="is-disabled">{statusTexts.disabledValue}</td>
                <td className="is-disabled">{statusTexts.disabledValue}</td>
              </tr>
            ) : (
              result.manse.luck_cycles.map((cycle) => (
                <tr
                  key={`${cycle.index}-${cycle.gan_zhi}`}
                  className={
                    isSameLuckCycle(focus.current, cycle)
                      ? "is-current"
                      : isSameLuckCycle(focus.next, cycle)
                        ? "is-next"
                        : undefined
                  }
                >
                  <td>
                    <strong>{formatManseText(cycle.gan_zhi, locale)}</strong>
                  </td>
                  <td>{formatYearMonth(cycle.start_datetime, locale)}</td>
                  <td>{formatYearMonth(cycle.change_datetime, locale)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {isDisabled ? (
        <p className="reading-disabled-note">{statusTexts.luckTimelineDisabledNote}</p>
      ) : null}
    </div>
  );
}

function UncertaintySummaryNotice({
  locale,
  result,
}: {
  locale: Locale;
  result: SajuPreviewResponse;
}) {
  const text = sectionViewCopy[locale];
  const formatMessage = (
    flag: SajuPreviewResponse["result"]["uncertainty_summary"][number],
  ) => {
    const message = flag.user_message;
    if (locale !== "ko") {
      return message;
    }

    const messagesByCode: Record<string, string> = {
      day_pillar_uncertain_due_to_unknown_time:
        "출생시간을 모르면 자정 전후 경계 때문에 하루 기준을 확정하기 어렵습니다.",
      year_or_month_pillar_may_change:
        "출생시간 후보 범위 안에 절기 경계가 있어 해석 기준이 달라질 수 있습니다.",
      midnight_rule_changes_day_pillar: "자정 기준 적용 방식에 따라 일주가 달라질 수 있습니다.",
      midnight_rule_changes_hour_pillar: "자정 기준 적용 방식에 따라 시주가 달라질 수 있습니다.",
      standard_vs_mean_solar_changes_hour_pillar:
        "표준시와 지역시차 보정 기준에 따라 시주가 달라질 수 있습니다.",
      luck_cycle_start_age_changed: "보정 기준 후보에 따라 대운 시작 나이가 달라질 수 있습니다.",
      primary_differs_from_candidate: "보정 기준 후보 중 일부가 현재 기준 사주와 다르게 계산됩니다.",
      near_solar_term: "입력 시간이 절기 경계에 가까워 일부 해석 기준이 달라질 수 있습니다.",
    };

    const translated = messagesByCode[flag.code];
    if (translated) {
      return translated;
    }

    if (message.includes("midnight rule")) {
      return "자정 기준 적용 방식에 따라 일주가 달라질 수 있습니다.";
    }

    if (message.includes("unknown birth-time interval includes the late-zi boundary")) {
      return "출생시간을 모르면 자정 전후 경계 때문에 하루 기준을 확정하기 어렵습니다.";
    }

    if (message.includes("hour pillar changes")) {
      return "표준시와 지역시차 보정 기준에 따라 시주가 달라질 수 있습니다.";
    }

    if (message.includes("candidate chart differs")) {
      return "보정 기준 후보 중 일부가 현재 기준 사주와 다르게 계산됩니다.";
    }

    return message;
  };
  const flags = (result.result.uncertainty_summary ?? []).filter(
    (flag) => flag.severity === "warning" || flag.severity === "critical",
  );

  if (!flags.length) {
    return null;
  }

  return (
    <section className="result-uncertainty-notice">
      <div className="result-uncertainty-head">
        <span className="result-panel-label">{text.uncertaintyTitle}</span>
        <p>{text.uncertaintyIntro}</p>
      </div>
      <ul>
        {flags.map((flag) => {
          const severity = flag.severity === "critical" ? "critical" : "warning";
          return (
            <li className={`is-${severity}`} key={flag.code}>
              <strong>{text.severityLabels[severity]}</strong>
              <span>{formatMessage(flag)}</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function renderInlineText(text: string) {
  const tokens = text.split(/(\*\*[^*]+\*\*)/g).filter(Boolean);
  return tokens.map((token, index) => {
    if (token.startsWith("**") && token.endsWith("**")) {
      return <strong key={`strong-${index}`}>{token.slice(2, -2)}</strong>;
    }

    return <span key={`text-${index}`}>{token}</span>;
  });
}

function isMarkdownTableRow(line: string) {
  return line.startsWith("|") && line.endsWith("|") && line.split("|").length > 3;
}

function isMarkdownSeparatorRow(line: string) {
  return /^\|[\s:\-|\u2500]+\|$/.test(line);
}

function parseTableCells(line: string) {
  return line
    .split("|")
    .slice(1, -1)
    .map((cell) => cell.trim());
}

function isNumberedHeading(line: string) {
  return /^((\d+[.)])|([①-⑩])|(\d+️⃣))\s*/.test(line);
}

function isSupportHeading(label: string) {
  const normalized = label.toLowerCase();
  return (
    label === "풀이 포인트" ||
    label === "전문가 노트" ||
    normalized === "interpretation points" ||
    normalized === "expert note" ||
    normalized === "expert notes"
  );
}

function splitReadableText(text: string, maxSentences = 2, maxChars = 170) {
  const sentences =
    text
      .match(/[^.!?。]+[.!?。]+(?:["”’)]*)?|[^.!?。]+$/g)
      ?.map((sentence) => sentence.trim())
      .filter(Boolean) ?? [];

  if (sentences.length <= 1) {
    return [text];
  }

  const chunks: string[] = [];
  let current = "";
  let sentenceCount = 0;

  for (const sentence of sentences) {
    const next = current ? `${current} ${sentence}` : sentence;
    if (current && (sentenceCount >= maxSentences || next.length > maxChars)) {
      chunks.push(current);
      current = sentence;
      sentenceCount = 1;
      continue;
    }

    current = next;
    sentenceCount += 1;
  }

  if (current) {
    chunks.push(current);
  }

  return chunks;
}

function truncateText(text: string, maxLength: number) {
  const compact = text.replace(/\s+/g, " ").trim();

  if (compact.length <= maxLength) {
    return compact;
  }

  return `${compact.slice(0, Math.max(0, maxLength - 3)).trimEnd()}...`;
}

function stripInlineMarkdown(text: string) {
  return text
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/__([^_]+)__/g, "$1")
    .replace(/[_*~]/g, "")
    .replace(/<[^>]+>/g, "")
    .trim();
}

const previewSentencePattern = /[^.!?。！？]+[.!?。！？]+(?:["”’)]*)?|[^.!?。！？]+$/g;

function splitPreviewSentences(text: string) {
  return (
    text
      .match(previewSentencePattern)
      ?.map((sentence) => sentence.trim())
      .filter(Boolean) ?? []
  );
}

function truncatePreviewAtBoundary(text: string, maxLength: number) {
  const compact = text
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.replace(/\s+/g, " ").trim())
    .filter(Boolean)
    .join("\n\n");

  if (compact.length <= maxLength) {
    return compact;
  }

  const flattened = compact.replace(/\n{2,}/g, " ");
  const sentences = splitPreviewSentences(flattened);
  let preview = "";

  for (const sentence of sentences) {
    const next = preview ? `${preview} ${sentence}` : sentence;
    if (next.length > maxLength - 3) {
      break;
    }
    preview = next;
  }

  if (preview.length >= Math.min(220, maxLength * 0.55)) {
    return `${preview.trimEnd()}...`;
  }

  return `${flattened.slice(0, Math.max(0, maxLength - 3)).trimEnd()}...`;
}

function stripPreviewContinuationMark(text: string) {
  return text.replace(/\s*\.{3}$/g, "").trim();
}

function extractPreviewFromMarkdown(
  body: string | null | undefined,
  maxLength = 420,
  fallbackText = "상세 해석을 준비 중입니다.",
) {
  const raw = typeof body === "string" ? body : "";

  if (!raw.trim()) {
    return fallbackText;
  }

  const paragraphs = raw
    .split(/\n\s*\n/g)
    .map((block) =>
      block
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter((line) => {
          if (!line) {
            return false;
          }
          if (/^#{1,6}\s+/.test(line)) {
            return false;
          }
          if (isMarkdownSeparatorRow(line) || isMarkdownTableRow(line)) {
            return false;
          }
          return true;
        })
        .map((line) =>
          stripInlineMarkdown(
            line
              .replace(/^[-*+]\s+/, "")
              .replace(/^>\s+/, "")
              .replace(/^((\d+[.)])|([①-⑩])|(\d+️⃣))\s*/, ""),
          ),
        )
        .filter(Boolean)
        .join(" "),
    )
    .map((paragraph) => paragraph.replace(/\s+/g, " ").trim())
    .filter(Boolean);

  if (!paragraphs.length) {
    return fallbackText;
  }

  const selectedParagraphs: string[] = [];
  let sentenceCount = 0;

  for (const paragraph of paragraphs.slice(0, 3)) {
    const sentences = splitPreviewSentences(paragraph);
    const remainingSentences = Math.max(0, 8 - sentenceCount);
    const nextParagraph = sentences.length
      ? sentences.slice(0, remainingSentences || 1).join(" ")
      : paragraph;

    if (!nextParagraph) {
      continue;
    }

    const candidate = [...selectedParagraphs, nextParagraph].join("\n\n");

    if (selectedParagraphs.length && candidate.length > maxLength && sentenceCount >= 5) {
      break;
    }

    selectedParagraphs.push(nextParagraph);
    sentenceCount += sentences.length ? Math.min(sentences.length, remainingSentences || 1) : 1;

    if (sentenceCount >= 8) {
      break;
    }

    if (sentenceCount >= 5 && candidate.length >= Math.min(320, maxLength * 0.75)) {
      break;
    }
  }

  return truncatePreviewAtBoundary(selectedParagraphs.join("\n\n"), maxLength);
}

function extractFirstPreviewSentence(
  body: string | null | undefined,
  maxLength: number,
  fallbackText: string,
) {
  const preview = extractPreviewFromMarkdown(body, maxLength, fallbackText);
  const firstSentence = splitPreviewSentences(preview.replace(/\n{2,}/g, " "))?.[0]?.trim();

  return truncateText(firstSentence || preview, maxLength);
}

function renderRichBody(text: string) {
  const nodes: ReactNode[] = [];
  const lines = text.split(/\r?\n/);
  let bullets: string[] = [];
  let tableRows: string[][] = [];
  let hasTableHeader = false;
  let keyIndex = 0;
  let supportBlockNodes: ReactNode[] | null = null;

  const pushNode = (node: ReactNode) => {
    if (supportBlockNodes) {
      supportBlockNodes.push(node);
      return;
    }

    nodes.push(node);
  };

  const flushSupportBlock = () => {
    if (!supportBlockNodes?.length) {
      supportBlockNodes = null;
      return;
    }

    nodes.push(
      <aside className="reading-support-block" key={`support-${keyIndex++}`}>
        {supportBlockNodes}
      </aside>,
    );
    supportBlockNodes = null;
  };

  const flushBullets = () => {
    if (!bullets.length) {
      return;
    }
    pushNode(
      <ul className="reading-bullets" key={`bullets-${keyIndex++}`}>
        {bullets.map((bullet, index) => {
          const parts = splitReadableText(bullet, 1, 140);
          return (
            <li key={`bullet-${keyIndex}-${index}`}>
              {parts.length === 1
                ? renderInlineText(parts[0])
                : parts.map((part, partIndex) => (
                    <span
                      className="reading-bullet-paragraph"
                      key={`bullet-part-${keyIndex}-${index}-${partIndex}`}
                    >
                      {renderInlineText(part)}
                    </span>
                  ))}
            </li>
          );
        })}
      </ul>,
    );
    bullets = [];
  };

  const flushTable = () => {
    if (!tableRows.length) {
      hasTableHeader = false;
      return;
    }

    const headerCells = hasTableHeader ? tableRows[0] : null;
    const bodyRows = hasTableHeader ? tableRows.slice(1) : tableRows;

    pushNode(
      <div className="reading-table-wrap" key={`table-${keyIndex++}`}>
        <table className="reading-table">
          {headerCells ? (
            <thead>
              <tr>
                {headerCells.map((cell, index) => (
                  <th key={`th-${keyIndex}-${index}`}>{renderInlineText(cell)}</th>
                ))}
              </tr>
            </thead>
          ) : null}
          <tbody>
            {bodyRows.map((row, rowIndex) => (
              <tr key={`tr-${keyIndex}-${rowIndex}`}>
                {row.map((cell, cellIndex) => (
                  <td key={`td-${keyIndex}-${rowIndex}-${cellIndex}`}>
                    {renderInlineText(cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>,
    );

    tableRows = [];
    hasTableHeader = false;
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();

    if (!line) {
      flushBullets();
      flushTable();
      continue;
    }

    if (isMarkdownTableRow(line)) {
      flushBullets();

      if (isMarkdownSeparatorRow(line)) {
        hasTableHeader = true;
      } else {
        tableRows.push(parseTableCells(line));
      }
      continue;
    }

    flushTable();

    if (line.startsWith("- ")) {
      bullets.push(line.slice(2).trim());
      continue;
    }

    flushBullets();

    if (line.startsWith("### ")) {
      const headingLabel = line.slice(4).trim();
      const isSupport = isSupportHeading(headingLabel);
      flushSupportBlock();

      if (isSupport) {
        supportBlockNodes = [];
      }

      pushNode(
        <h4
          className={`reading-subheading${isSupport ? " reading-support-heading" : ""}`}
          key={`h4-${keyIndex++}`}
        >
          {renderInlineText(headingLabel)}
        </h4>,
      );
      continue;
    }

    if (line.startsWith("## ")) {
      flushSupportBlock();
      pushNode(
        <h3 className="reading-inline-heading" key={`h3-${keyIndex++}`}>
          {renderInlineText(line.slice(3).trim())}
        </h3>,
      );
      continue;
    }

    if (isNumberedHeading(line)) {
      flushSupportBlock();
      pushNode(
        <h4 className="reading-numbered-heading" key={`numbered-${keyIndex++}`}>
          {renderInlineText(line)}
        </h4>,
      );
      continue;
    }

    for (const paragraph of splitReadableText(line)) {
      pushNode(
        <p className="reading-paragraph" key={`p-${keyIndex++}`}>
          {renderInlineText(paragraph)}
        </p>,
      );
    }
  }

  flushBullets();
  flushTable();
  flushSupportBlock();
  return nodes;
}

function NarrativeSection({
  section,
  anchorId,
  badge,
  index,
  prelude,
  afterContent,
}: {
  section: InterpretationNarrativeSection;
  anchorId: string;
  badge: string;
  index: number;
  prelude?: ReactNode;
  afterContent?: ReactNode;
}) {
  return (
    <section className="reading-section-panel" id={anchorId}>
      <div className="reading-section-shell">
        <div className="reading-section-meta">
          <span className="reading-section-index">{String(index).padStart(2, "0")}</span>
          <div className="reading-section-head">
            <p className="reading-section-label">{badge}</p>
            <h3>{section.title}</h3>
          </div>
        </div>
        {prelude ? <div className="reading-section-prelude">{prelude}</div> : null}
        <div className="reading-article">{renderRichBody(section.body)}</div>
        {afterContent ? <div className="reading-section-extra">{afterContent}</div> : null}
      </div>
    </section>
  );
}

type InsightCardData = {
  title: string;
  subtitle: string;
  chips: string[];
  preview?: string;
  previewParagraphs?: string[];
  userTakeaway?: string;
  nextQuestion?: string;
  basis: string;
  cta: string;
  href: string;
};

const publicPreviewForbiddenPatterns = [
  /\bbalance_score\b/i,
  /\binternal_grade\b/i,
  /\bevidence_id\b/i,
  /\bscore\b/i,
  /점수:/,
  /등급:/,
  /100점/,
  /100%/,
];

function containsPrivatePreviewToken(text: string) {
  return publicPreviewForbiddenPatterns.some((pattern) => pattern.test(text));
}

function safePreviewText(text: string | null | undefined, fallbackText: string) {
  const value = typeof text === "string" ? text.trim() : "";

  if (!value || containsPrivatePreviewToken(value)) {
    return fallbackText;
  }

  return value;
}

function safePreviewParagraphs(
  paragraphs: Array<string | null | undefined> | null | undefined,
  fallbackText: string,
) {
  const safeParagraphs = (paragraphs ?? [])
    .map((paragraph) => (typeof paragraph === "string" ? paragraph.trim() : ""))
    .filter((paragraph) => paragraph && !containsPrivatePreviewToken(paragraph));

  return safeParagraphs.length ? safeParagraphs : [fallbackText];
}

function groupHeroOverviewParagraphs(paragraphs: string[]) {
  const cleanParagraphs = paragraphs.map((paragraph) => paragraph.trim()).filter(Boolean);

  if (cleanParagraphs.length <= 3) {
    return cleanParagraphs;
  }

  const targetGroupCount = cleanParagraphs.length >= 7 ? 3 : 2;
  const groupSize = Math.ceil(cleanParagraphs.length / targetGroupCount);
  const grouped: string[] = [];

  for (let index = 0; index < cleanParagraphs.length; index += groupSize) {
    grouped.push(cleanParagraphs.slice(index, index + groupSize).join(" "));
  }

  return grouped;
}

function normalizeNarrativeSection(
  section: InterpretationNarrativeSection | null | undefined,
  fallbackTitle: string,
): InterpretationNarrativeSection {
  return {
    title: section?.title?.trim() || fallbackTitle,
    body: section?.body || "",
    evidence_ids: section?.evidence_ids ?? [],
  };
}

function getHeroWarningBadges(result: SajuPreviewResponse, locale: Locale) {
  const text = sectionViewCopy[locale];
  const flags = (result.result.uncertainty_summary ?? []).filter(
    (flag) => flag.severity === "warning" || flag.severity === "critical",
  );
  const badges: string[] = [];
  const hasBirthTimeWarning =
    !result.result.hour_pillar_enabled ||
    flags.some((flag) => {
      const terms = `${flag.code} ${flag.affected_fields.join(" ")}`.toLowerCase();
      return (
        terms.includes("birth") ||
        terms.includes("time") ||
        terms.includes("hour") ||
        terms.includes("placeholder")
      );
    });
  const hasBoundaryWarning = flags.some((flag) => {
    const terms = `${flag.code} ${flag.affected_fields.join(" ")}`.toLowerCase();
    return (
      terms.includes("boundary") ||
      terms.includes("midnight") ||
      terms.includes("solar_term") ||
      terms.includes("year_month")
    );
  });

  if (hasBirthTimeWarning) {
    badges.push(text.birthTimeWarningBadge);
  }

  if (hasBoundaryWarning) {
    badges.push(text.boundaryWarningBadge);
  }

  if (flags.length && !badges.length) {
    badges.push(text.generalWarningBadge);
  }

  return badges;
}

function scrollToAnchor(href: string) {
  if (!href.startsWith("#")) {
    return;
  }

  window.setTimeout(() => {
    document.querySelector(href)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, 80);
}

function InsightCard({
  card,
  onCtaClick,
}: {
  card: InsightCardData;
  onCtaClick?: (href: string) => void;
}) {
  const previewParagraphs = card.previewParagraphs?.length
    ? card.previewParagraphs
    : (card.preview ?? "")
        .split(/\n{2,}/)
        .map((paragraph) => paragraph.trim())
        .filter(Boolean);

  return (
    <article className="insightCard">
      <div>
        <h3 className="insightCardTitle">{card.title}</h3>
        <p className="insightCardSubtitle">{card.subtitle}</p>
      </div>
      <div className="insightCardChips" aria-label={card.title}>
        {card.chips.map((chip) => (
          <span key={chip}>{chip}</span>
        ))}
      </div>
      <div className="insightCardPreview">
        {previewParagraphs.map((paragraph, index) => (
          <p key={`${card.title}-preview-${index}`}>{paragraph}</p>
        ))}
      </div>
      {card.userTakeaway ? <p className="insightCardTakeaway">{card.userTakeaway}</p> : null}
      {card.nextQuestion ? <p className="insightCardQuestion">{card.nextQuestion}</p> : null}
      <p className="insightCardBasis">{card.basis}</p>
      <a
        className="insightCardCta"
        href={card.href}
        onClick={(event) => {
          if (!onCtaClick) {
            return;
          }
          event.preventDefault();
          onCtaClick(card.href);
        }}
      >
        {card.cta}
      </a>
    </article>
  );
}

type SectionInsightState = {
  status: InsightLoadState;
  report?: SajuDetailRenderedReport;
  error?: string | null;
};

function DetailRevealPanel({
  detailType,
  state,
  locale,
}: {
  detailType: SajuDetailType;
  state: SectionInsightState | undefined;
  locale: Locale;
}) {
  const copy = sectionInsightCopy[locale];
  const status = state?.status ?? "idle";

  if (detailType === "compatibility_compare" && status !== "loading" && !state?.report) {
    return (
      <div className="detailRevealPanel">
        <h4>{copy.status.compatibilityTitle}</h4>
        <p>{copy.status.compatibilityBody}</p>
      </div>
    );
  }

  if (status === "loading") {
    return (
      <div className="detailRevealPanel is-loading">
        <p>{copy.status.loading}</p>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="detailRevealPanel is-error">
        <p>{state?.error || copy.status.error}</p>
      </div>
    );
  }

  const report = state?.report;
  if (!report) {
    return null;
  }

  return (
    <div className="detailRevealPanel">
      <div className="detailRevealHead">
        <h4>{report.title}</h4>
        <p>{report.summary}</p>
      </div>
      <p className="detailRevealConclusion">{report.body.conclusion}</p>
      {report.body.periods.length ? (
        <div className="detailRevealPeriods">
          {report.body.periods.map((period) => (
            <article key={`${period.label}-${period.period}`}>
              <span>{period.label}</span>
              <strong>{period.period}</strong>
              <p>{period.description}</p>
            </article>
          ))}
        </div>
      ) : null}
      {report.body.cautions.length ? (
        <div className="detailRevealList">
          <strong>{locale === "ko" ? "주의해서 볼 점" : "Watch points"}</strong>
          <ul>
            {report.body.cautions.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {report.body.advice.length ? (
        <div className="detailRevealList">
          <strong>{locale === "ko" ? "실행 포인트" : "Action points"}</strong>
          <ul>
            {report.body.advice.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {report.body.basis_chips.length ? (
        <div className="detailRevealChips">
          {report.body.basis_chips.map((chip) => (
            <span key={chip}>{chip}</span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function SectionInsightChips({
  heading,
  items,
  states,
  activeDetailType,
  locale,
  onOpen,
}: {
  heading: string;
  items: SectionInsightCopy[];
  states: Partial<Record<SajuDetailType, SectionInsightState>>;
  activeDetailType: SajuDetailType | null;
  locale: Locale;
  onOpen: (detailType: SajuDetailType) => void;
}) {
  const activeItem = activeDetailType
    ? items.find((item) => item.detailType === activeDetailType)
    : undefined;

  return (
    <div className="sectionInsightBlock">
      <h4>{heading}</h4>
      <div className="sectionInsightGrid">
        {items.map((item) => {
          const state = states[item.detailType];
          const isActive = activeDetailType === item.detailType;
          const isLoading = state?.status === "loading";
          return (
            <button
              className={`sectionInsightCard${isActive ? " is-active" : ""}`}
              disabled={isLoading}
              key={item.detailType}
              type="button"
              onClick={() => onOpen(item.detailType)}
            >
              <span>{item.title}</span>
              <p>{isLoading ? sectionInsightCopy[locale].status.loading : item.description}</p>
            </button>
          );
        })}
      </div>
      {activeItem ? (
        <DetailRevealPanel
          detailType={activeItem.detailType}
          locale={locale}
          state={states[activeItem.detailType]}
        />
      ) : null}
    </div>
  );
}

function getFreePreviewCardDisplay(
  key: FreePreviewCard["key"],
  locale: Locale,
) {
  const viewTexts = sectionViewCopy[locale];

  switch (key) {
    case "core":
      return {
        title: viewTexts.cards.core.title,
        subtitle: viewTexts.cards.core.subtitle,
        cta: viewTexts.cards.core.cta,
        href: "#core-analysis",
        basis: insightCardMeta[locale].core.basis,
        chips: insightCardMeta[locale].core.chips,
      };
    case "work_money":
      return {
        title: viewTexts.cards.workMoney.title,
        subtitle: viewTexts.cards.workMoney.subtitle,
        cta: viewTexts.cards.workMoney.cta,
        href: "#work-money-reading",
        basis: insightCardMeta[locale].workMoney.basis,
        chips: insightCardMeta[locale].workMoney.chips,
      };
    case "love":
      return {
        title: viewTexts.cards.love.title,
        subtitle: viewTexts.cards.love.subtitle,
        cta: viewTexts.cards.love.cta,
        href: "#love-reading",
        basis: insightCardMeta[locale].love.basis,
        chips: insightCardMeta[locale].love.chips,
      };
    case "luck_flow":
      return {
        title: viewTexts.cards.luck.title,
        subtitle: viewTexts.cards.luck.subtitle,
        cta: viewTexts.cards.luck.cta,
        href: "#luck-flow-reading",
        basis: insightCardMeta[locale].luck.basis,
        chips: insightCardMeta[locale].luck.chips,
      };
  }
}

function buildFreePreviewInsightCards(
  cards: FreePreviewCard[],
  locale: Locale,
  fallbackText: string,
): InsightCardData[] {
  const cardByKey = new Map(cards.map((card) => [card.key, card]));
  const order: Array<FreePreviewCard["key"]> = ["core", "work_money", "love", "luck_flow"];
  const insightCards: InsightCardData[] = [];

  for (const key of order) {
    const card = cardByKey.get(key);
    if (!card) {
      continue;
    }

    const display = getFreePreviewCardDisplay(key, locale);
    const chips = card.chips
      .map((chip) => safePreviewText(chip, ""))
      .filter(Boolean);

    insightCards.push({
      title: display.title,
      subtitle: safePreviewText(card.subtitle, display.subtitle),
      chips: chips.length ? chips : display.chips,
      previewParagraphs: safePreviewParagraphs(card.preview_paragraphs, fallbackText),
      userTakeaway: safePreviewText(card.user_takeaway, ""),
      nextQuestion: safePreviewText(card.next_question, ""),
      basis: safePreviewText(card.basis_line, display.basis),
      cta: display.cta,
      href: display.href,
    });
  }

  return insightCards;
}

function CoreDiagnosisBlock({
  diagnoses,
  locale,
  fallbackText,
}: {
  diagnoses: FreePreviewDiagnosis[];
  locale: Locale;
  fallbackText: string;
}) {
  const diagnosisByKey = new Map(diagnoses.map((diagnosis) => [diagnosis.key, diagnosis]));
  const order: FreePreviewDiagnosisKey[] = ["strongest_point", "repeating_pattern", "current_task"];
  const items = order
    .map((key) => {
      const diagnosis = diagnosisByKey.get(key);
      if (!diagnosis) {
        return null;
      }

      return {
        key,
        title: diagnosisTitleByKey[locale][key] || diagnosis.title,
        body: safePreviewText(diagnosis.body, fallbackText),
      };
    })
    .filter((item): item is { key: FreePreviewDiagnosisKey; title: string; body: string } =>
      Boolean(item),
    );

  if (!items.length) {
    return null;
  }

  return (
    <section className="coreDiagnosisBlock" aria-label={sectionViewCopy[locale].coreDiagnosisLabel}>
      <span className="result-panel-label">{sectionViewCopy[locale].coreDiagnosisLabel}</span>
      <div className="coreDiagnosisGrid">
        {items.map((item) => (
          <article className="coreDiagnosisCard" key={item.key}>
            <h3>{item.title}</h3>
            <p>{item.body}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

export function SajuResultView({ locale, result, detailPayload, onReset }: SajuResultViewProps) {
  const texts = getCopy(locale);
  const viewTexts = sectionViewCopy[locale];
  const detailTexts = detailLazyCopy[locale];
  const statusTexts = disabledStateCopy[locale];
  const isBirthTimeUnknown = !result.result.hour_pillar_enabled;
  const visiblePillars = result.result.signals.visible_pillar_values
    .map((value) => formatManseText(value, locale))
    .join(" / ");
  const freePreview = result.result.free_preview;
  const embeddedInterpretation = result.result.interpretation ?? null;
  const [detailReport, setDetailReport] = useState<InterpretationReport | null>(() =>
    freePreview ? null : embeddedInterpretation,
  );
  const [detailStatus, setDetailStatus] = useState<DetailLoadState>(() =>
    freePreview ? "idle" : embeddedInterpretation ? "ready" : "idle",
  );
  const [detailError, setDetailError] = useState<string | null>(null);
  const [pendingScrollTarget, setPendingScrollTarget] = useState<string | null>(null);
  const [detailBundleHash, setDetailBundleHash] = useState<string | null>(null);
  const [activeSectionInsights, setActiveSectionInsights] = useState<Record<string, SajuDetailType>>(
    {},
  );
  const [sectionInsightStates, setSectionInsightStates] = useState<
    Partial<Record<SajuDetailType, SectionInsightState>>
  >({});
  const detailLoaderRef = useRef<HTMLElement | null>(null);
  const interpretation = detailReport ?? (!freePreview ? embeddedInterpretation : null);

  useEffect(() => {
    setDetailReport(freePreview ? null : embeddedInterpretation);
    setDetailStatus(freePreview ? "idle" : embeddedInterpretation ? "ready" : "idle");
    setDetailError(null);
    setPendingScrollTarget(null);
    setDetailBundleHash(null);
    setActiveSectionInsights({});
    setSectionInsightStates({});
  }, [embeddedInterpretation, freePreview, result.trace_id]);

  const loadFreeDetail = useCallback(
    async (targetHref?: string) => {
      if (!freePreview) {
        if (targetHref) {
          scrollToAnchor(targetHref);
        }
        return;
      }

      if (detailReport) {
        if (targetHref) {
          scrollToAnchor(targetHref);
        }
        return;
      }

      if (detailStatus === "loading") {
        if (targetHref) {
          setPendingScrollTarget(targetHref);
        }
        return;
      }

      if (targetHref) {
        setPendingScrollTarget(targetHref);
      }

      if (!detailPayload) {
        if (embeddedInterpretation) {
          setDetailReport(embeddedInterpretation);
          setDetailStatus("ready");
          setDetailError(detailTexts.fallbackNotice);
        } else {
          setDetailStatus("error");
          setDetailError(detailTexts.errorTitle);
        }
        return;
      }

      setDetailStatus("loading");
      setDetailError(null);

      try {
        const response = await createSajuFreeDetail(detailPayload, detailPayload.debug);
        setDetailReport(response.detail_report ?? response.interpretation);
        setDetailStatus("ready");
      } catch (_error) {
        if (embeddedInterpretation) {
          setDetailReport(embeddedInterpretation);
          setDetailStatus("ready");
          setDetailError(detailTexts.fallbackNotice);
          return;
        }

        setDetailStatus("error");
        setDetailError(detailTexts.errorTitle);
      }
    },
    [
      detailPayload,
      detailReport,
      detailStatus,
      detailTexts.errorTitle,
      detailTexts.fallbackNotice,
      embeddedInterpretation,
      freePreview,
    ],
  );

  useEffect(() => {
    if (!pendingScrollTarget || !detailReport) {
      return;
    }

    scrollToAnchor(pendingScrollTarget);
    setPendingScrollTarget(null);
  }, [detailReport, pendingScrollTarget]);

  useEffect(() => {
    if (!freePreview || detailReport || detailStatus !== "idle" || !detailLoaderRef.current) {
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          void loadFreeDetail();
        }
      },
      { rootMargin: "260px 0px" },
    );
    observer.observe(detailLoaderRef.current);

    return () => observer.disconnect();
  }, [detailReport, detailStatus, freePreview, loadFreeDetail]);

  const handleInsightCtaClick = useCallback(
    (href: string) => {
      if (freePreview && !detailReport) {
        void loadFreeDetail(href);
        return;
      }

      scrollToAnchor(href);
    },
    [detailReport, freePreview, loadFreeDetail],
  );

  const handleDetailNavClick = useCallback(
    (event: MouseEvent<HTMLAnchorElement>, href: string) => {
      if (freePreview && !detailReport) {
        event.preventDefault();
        void loadFreeDetail(href);
      }
    },
    [detailReport, freePreview, loadFreeDetail],
  );

  const openSectionInsight = useCallback(
    async (sectionKey: string, detailType: SajuDetailType) => {
      setActiveSectionInsights((current) => ({
        ...current,
        [sectionKey]: detailType,
      }));

      const existingState = sectionInsightStates[detailType];
      if (existingState?.status === "ready" || existingState?.status === "loading") {
        return;
      }

      if (detailType === "compatibility_compare") {
        setSectionInsightStates((current) => ({
          ...current,
          [detailType]: { status: "ready" },
        }));
        return;
      }

      if (!detailPayload) {
        setSectionInsightStates((current) => ({
          ...current,
          [detailType]: {
            status: "error",
            error: sectionInsightCopy[locale].status.error,
          },
        }));
        return;
      }

      setSectionInsightStates((current) => ({
        ...current,
        [detailType]: { status: "loading" },
      }));

      try {
        let inputHash = detailBundleHash;
        if (!inputHash) {
          const prepared = await prepareSajuDetailBundle(result.trace_id, detailPayload, detailType);
          inputHash = prepared.input_hash;
          setDetailBundleHash(inputHash);
        }

        const rendered = await renderSajuDetailInsight(
          result.trace_id,
          detailPayload,
          detailType,
          inputHash,
        );
        setDetailBundleHash(rendered.input_hash);
        setSectionInsightStates((current) => ({
          ...current,
          [detailType]: {
            status: "ready",
            report: rendered.report,
          },
        }));
      } catch (_error) {
        setSectionInsightStates((current) => ({
          ...current,
          [detailType]: {
            status: "error",
            error: sectionInsightCopy[locale].status.error,
          },
        }));
      }
    },
    [detailBundleHash, detailPayload, locale, result.trace_id, sectionInsightStates],
  );

  if (!interpretation && !freePreview) {
    return (
      <section className="result-screen">
        <div className="result-header">
          <div className="result-header-copy">
            <h2>{texts.resultTitle}</h2>
            <p>{visiblePillars}</p>
          </div>
          <button className="secondary-button" type="button" onClick={onReset}>
            {texts.backToForm}
          </button>
        </div>

        <div className="result-section">
          <h3>{texts.overview}</h3>
          <p>{result.result.overview}</p>
        </div>
      </section>
    );
  }

  const coreSection = normalizeNarrativeSection(
    interpretation?.core_analysis,
    viewTexts.cards.core.title,
  );
  const careerSection = normalizeNarrativeSection(
    interpretation?.career,
    viewTexts.sectionLabels.career,
  );
  const wealthSection = normalizeNarrativeSection(
    interpretation?.wealth,
    viewTexts.sectionLabels.wealth,
  );
  const loveSection = normalizeNarrativeSection(
    interpretation?.love,
    viewTexts.cards.love.title,
  );
  const luckFlowSection = normalizeNarrativeSection(
    interpretation?.luck_flow,
    viewTexts.cards.luck.title,
  );
  const legacySummaryHeadline =
    interpretation?.summary?.headline?.trim() || result.result.overview || texts.resultTitle;
  const legacySummaryOverview =
    interpretation?.summary?.overview?.trim() || result.result.overview || viewTexts.previewFallback;
  const summaryHeadline = freePreview
    ? safePreviewText(freePreview.headline, legacySummaryHeadline)
    : legacySummaryHeadline;
  const summaryOverview = freePreview
    ? groupHeroOverviewParagraphs(
        safePreviewParagraphs(freePreview.hero_overview, legacySummaryOverview),
      ).join("\n\n")
    : groupHeroOverviewParagraphs(splitReadableText(legacySummaryOverview, 3, 260)).join("\n\n");
  const heroWarningBadges = getHeroWarningBadges(result, locale);
  const cardMeta = insightCardMeta[locale];
  const workPreview = truncatePreviewAtBoundary(
    `${stripPreviewContinuationMark(
      extractPreviewFromMarkdown(careerSection.body, 260, viewTexts.previewFallback),
    )}\n\n${stripPreviewContinuationMark(
      extractPreviewFromMarkdown(wealthSection.body, 260, viewTexts.previewFallback),
    )}`,
    520,
  );
  const legacyInsightCards: InsightCardData[] = [
    {
      title: viewTexts.cards.core.title,
      subtitle: viewTexts.cards.core.subtitle,
      chips: cardMeta.core.chips,
      preview: extractPreviewFromMarkdown(coreSection.body, 460, viewTexts.previewFallback),
      basis: cardMeta.core.basis,
      cta: viewTexts.cards.core.cta,
      href: "#core-analysis",
    },
    {
      title: viewTexts.cards.workMoney.title,
      subtitle: viewTexts.cards.workMoney.subtitle,
      chips: cardMeta.workMoney.chips,
      preview: workPreview,
      basis: cardMeta.workMoney.basis,
      cta: viewTexts.cards.workMoney.cta,
      href: "#work-money-reading",
    },
    {
      title: viewTexts.cards.love.title,
      subtitle: viewTexts.cards.love.subtitle,
      chips: cardMeta.love.chips,
      preview: extractPreviewFromMarkdown(loveSection.body, 460, viewTexts.previewFallback),
      basis: cardMeta.love.basis,
      cta: viewTexts.cards.love.cta,
      href: "#love-reading",
    },
    {
      title: viewTexts.cards.luck.title,
      subtitle: viewTexts.cards.luck.subtitle,
      chips: cardMeta.luck.chips,
      preview: extractPreviewFromMarkdown(luckFlowSection.body, 460, viewTexts.previewFallback),
      basis: cardMeta.luck.basis,
      cta: viewTexts.cards.luck.cta,
      href: "#luck-flow-reading",
    },
  ];
  const freePreviewCards = freePreview
    ? buildFreePreviewInsightCards(freePreview.cards, locale, viewTexts.previewFallback)
    : [];
  const insightCards = freePreviewCards.length ? freePreviewCards : legacyInsightCards;
  const detailNavSections: Array<{
    key: SectionKey;
    anchorId: string;
    badge: string;
    section: InterpretationNarrativeSection;
  }> = [
    {
      key: "core_analysis",
      anchorId: "core-analysis",
      badge: viewTexts.cards.core.title,
      section: coreSection,
    },
    {
      key: "career",
      anchorId: "work-money-reading",
      badge: viewTexts.cards.workMoney.title,
      section: careerSection,
    },
    {
      key: "love",
      anchorId: "love-reading",
      badge: viewTexts.cards.love.title,
      section: loveSection,
    },
    {
      key: "luck_flow",
      anchorId: "luck-flow-reading",
      badge: viewTexts.cards.luck.title,
      section: luckFlowSection,
    },
  ];
  const hasDetailReport = Boolean(interpretation);
  const insightCopy = sectionInsightCopy[locale];
  const renderSectionInsights = (
    sectionKey: string,
    heading: string,
    detailTypes: SajuDetailType[],
  ) => (
    <SectionInsightChips
      activeDetailType={activeSectionInsights[sectionKey] ?? null}
      heading={heading}
      items={detailTypes.map((detailType) => insightCopy.items[detailType])}
      locale={locale}
      states={sectionInsightStates}
      onOpen={(detailType) => void openSectionInsight(sectionKey, detailType)}
    />
  );

  return (
    <section className="result-screen">
      <div className="result-header">
        <div className="result-header-copy">
          <h2>{texts.resultTitle}</h2>
          <p>{visiblePillars}</p>
        </div>
        <button className="secondary-button" type="button" onClick={onReset}>
          {texts.backToForm}
        </button>
      </div>

      <div className="result-layout">
        <div className="result-main-column">
          {isBirthTimeUnknown ? (
            <section className="result-disabled-banner">
              <div className="result-disabled-banner-head">
                <span className="result-panel-label">{statusTexts.disabledBadge}</span>
                <h3>{statusTexts.unknownTimeNoticeTitle}</h3>
              </div>
              <p>{statusTexts.unknownTimeNoticeBody}</p>
            </section>
          ) : null}

          <section className="resultHero">
            <div className="resultHeroTop">
              <span className="result-panel-label">{viewTexts.heroLabel}</span>
            </div>
            <h2 className="resultHeroHeadline">{summaryHeadline}</h2>
            <div className="reading-article resultHeroOverview">
              {renderRichBody(summaryOverview)}
            </div>
            <div className="resultHeroBadges" aria-label={viewTexts.heroLabel}>
              <span>{viewTexts.solarTermBadge}</span>
              <span>{viewTexts.timeCorrectionBadge}</span>
              {heroWarningBadges.map((badge) => (
                <span className="is-warning" key={badge}>
                  {badge}
                </span>
              ))}
            </div>
          </section>

          {freePreview ? (
            <CoreDiagnosisBlock
              diagnoses={freePreview.core_diagnoses}
              locale={locale}
              fallbackText={viewTexts.previewFallback}
            />
          ) : null}

          <section className="insightBlock" aria-label={viewTexts.insightLabel}>
            <span className="result-panel-label">{viewTexts.insightLabel}</span>
            <div className="insightGrid">
              {insightCards.map((card) => (
                <InsightCard
                  card={card}
                  key={card.title}
                  onCtaClick={handleInsightCtaClick}
                />
              ))}
            </div>
          </section>

          <UncertaintySummaryNotice locale={locale} result={result} />
          <CompactPillarTable locale={locale} result={result} />

          {hasDetailReport ? (
            <>
              {detailError ? <p className="detailLazyNotice">{detailError}</p> : null}
              <NarrativeSection
                section={coreSection}
                anchorId="core-analysis"
                badge={viewTexts.cards.core.title}
                index={1}
                prelude={
                  <>
                    <ElementBalanceCard locale={locale} result={result} />
                    <DetailedPillarTable locale={locale} result={result} />
                  </>
                }
                afterContent={renderSectionInsights("core", insightCopy.headings.core, [
                  "relationship_support",
                  "health_condition",
                ])}
              />

              <section className="detailGroup" id="work-money-reading">
                <div className="detailGroupHead">
                  <span className="result-panel-label">{viewTexts.cards.workMoney.title}</span>
                  <p>{viewTexts.cards.workMoney.subtitle}</p>
                </div>
                <NarrativeSection
                  section={careerSection}
                  anchorId="career-reading"
                  badge={viewTexts.sectionLabels.career}
                  index={2}
                  afterContent={renderSectionInsights("career", insightCopy.headings.career, [
                    "career_timing",
                  ])}
                />
                <NarrativeSection
                  section={wealthSection}
                  anchorId="wealth-reading"
                  badge={viewTexts.sectionLabels.wealth}
                  index={3}
                  afterContent={renderSectionInsights("wealth", insightCopy.headings.wealth, [
                    "wealth_timing",
                  ])}
                />
              </section>

              <NarrativeSection
                section={loveSection}
                anchorId="love-reading"
                badge={viewTexts.cards.love.title}
                index={4}
                afterContent={renderSectionInsights("love", insightCopy.headings.love, [
                  "love_timing",
                  "ideal_partner",
                  "compatibility_compare",
                ])}
              />

              <NarrativeSection
                section={luckFlowSection}
                anchorId="luck-flow-reading"
                badge={viewTexts.cards.luck.title}
                index={5}
                prelude={<LuckTimelineTable locale={locale} result={result} />}
                afterContent={renderSectionInsights("luck", insightCopy.headings.luck, [
                  "yearly_caution",
                  "monthly_flow",
                ])}
              />
            </>
          ) : (
            <section className="detailLazyPanel" id="free-detail" ref={detailLoaderRef}>
              <span className="result-panel-label">{detailTexts.label}</span>
              <h3>{detailStatus === "loading" ? detailTexts.loadingTitle : detailTexts.title}</h3>
              <p>{detailStatus === "loading" ? detailTexts.loadingBody : detailTexts.body}</p>
              {detailError ? <p className="detailLazyError">{detailError}</p> : null}
              <button
                className="detailLazyButton"
                type="button"
                disabled={detailStatus === "loading"}
                onClick={() => void loadFreeDetail("#core-analysis")}
              >
                {detailStatus === "loading" ? detailTexts.loadingTitle : detailTexts.button}
              </button>
            </section>
          )}
        </div>

        <aside className="result-side-column">
          <section className="result-side-panel">
            <span className="result-panel-label">{viewTexts.outlineLabel}</span>
            <nav className="result-section-nav" aria-label={viewTexts.outlineLabel}>
              {detailNavSections.map((section) => (
                <a
                  className="result-section-link"
                  href={`#${section.anchorId}`}
                  key={section.key}
                  onClick={(event) => handleDetailNavClick(event, `#${section.anchorId}`)}
                >
                  <span>{section.badge}</span>
                  <strong>{section.section.title}</strong>
                </a>
              ))}
            </nav>
          </section>

          <section className="result-side-panel">
            <span className="result-panel-label">{viewTexts.basisLabel}</span>
            <ul className="result-basis-list">
              {viewTexts.basisItems.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </section>
        </aside>
      </div>
    </section>
  );
}
