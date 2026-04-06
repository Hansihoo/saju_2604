import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";

import {
  RegionSuggestion,
  SajuPreviewResponse,
  createSajuPreview,
  searchRegionSuggestions,
} from "./shared/api/saju";

type Locale = "ko" | "en";
type Mode = "service" | "dev";

type ApiHealth = {
  status: string;
  service: string;
  version: string;
  message: string;
  focus: string[];
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

const copy = {
  ko: {
    title: "사주 / 운세 풀이",
    subtitle: "출생 정보를 입력해 주세요.",
    birthDate: "생년월일",
    birthTime: "출생 시간",
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
    devLead: "파이프라인과 debug trace를 확인합니다.",
    pipeline: "파이프라인",
    requestEcho: "요청 데이터",
    checkpoints: "체크포인트",
    system: "시스템 상태",
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
  },
} as const;

function getMode(pathname: string): Mode {
  return pathname.startsWith("/dev") ? "dev" : "service";
}

export default function App() {
  const [locale, setLocale] = useState<Locale>("ko");
  const [mode, setMode] = useState<Mode>(() => getMode(window.location.pathname));
  const [birthDate, setBirthDate] = useState("1994-10-13");
  const [birthTime, setBirthTime] = useState("08:30");
  const [isBirthTimeEstimated, setIsBirthTimeEstimated] = useState(false);
  const [regionQuery, setRegionQuery] = useState("");
  const [selectedRegion, setSelectedRegion] = useState<RegionSuggestion | null>(null);
  const [regionOptions, setRegionOptions] = useState<RegionSuggestion[]>([]);
  const [highlightedRegionIndex, setHighlightedRegionIndex] = useState(-1);
  const [isRegionFocused, setIsRegionFocused] = useState(false);
  const [regionLoading, setRegionLoading] = useState(false);
  const [gender, setGender] = useState<"male" | "female">("female");
  const [calendarType, setCalendarType] = useState<"solar" | "lunar">("solar");
  const [isLunarLeapMonth, setIsLunarLeapMonth] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SajuPreviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [apiHealth, setApiHealth] = useState<ApiHealth | null>(null);

  const texts = copy[locale];
  const regionBoxRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const onPopState = () => setMode(getMode(window.location.pathname));
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    async function loadHealth() {
      const response = await fetch(`${API_BASE_URL}/health`);
      if (!response.ok) {
        throw new Error("health");
      }
      setApiHealth((await response.json()) as ApiHealth);
    }

    void loadHealth().catch(() => setApiHealth(null));
  }, []);

  useEffect(() => {
    if (!isRegionFocused || selectedRegion || regionQuery.trim().length === 0) {
      setRegionOptions([]);
      setHighlightedRegionIndex(-1);
      return;
    }

    const timeoutId = window.setTimeout(async () => {
      setRegionLoading(true);
      try {
        const items = await searchRegionSuggestions(regionQuery.trim());
        setRegionOptions(items);
        setHighlightedRegionIndex(items.length > 0 ? 0 : -1);
      } catch (_error) {
        setRegionOptions([]);
        setHighlightedRegionIndex(-1);
      } finally {
        setRegionLoading(false);
      }
    }, 250);

    return () => window.clearTimeout(timeoutId);
  }, [isRegionFocused, regionQuery, selectedRegion]);

  useEffect(() => {
    function handleDocumentClick(event: MouseEvent) {
      if (!regionBoxRef.current?.contains(event.target as Node)) {
        setIsRegionFocused(false);
      }
    }

    document.addEventListener("mousedown", handleDocumentClick);
    return () => document.removeEventListener("mousedown", handleDocumentClick);
  }, []);

  function navigate(nextMode: Mode) {
    window.history.pushState({}, "", nextMode === "dev" ? "/dev" : "/");
    setMode(nextMode);
  }

  function handleUnknownTimeChange(checked: boolean) {
    setIsBirthTimeEstimated(checked);
    if (checked) {
      setBirthTime("00:00");
    }
  }

  function handleRegionSelect(region: RegionSuggestion) {
    setSelectedRegion(region);
    setRegionQuery(region.display_name);
    setRegionOptions([]);
    setHighlightedRegionIndex(-1);
    setIsRegionFocused(false);
    setError(null);
  }

  function handleRegionInputKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      setIsRegionFocused(false);
      setHighlightedRegionIndex(-1);
      return;
    }

    if (!regionOptions.length) {
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlightedRegionIndex((current) => (current + 1) % regionOptions.length);
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlightedRegionIndex((current) =>
        current <= 0 ? regionOptions.length - 1 : current - 1,
      );
    }

    if (event.key === "Enter" && highlightedRegionIndex >= 0) {
      event.preventDefault();
      handleRegionSelect(regionOptions[highlightedRegionIndex]);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!selectedRegion) {
      setError(texts.regionRequired);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await createSajuPreview(
        {
          calendar_type: calendarType,
          birth_date: birthDate,
          birth_time: birthTime,
          is_birth_time_estimated: isBirthTimeEstimated,
          is_lunar_leap_month: isLunarLeapMonth,
          gender,
          region_id: selectedRegion.id,
          debug: false,
        },
        false,
      );
      setResult(response);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : texts.noResult);
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  const showRegionSuggestions =
    mode === "service" &&
    isRegionFocused &&
    !selectedRegion &&
    regionQuery.trim().length > 0;

  if (mode === "dev") {
    return (
      <div className="page-shell dev-page">
        <main className="dev-container">
          <header className="dev-header">
            <button className="dev-link-button" type="button" onClick={() => navigate("service")}>
              ← 사용자 화면
            </button>
            <label className="locale-select">
              <span>{texts.language}</span>
              <select value={locale} onChange={(event) => setLocale(event.target.value as Locale)}>
                <option value="ko">한국어</option>
                <option value="en">English</option>
              </select>
            </label>
          </header>

          <section className="dev-section">
            <h1>{texts.devTitle}</h1>
            <p>{texts.devLead}</p>
          </section>

          <section className="dev-section">
            <h2>{texts.system}</h2>
            <p>{apiHealth ? texts.online : texts.offline}</p>
          </section>

          {result ? (
            <>
              <section className="dev-section">
                <h2>{texts.pipeline}</h2>
                <ul className="dev-list">
                  {Object.entries(result.pipeline_status).map(([key, value]) => (
                    <li key={key}>
                      <span>{key}</span>
                      <strong>{value}</strong>
                    </li>
                  ))}
                </ul>
              </section>

              {result.debug_trace ? (
                <>
                  <section className="dev-section">
                    <h2>{texts.checkpoints}</h2>
                    <ul className="dev-list stacked">
                      {result.debug_trace.checkpoints.map((checkpoint) => (
                        <li key={checkpoint.stage}>
                          <strong>{checkpoint.stage}</strong>
                          <span>{checkpoint.status}</span>
                        </li>
                      ))}
                    </ul>
                  </section>

                  <section className="dev-section">
                    <h2>{texts.requestEcho}</h2>
                    <pre className="dev-pre">
                      {JSON.stringify(result.debug_trace.request_echo, null, 2)}
                    </pre>
                  </section>
                </>
              ) : null}
            </>
          ) : null}
        </main>
      </div>
    );
  }

  return (
    <div className="page-shell">
      <main className="service-page">
        <header className="service-header">
          <div className="service-header-top">
            <span className="service-icon" aria-hidden="true">
              命
            </span>
            <label className="locale-select">
              <span>{texts.language}</span>
              <select value={locale} onChange={(event) => setLocale(event.target.value as Locale)}>
                <option value="ko">한국어</option>
                <option value="en">English</option>
              </select>
            </label>
          </div>
          <h1>{texts.title}</h1>
          <p>{texts.subtitle}</p>
        </header>

        {result ? (
          <section className="result-screen">
            <div className="result-header">
              <h2>{texts.resultTitle}</h2>
              <button className="secondary-button" type="button" onClick={() => setResult(null)}>
                {texts.backToForm}
              </button>
            </div>

            <div className="result-section">
              <h3>{texts.overview}</h3>
              <p>{result.result.overview}</p>
            </div>
            <div className="result-section">
              <h3>{texts.strengths}</h3>
              <p>{result.result.strengths[0]}</p>
            </div>
            <div className="result-section">
              <h3>{texts.cautions}</h3>
              <p>{result.result.cautions[0]}</p>
            </div>
            <div className="result-section">
              <h3>{texts.love}</h3>
              <p>{result.result.love}</p>
            </div>
            <div className="result-section">
              <h3>{texts.career}</h3>
              <p>{result.result.career}</p>
            </div>
            <div className="result-section">
              <h3>{texts.wealth}</h3>
              <p>{result.result.wealth}</p>
            </div>
            <div className="result-section">
              <h3>{texts.action}</h3>
              <p>{result.result.action_advice}</p>
            </div>
          </section>
        ) : (
          <form className="service-form" onSubmit={handleSubmit}>
            <div className="form-field">
              <label htmlFor="birth-date">{texts.birthDate}</label>
              <input id="birth-date" type="date" value={birthDate} onChange={(event) => setBirthDate(event.target.value)} />
            </div>

            <div className="form-field">
              <label htmlFor="birth-time">{texts.birthTime}</label>
              <div className="time-field-row">
                <input
                  id="birth-time"
                  type="time"
                  value={birthTime}
                  disabled={isBirthTimeEstimated}
                  onChange={(event) => setBirthTime(event.target.value)}
                />
                <label className="inline-check">
                  <input
                    type="checkbox"
                    checked={isBirthTimeEstimated}
                    onChange={(event) => handleUnknownTimeChange(event.target.checked)}
                  />
                  <span>{texts.unknownTime}</span>
                </label>
              </div>
            </div>

            <div className="form-field" ref={regionBoxRef}>
              <label htmlFor="birth-region">{texts.region}</label>
              <div className="region-input-shell">
                <input
                  id="birth-region"
                  type="text"
                  autoComplete="off"
                  value={regionQuery}
                  placeholder={texts.regionPlaceholder}
                  onFocus={() => setIsRegionFocused(true)}
                  onKeyDown={handleRegionInputKeyDown}
                  onChange={(event) => {
                    setRegionQuery(event.target.value);
                    setSelectedRegion(null);
                    setIsRegionFocused(true);
                    setError(null);
                  }}
                />
              </div>

              {showRegionSuggestions ? (
                <div className="autocomplete-list" role="listbox">
                  {regionLoading ? (
                    <div className="autocomplete-empty">Loading...</div>
                  ) : regionOptions.length > 0 ? (
                    regionOptions.map((item, index) => (
                      <button
                        key={item.id}
                        type="button"
                        className={`autocomplete-item${highlightedRegionIndex === index ? " active" : ""}`}
                        onMouseDown={(event) => {
                          event.preventDefault();
                          handleRegionSelect(item);
                        }}
                      >
                        {item.display_name}
                      </button>
                    ))
                  ) : (
                    <div className="autocomplete-empty">{texts.noSuggestions}</div>
                  )}
                </div>
              ) : null}
            </div>

            <div className="form-field">
              <span className="field-legend">{texts.gender}</span>
              <div className="radio-group">
                <label className="radio-inline">
                  <input type="radio" name="gender" checked={gender === "male"} onChange={() => setGender("male")} />
                  <span>{texts.male}</span>
                </label>
                <label className="radio-inline">
                  <input type="radio" name="gender" checked={gender === "female"} onChange={() => setGender("female")} />
                  <span>{texts.female}</span>
                </label>
              </div>
            </div>

            <div className="form-field">
              <span className="field-legend">{texts.calendarType}</span>
              <div className="radio-group">
                <label className="radio-inline">
                  <input
                    type="radio"
                    name="calendar-type"
                    checked={calendarType === "solar"}
                    onChange={() => setCalendarType("solar")}
                  />
                  <span>{texts.solar}</span>
                </label>
                <label className="radio-inline">
                  <input
                    type="radio"
                    name="calendar-type"
                    checked={calendarType === "lunar"}
                    onChange={() => setCalendarType("lunar")}
                  />
                  <span>{texts.lunar}</span>
                </label>
              </div>
              {calendarType === "lunar" ? (
                <label className="inline-check subtle">
                  <input
                    type="checkbox"
                    checked={isLunarLeapMonth}
                    onChange={(event) => setIsLunarLeapMonth(event.target.checked)}
                  />
                  <span>{texts.leapMonth}</span>
                </label>
              ) : null}
            </div>

            {error ? <p className="form-error">{error}</p> : null}

            <button className="submit-button" type="submit" disabled={loading}>
              {loading ? texts.loading : texts.submit}
            </button>
          </form>
        )}
      </main>
    </div>
  );
}
