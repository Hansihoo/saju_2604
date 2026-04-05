import { FormEvent, useEffect, useState } from "react";

type ApiHealth = {
  status: string;
  service: string;
  version: string;
  message: string;
  focus: string[];
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

const highlights = [
  {
    title: "쉽게 읽히는 해석",
    body: "복잡한 용어를 줄이고, 지금의 감정과 선택에 연결되는 설명으로 정리합니다."
  },
  {
    title: "입력 부담 최소화",
    body: "생년월일과 출생 시간 중심으로 시작하고, 필요한 정보만 단계적으로 요청합니다."
  },
  {
    title: "모바일 우선 경험",
    body: "상담 예약 전 탐색, 오늘의 흐름 확인, 핵심 결과 공유까지 휴대폰에서 자연스럽게 이어집니다."
  }
];

const roadmap = [
  "사주 기본 정보 입력",
  "초기 성향 리포트 생성",
  "오늘의 흐름 카드",
  "해석 결과 저장 및 재조회"
];

export default function App() {
  const [name, setName] = useState("지민");
  const [birthDate, setBirthDate] = useState("1994-10-13");
  const [birthTime, setBirthTime] = useState("08:30");
  const [apiHealth, setApiHealth] = useState<ApiHealth | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    async function loadHealth() {
      try {
        const response = await fetch(`${API_BASE_URL}/health`);

        if (!response.ok) {
          throw new Error(`API responded with ${response.status}`);
        }

        const data = (await response.json()) as ApiHealth;
        setApiHealth(data);
        setApiError(null);
      } catch (error) {
        setApiError("API 연결 전 상태입니다. 백엔드를 실행하면 준비 상태를 확인할 수 있어요.");
      }
    }

    void loadHealth();
  }, []);

  function handlePreviewSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitted(true);
  }

  const previewMessage = submitted
    ? `${name}님은 차분한 관찰력과 빠른 결단이 함께 보이는 흐름으로 해석해볼 수 있어요. 지금 버전에서는 입력 경험을 먼저 다듬고, 다음 단계에서 실제 해석 엔진을 붙일 예정입니다.`
    : "입력값을 바탕으로 어떤 톤의 해석을 보여줄지 미리 볼 수 있는 자리입니다.";

  return (
    <div className="page-shell">
      <main className="layout">
        <section className="hero">
          <div className="hero-copy">
            <p className="eyebrow">SAJU WEB MVP</p>
            <h1>사주의 결을 읽고, 오늘의 선택에 연결하는 웹 서비스</h1>
            <p className="hero-text">
              suju-insight는 전통적인 사주 정보를 더 부드럽고 선명한 디지털 경험으로
              풀어내는 프로젝트입니다. 첫 버전은 입력 부담을 낮추고, 해석 결과가
              어렵지 않게 읽히도록 만드는 데 집중합니다.
            </p>

            <div className="hero-actions">
              <a className="primary-action" href="#preview">
                입력 경험 보기
              </a>
              <a className="ghost-action" href="#status">
                API 상태 확인
              </a>
            </div>
          </div>

          <div className="hero-panel">
            <div className="metric-card">
              <span>현재 목표</span>
              <strong>MVP 구조 확정</strong>
            </div>
            <div className="metric-card">
              <span>핵심 사용자 경험</span>
              <strong>모바일에서 3분 내 첫 해석</strong>
            </div>
            <div className="metric-card accent">
              <span>이번 스프린트</span>
              <strong>랜딩 + 입력 미리보기 + API 뼈대</strong>
            </div>
          </div>
        </section>

        <section className="section-grid">
          {highlights.map((item) => (
            <article className="feature-card" key={item.title}>
              <h2>{item.title}</h2>
              <p>{item.body}</p>
            </article>
          ))}
        </section>

        <section className="workspace">
          <article className="roadmap-card">
            <p className="section-label">MVP ROADMAP</p>
            <h2>사용자가 가장 먼저 느껴야 할 흐름</h2>
            <ul>
              {roadmap.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>

          <article className="preview-card" id="preview">
            <p className="section-label">INPUT PREVIEW</p>
            <h2>사주 입력 경험 초안</h2>
            <form className="preview-form" onSubmit={handlePreviewSubmit}>
              <label>
                이름
                <input value={name} onChange={(event) => setName(event.target.value)} />
              </label>

              <label>
                생년월일
                <input
                  type="date"
                  value={birthDate}
                  onChange={(event) => setBirthDate(event.target.value)}
                />
              </label>

              <label>
                출생 시간
                <input
                  type="time"
                  value={birthTime}
                  onChange={(event) => setBirthTime(event.target.value)}
                />
              </label>

              <button type="submit">해석 톤 미리보기</button>
            </form>

            <div className="preview-result">
              <p className="result-meta">
                입력값: {birthDate} / {birthTime || "시간 미입력"}
              </p>
              <p>{previewMessage}</p>
            </div>
          </article>
        </section>

        <section className="status-card" id="status">
          <div>
            <p className="section-label">SERVICE STATUS</p>
            <h2>백엔드 준비 상태</h2>
          </div>

          {apiHealth ? (
            <div className="status-success">
              <p>
                <strong>{apiHealth.service}</strong> {apiHealth.version}
              </p>
              <p>{apiHealth.message}</p>
              <div className="pill-row">
                <span className="pill pill-success">{apiHealth.status}</span>
                {apiHealth.focus.map((item) => (
                  <span className="pill" key={item}>
                    {item}
                  </span>
                ))}
              </div>
            </div>
          ) : (
            <div className="status-pending">
              <p>{apiError ?? "API 상태를 확인하는 중입니다."}</p>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

