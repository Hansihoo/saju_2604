export type Locale = "ko" | "en";

type CopyDefinition = {
  title: string;
  subtitle: string;
  birthDate: string;
  birthTime: string;
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
};

export const copy: Record<Locale, CopyDefinition> = {
  ko: {
    title: "사주 / 운세 풀이",
    subtitle: "출생 정보를 입력해 주세요.",
    birthDate: "생년월일",
    birthTime: "출생 시간",
    unknownTime: "시간 모름",
    region: "출생 지역",
    regionPlaceholder: "지역을 검색해 선택해 주세요.",
    gender: "성별",
    male: "남성",
    female: "여성",
    calendarType: "달력 기준",
    solar: "양력",
    lunar: "음력",
    leapMonth: "윤달",
    submit: "사주 풀이",
    loading: "사주 풀이 중...",
    resultTitle: "사주 결과",
    overview: "전체 흐름",
    strengths: "강점",
    cautions: "주의",
    love: "연애",
    career: "직업",
    wealth: "금전",
    action: "행동",
    backToForm: "다시 입력",
    language: "언어",
    regionRequired: "추천 목록에서 출생 지역을 선택해 주세요.",
    noSuggestions: "검색 결과가 없습니다.",
    noResult: "결과를 불러오지 못했습니다.",
    online: "백엔드 연결됨",
    offline: "백엔드 연결 대기",
    devTitle: "개발자 화면",
    devLead: "파이프라인 상태와 debug trace를 확인합니다.",
    pipeline: "파이프라인",
    requestEcho: "요청 데이터",
    checkpoints: "체크포인트",
    system: "시스템 상태",
    backToService: "사용자 화면",
    noDebugData: "아직 확인할 preview 결과가 없습니다.",
  },
  en: {
    title: "Saju / fortune reading",
    subtitle: "Enter the birth details.",
    birthDate: "Birth date",
    birthTime: "Birth time",
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
    loading: "Reading...",
    resultTitle: "Saju result",
    overview: "Overall flow",
    strengths: "Strengths",
    cautions: "Cautions",
    love: "Love",
    career: "Career",
    wealth: "Wealth",
    action: "Action",
    backToForm: "Edit input",
    language: "Language",
    regionRequired: "Please select a region from the suggestion list.",
    noSuggestions: "No matching regions found.",
    noResult: "Could not load the result.",
    online: "Backend connected",
    offline: "Waiting for backend",
    devTitle: "Developer view",
    devLead: "Check pipeline status and debug trace.",
    pipeline: "Pipeline",
    requestEcho: "Request data",
    checkpoints: "Checkpoints",
    system: "System status",
    backToService: "Service page",
    noDebugData: "No preview result is available yet.",
  },
};

export function getCopy(locale: Locale) {
  return copy[locale];
}
