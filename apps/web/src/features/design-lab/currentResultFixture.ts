export type DesignArticle = {
  title: string;
  subtitle: string;
  chips: string[];
  body: string[];
  takeaway: string;
  question: string;
  basis: string;
  tone: "core" | "work" | "love" | "flow";
};

export type DesignFixture = {
  pillars: string[];
  headline: string;
  overview: string[];
  badges: string[];
  diagnoses: Array<{
    title: string;
    body: string;
    tone: "strength" | "pattern" | "task";
  }>;
  elements: Array<{
    key: "wood" | "fire" | "earth" | "metal" | "water";
    label: string;
    value: number;
    state: "low" | "normal" | "high";
  }>;
  metrics: Array<{
    label: string;
    value: number;
    tone: "teal" | "gold" | "rose" | "blue";
  }>;
  timeline: Array<{
    label: string;
    period: string;
    note: string;
    active?: boolean;
  }>;
  articles: DesignArticle[];
};

export const currentResultFixture: DesignFixture = {
  pillars: ["무진", "계해", "경진", "병자"],
  headline: "괜찮다고 말해도 마음속 계산이 많은 사람",
  overview: [
    "겉으로는 담담해 보여도 속으로는 해야 할 일과 사람의 반응을 오래 재는 편입니다.",
    "상황을 읽고 필요한 말을 골라내는 힘이 있어 일에서는 문제를 발견하고 틀을 잡는 데 강점이 있습니다.",
    "지금은 일과 역할에서 안정된 자리를 만들고, 오래 가져갈 관계와 놓을 일을 차분히 가려보는 때입니다.",
  ],
  badges: ["절기 기준", "시간대 보정", "경계값 확인 필요"],
  diagnoses: [
    {
      title: "가장 강한 점",
      body:
        "가장 큰 힘은 급하게 흔들리기보다 주변 상황을 읽고 필요한 역할을 끝까지 붙잡는 데 있습니다.",
      tone: "strength",
    },
    {
      title: "반복되는 패턴",
      body:
        "문제가 생기면 먼저 속으로 계산하고, 해결책이 어느 정도 보일 때까지 말을 아끼는 편입니다.",
      tone: "pattern",
    },
    {
      title: "지금 시기 과제",
      body:
        "맡은 일을 넓히는 것보다 계속 감당할 수 있는 방식으로 역할을 나누는 선택이 중요합니다.",
      tone: "task",
    },
  ],
  elements: [
    { key: "wood", label: "목", value: 10, state: "low" },
    { key: "fire", label: "화", value: 18, state: "normal" },
    { key: "earth", label: "토", value: 32, state: "high" },
    { key: "metal", label: "금", value: 12, state: "low" },
    { key: "water", label: "수", value: 28, state: "high" },
  ],
  metrics: [
    { label: "책임감", value: 84, tone: "teal" },
    { label: "관계 속도", value: 52, tone: "rose" },
    { label: "돈 관리", value: 73, tone: "gold" },
    { label: "현재 흐름", value: 68, tone: "blue" },
  ],
  timeline: [
    {
      label: "현재 대운",
      period: "35세 4개월 - 45세 4개월",
      note: "역할을 안정시키고 책임의 범위를 정리하는 시기",
      active: true,
    },
    {
      label: "다음 대운",
      period: "45세 4개월 - 55세 4개월",
      note: "배움과 생활 기반을 다시 다지는 전환",
    },
  ],
  articles: [
    {
      title: "내 사주 특징",
      subtitle: "단단해 보이지만 책임과 피로를 함께 안고 움직입니다",
      chips: ["혼자 판단함", "속으로 오래 살핌", "책임을 오래 붙잡음", "표현은 늦게 나옴"],
      body: [
        "겉으로는 크게 흔들리지 않는 사람처럼 보이지만, 속에서는 여러 경우를 동시에 따져보는 시간이 깁니다.",
        "지금 필요한 사용법은 더 강하게 버티는 것이 아니라, 맡을 몫과 넘길 몫을 생활 속에서 구분하는 일입니다.",
      ],
      takeaway: "오래 버틴 뒤에야 말하면 관계와 일에서 비용이 커집니다.",
      question: "왜 어떤 일은 끝까지 해내는데, 어떤 일은 시작 전부터 피로가 먼저 올까요?",
      basis: "기술 근거는 접힌 영역이나 전문가 보기로 분리",
      tone: "core",
    },
    {
      title: "일과 돈의 흐름",
      subtitle: "성과는 책임 있는 자리에서 나오고 돈은 관리 습관에서 체감됩니다",
      chips: ["역할이 커짐", "문제 발견력", "지출 점검", "경계 세우기"],
      body: [
        "일에서는 눈앞의 일을 그대로 처리하기보다, 어디가 막히는지 먼저 보는 힘이 있습니다.",
        "수입은 갑자기 확 넓히는 방식보다 꾸준히 맡은 역할을 안정시키며 쌓는 쪽이 어울립니다.",
      ],
      takeaway: "돈의 문제는 버는 힘만이 아니라 피로 때문에 쉽게 쓰는 지점에서도 봐야 합니다.",
      question: "돈이 들어와도 체감이 늦은 이유는 어디에서 새는 습관 때문일까요?",
      basis: "월주, 식상, 재성 등은 상세 근거로 이동",
      tone: "work",
    },
    {
      title: "연애와 결혼 흐름",
      subtitle: "마음은 깊게 보지만 표현은 늦고 약속의 무게를 오래 확인합니다",
      chips: ["천천히 마음 염", "신뢰를 오래 봄", "서운함 누적", "거리 조절 필요"],
      body: [
        "관계에서는 가볍게 시작해도 속으로는 오래 갈 수 있는지 먼저 살피는 편입니다.",
        "작은 불편함을 일찍 말하는 연습이 중요합니다. 표현을 아끼는 만큼 오해가 커질 수 있습니다.",
      ],
      takeaway: "마음이 깊은 만큼 표현을 아끼면 상대는 깊이를 못 보고 거리만 느낄 수 있습니다.",
      question: "왜 어떤 관계에서는 편한데, 어떤 관계에서는 금방 지칠까요?",
      basis: "배우자궁과 보조 지표는 하단 근거로 분리",
      tone: "love",
    },
    {
      title: "현재 운과 대운 흐름",
      subtitle: "현재는 역할을 안정시키고 다음 시기에는 생활 기반을 다시 다집니다",
      chips: ["역할 강화", "생활 안정", "부담 조절", "다음 준비"],
      body: [
        "현재 시기는 책임 있는 자리에 서거나, 이미 맡은 일을 더 안정적으로 만드는 쪽에 힘이 실립니다.",
        "넓히기 전에 비워 둘 자리를 만드는 것이 좋습니다.",
      ],
      takeaway: "지금은 넓히는 힘보다 오래 가져갈 수 있게 줄이고 나누는 선택이 실속 있습니다.",
      question: "다음 변화 전에 먼저 덜어내야 할 생활 패턴은 무엇일까요?",
      basis: "현재/다음 대운 정보는 타임라인으로 시각화",
      tone: "flow",
    },
  ],
};
