export type Locale = "ko" | "en";

type CopyDefinition = {
  title: string;
  subtitle: string;
  birthDate: string;
  birthDatePlaceholder: string;
  birthDateInvalid: string;
  birthTime: string;
  birthTimePlaceholder: string;
  birthTimeInvalid: string;
  unknownTime: string;
  region: string;
  regionPlaceholder: string;
  gender: string;
  male: string;
  female: string;
  calendarType: string;
  solar: string;
  lunar: string;
  leapMonth: string;
  submit: string;
  loading: string;
  resultTitle: string;
  overview: string;
  strengths: string;
  cautions: string;
  love: string;
  career: string;
  wealth: string;
  action: string;
  backToForm: string;
  language: string;
  regionRequired: string;
  noSuggestions: string;
  noResult: string;
  online: string;
  offline: string;
  devTitle: string;
  devLead: string;
  pipeline: string;
  requestEcho: string;
  checkpoints: string;
  system: string;
  backToService: string;
  noDebugData: string;
  coreAnalysis: string;
  luckFlow: string;
  currentFlow: string;
  nextFlow: string;
  conclusionLabel: string;
  evidenceLabel: string;
  explanationLabel: string;
  overviewLabel: string;
  differenceLabel: string;
  strengthsLabel: string;
  cautionsLabel: string;
  adviceLabel: string;
  marriageLabel: string;
  goodMatchLabel: string;
  difficultMatchLabel: string;
  relativeLevelLabel: string;
  favorableTimingLabel: string;
  suitableEnvironmentLabel: string;
};

export const copy: Record<Locale, CopyDefinition> = {
  ko: {
    title: "사주 / 운세 풀이",
    subtitle: "출생 정보를 입력해 주세요.",
    birthDate: "생년월일",
    birthDatePlaceholder: "YYYY-MM-DD",
    birthDateInvalid: "생년월일을 YYYY-MM-DD 형식으로 입력해 주세요.",
    birthTime: "출생 시간",
    birthTimePlaceholder: "HH:MM",
    birthTimeInvalid: "출생 시간을 HH:MM 형식으로 입력해 주세요.",
    unknownTime: "시간 모름",
    region: "출생 지역",
    regionPlaceholder: "지역을 검색해 선택해 주세요",
    gender: "성별",
    male: "남성",
    female: "여성",
    calendarType: "달력 기준",
    solar: "양력",
    lunar: "음력",
    leapMonth: "윤달",
    submit: "사주 풀이",
    loading: "사주를 계산하고 있어요...",
    resultTitle: "사주 결과",
    overview: "전체 흐름",
    strengths: "강점",
    cautions: "주의",
    love: "연애운",
    career: "직장운",
    wealth: "금전운",
    action: "행동 조언",
    backToForm: "다시 입력",
    language: "언어",
    regionRequired: "추천 목록에서 출생 지역을 선택해 주세요.",
    noSuggestions: "검색 결과가 없습니다.",
    noResult: "결과를 불러오지 못했습니다.",
    online: "백엔드 연결됨",
    offline: "백엔드 연결 대기",
    devTitle: "개발자 화면",
    devLead: "파이프라인 상태와 검증용 만세력 정보를 확인합니다.",
    pipeline: "파이프라인",
    requestEcho: "요청 정보",
    checkpoints: "체크포인트",
    system: "시스템 상태",
    backToService: "사용자 화면",
    noDebugData: "아직 확인할 preview 결과가 없습니다.",
    coreAnalysis: "내 사주의 특징",
    luckFlow: "대운 흐름",
    currentFlow: "현재 흐름",
    nextFlow: "다음 흐름",
    conclusionLabel: "결론",
    evidenceLabel: "근거",
    explanationLabel: "설명",
    overviewLabel: "특징",
    differenceLabel: "평균과 다른 점",
    strengthsLabel: "장점",
    cautionsLabel: "단점 / 주의점",
    adviceLabel: "어떻게 해야 하는지",
    marriageLabel: "결혼운",
    goodMatchLabel: "잘 맞는 배우자",
    difficultMatchLabel: "잘 맞지 않는 사람",
    relativeLevelLabel: "상대적인 금전 흐름",
    favorableTimingLabel: "좋아질 가능성이 큰 시기",
    suitableEnvironmentLabel: "잘 맞는 환경",
  },
  en: {
    title: "Saju / fortune reading",
    subtitle: "Enter the birth details.",
    birthDate: "Birth date",
    birthDatePlaceholder: "YYYY-MM-DD",
    birthDateInvalid: "Enter the birth date in YYYY-MM-DD format.",
    birthTime: "Birth time",
    birthTimePlaceholder: "HH:MM",
    birthTimeInvalid: "Enter the birth time in HH:MM format.",
    unknownTime: "Unknown time",
    region: "Birth region",
    regionPlaceholder: "Search and select a region",
    gender: "Gender",
    male: "Male",
    female: "Female",
    calendarType: "Calendar type",
    solar: "Solar",
    lunar: "Lunar",
    leapMonth: "Leap month",
    submit: "Read my saju",
    loading: "Preparing your reading...",
    resultTitle: "Saju result",
    overview: "Overall flow",
    strengths: "Strengths",
    cautions: "Cautions",
    love: "Love",
    career: "Career",
    wealth: "Wealth",
    action: "Action advice",
    backToForm: "Edit input",
    language: "Language",
    regionRequired: "Please select a region from the suggestion list.",
    noSuggestions: "No matching regions found.",
    noResult: "Could not load the result.",
    online: "Backend connected",
    offline: "Waiting for backend",
    devTitle: "Developer view",
    devLead: "Check pipeline status and validation-oriented manse data.",
    pipeline: "Pipeline",
    requestEcho: "Request data",
    checkpoints: "Checkpoints",
    system: "System status",
    backToService: "Service page",
    noDebugData: "No preview result is available yet.",
    coreAnalysis: "Core traits",
    luckFlow: "Luck flow",
    currentFlow: "Current flow",
    nextFlow: "Next flow",
    conclusionLabel: "Conclusion",
    evidenceLabel: "Evidence",
    explanationLabel: "Explanation",
    overviewLabel: "Overview",
    differenceLabel: "What stands out",
    strengthsLabel: "Strengths",
    cautionsLabel: "Risks and cautions",
    adviceLabel: "What to do",
    marriageLabel: "Marriage",
    goodMatchLabel: "Good match",
    difficultMatchLabel: "Difficult match",
    relativeLevelLabel: "Relative wealth trend",
    favorableTimingLabel: "Better timing",
    suitableEnvironmentLabel: "Suitable environment",
  },
};

export function getCopy(locale: Locale) {
  return copy[locale];
}
