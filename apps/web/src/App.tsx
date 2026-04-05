import { FormEvent, useEffect, useState } from "react";

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

const ko = {
  brand: "\uc0ac\uc720\uba85\ub9ac",
  badge: "AI \uc0ac\uc8fc \ub9ac\ub529",
  service: "\uc11c\ube44\uc2a4",
  dev: "\uac1c\ubc1c",
  language: "\uc5b8\uc5b4",
  online: "\ubc31\uc5d4\ub4dc \uc5f0\uacb0\ub428",
  offline: "\ubc31\uc5d4\ub4dc \uc5f0\uacb0 \ub300\uae30",
  heroEyebrow: "\uc815\ud655\ud55c \uacc4\uc0b0 \uae30\ubc18 \ud574\uc11d",
  heroTitle: "\uc0ac\uc6a9\uc790\uc6a9 \ud654\uba74\uacfc \uac1c\ubc1c\uc790\uc6a9 \ud654\uba74\uc744 \ubd84\ub9ac\ud588\uc2b5\ub2c8\ub2e4.",
  heroText:
    "\uba54\uc778 \ud654\uba74\uc740 \uc0ac\uc6a9\uc790 \uacbd\ud5d8\uc5d0 \uc9d1\uc911\ud558\uace0, \uac1c\ubc1c\uc790 \ud654\uba74\uc740 \ud30c\uc774\ud504\ub77c\uc778\uacfc \ub514\ubc84\uadf8 \uc815\ubcf4\ub97c \ub530\ub85c \ud655\uc778\ud558\ub3c4\ub85d \uad6c\uc131\ud569\ub2c8\ub2e4.",
  formTitle: "\ucd9c\uc0dd \uc815\ubcf4\ub97c \uc785\ub825\ud574 \uc8fc\uc138\uc694",
  formLead:
    "\uc9c0\uc5ed, \uc2dc\uac04, \ub2ec\ub825 \uae30\uc900\uc744 \ubc14\ud0d5\uc73c\ub85c \ud604\uc7ac \uad6c\ud604\ub41c \uc0ac\uc8fc \uacc4\uc0b0 \ud750\ub984\uc744 \ud655\uc778\ud569\ub2c8\ub2e4.",
  calendarType: "\ub2ec\ub825 \uae30\uc900",
  solar: "\uc591\ub825",
  lunar: "\uc74c\ub825",
  birthDate: "\uc0dd\ub144\uc6d4\uc77c",
  birthTime: "\ucd9c\uc0dd \uc2dc\uac01",
  estimatedTime: "\ucd9c\uc0dd\uc2dc\uac04\uc744 \uc815\ud655\ud788 \ubaa8\ub985\ub2c8\ub2e4",
  leapMonth: "\uc724\ub2ec\uc785\ub2c8\ub2e4",
  gender: "\uc131\ubcc4",
  female: "\uc5ec\uc131",
  male: "\ub0a8\uc131",
  region: "\ucd9c\uc0dd \uc9c0\uc5ed",
  regionPlaceholder: "\uc9c0\uc5ed\uc744 \uc785\ub825\ud558\uba74 \ucd94\ucc9c \ubaa9\ub85d\uc774 \ub098\ud0c0\ub0a9\ub2c8\ub2e4",
  regionValidation: "\ucd94\ucc9c \ubaa9\ub85d\uc5d0\uc11c \uc9c0\uc5ed\uc744 \ud558\ub098 \uc120\ud0dd\ud574 \uc8fc\uc138\uc694.",
  selectedRegion: "\uc120\ud0dd\ub41c \uc9c0\uc5ed",
  noRegion: "\uc544\uc9c1 \uc120\ud0dd\ub418\uc9c0 \uc54a\uc558\uc2b5\ub2c8\ub2e4.",
  advanced: "\uace0\uae09 \uc635\uc158",
  debug: "\uac1c\ubc1c\uc6a9 trace \ud3ec\ud568",
  submit: "\uacb0\uacfc \ubcf4\uae30",
  submitting: "\uacc4\uc0b0 \uc911...",
  resultTitle: "\ub2f9\uc2e0\uc758 \uae30\ubcf8 \uc0ac\uc8fc \ub9ac\ub529",
  resultEmpty: "\uc785\ub825\uc744 \uc644\ub8cc\ud558\uba74 \uc694\uc57d \uacb0\uacfc\uc640 \uadfc\uac70 \uc815\ubcf4\ub97c \ubcfc \uc218 \uc788\uc2b5\ub2c8\ub2e4.",
  regionLabel: "\uae30\uc900 \uc9c0\uc5ed",
  hourLabel: "\uc2dc\uc8fc \uc0c1\ud0dc",
  modeLabel: "\uc751\ub2f5 \ubaa8\ub4dc",
  hourEnabled: "\uc815\uc0c1 \ubc18\uc601",
  hourLimited: "\uc81c\ud55c\ub428",
  strengths: "\uac15\uc810",
  cautions: "\uc8fc\uc758 \ud3ec\uc778\ud2b8",
  love: "\uc5f0\uc560 \ud750\ub984",
  career: "\uc9c1\uc5c5 \ud750\ub984",
  wealth: "\uae08\uc804 \ud750\ub984",
  action: "\ud589\ub3d9 \uc870\uc5b8",
  limitations: "\uc81c\ud55c \uc0ac\ud56d",
  evidence: "\uadfc\uac70 \ub370\uc774\ud130",
  devTitle: "\uac1c\ubc1c\uc790 \uac80\uc99d \ud654\uba74",
  devLead: "\ud30c\uc774\ud504\ub77c\uc778 \ub2e8\uacc4, \uc2dc\uc2a4\ud15c \uc0c1\ud0dc, \ub514\ubc84\uadf8 trace\ub97c \ud655\uc778\ud569\ub2c8\ub2e4.",
  pipeline: "\ud30c\uc774\ud504\ub77c\uc778 \ub2e8\uacc4",
  system: "\uc2dc\uc2a4\ud15c \uc0c1\ud0dc",
  checkpoints: "\uccb4\ud06c\ud3ec\uc778\ud2b8",
  requestEcho: "\uc694\uccad echo",
  fallback: "\uc694\uccad \uc911 \ubb38\uc81c\uac00 \ubc1c\uc0dd\ud588\uc2b5\ub2c8\ub2e4.",
  no: "\uc5c6\uc74c",
  stage: {
    input_validation: "\uc785\ub825 \uac80\uc99d",
    region_resolution: "\uc9c0\uc5ed \ud574\uc11d",
    time_correction: "\uc2dc\uac04 \ubcf4\uc815",
    calendar_normalization: "\ub2ec\ub825 \uc815\uaddc\ud654",
    saju_calculation: "\uc0ac\uc8fc \uacc4\uc0b0",
    analysis_engine: "\ubd84\uc11d \uc5d4\uc9c4",
    llm_formatting: "\ubb38\uc7a5\ud654",
  },
  state: {
    passed: "\uc644\ub8cc",
    failed: "\uc2e4\ud328",
    skipped: "\ub300\uae30",
    disabled: "\ube44\ud65c\uc131",
    ready: "\uc900\ube44\ub428",
    coming_soon: "\uc900\ube44 \uc911",
  },
  evidenceLabel: {
    elements: "\uc624\ud589",
    ten_gods: "\uc2ed\uc131",
    luck_cycles: "\ub300\uc6b4",
  },
};

const en = {
  brand: "Sayu Myeongri",
  badge: "AI saju reading",
  service: "Service",
  dev: "Developer",
  language: "Language",
  online: "Backend connected",
  offline: "Waiting for backend",
  heroEyebrow: "Calculation-first reading",
  heroTitle: "Service view and developer view are separated.",
  heroText: "The main screen focuses on end users, and the developer screen keeps pipeline and debug details apart.",
  formTitle: "Enter the birth details",
  formLead: "Review the current saju calculation flow using region, time, and calendar input.",
  calendarType: "Calendar type",
  solar: "Solar",
  lunar: "Lunar",
  birthDate: "Birth date",
  birthTime: "Birth time",
  estimatedTime: "Birth time is estimated",
  leapMonth: "This is a leap lunar month",
  gender: "Gender",
  female: "Female",
  male: "Male",
  region: "Birth region",
  regionPlaceholder: "Type a region to get suggestions",
  regionValidation: "Choose one region from the suggestion list.",
  selectedRegion: "Selected region",
  noRegion: "Not selected yet.",
  advanced: "Advanced options",
  debug: "Include debug trace",
  submit: "Show result",
  submitting: "Calculating...",
  resultTitle: "Your baseline saju reading",
  resultEmpty: "Complete the form to see the summary and evidence data.",
  regionLabel: "Region",
  hourLabel: "Hour pillar",
  modeLabel: "Mode",
  hourEnabled: "Enabled",
  hourLimited: "Limited",
  strengths: "Strengths",
  cautions: "Cautions",
  love: "Love",
  career: "Career",
  wealth: "Wealth",
  action: "Action advice",
  limitations: "Limitations",
  evidence: "Evidence",
  devTitle: "Developer verification view",
  devLead: "Review pipeline stages, system state, and debug trace here.",
  pipeline: "Pipeline stages",
  system: "System status",
  checkpoints: "Checkpoints",
  requestEcho: "Request echo",
  fallback: "Something went wrong.",
  no: "None",
  stage: {
    input_validation: "Input validation",
    region_resolution: "Region resolution",
    time_correction: "Time correction",
    calendar_normalization: "Calendar normalization",
    saju_calculation: "Saju calculation",
    analysis_engine: "Analysis engine",
    llm_formatting: "LLM formatting",
  },
  state: {
    passed: "Passed",
    failed: "Failed",
    skipped: "Pending",
    disabled: "Disabled",
    ready: "Ready",
    coming_soon: "Planned",
  },
  evidenceLabel: {
    elements: "Five Elements",
    ten_gods: "Ten Gods",
    luck_cycles: "Luck Cycles",
  },
};

function t(locale: Locale) {
  return locale === "ko" ? ko : en;
}

function getMode(pathname: string): Mode {
  return pathname.startsWith("/dev") ? "dev" : "service";
}

export default function App() {
  const [locale, setLocale] = useState<Locale>("ko");
  const [mode, setMode] = useState<Mode>(() => getMode(window.location.pathname));
  const [calendarType, setCalendarType] = useState<"solar" | "lunar">("solar");
  const [birthDate, setBirthDate] = useState("1994-10-13");
  const [birthTime, setBirthTime] = useState("08:30");
  const [isBirthTimeEstimated, setIsBirthTimeEstimated] = useState(false);
  const [isLunarLeapMonth, setIsLunarLeapMonth] = useState(false);
  const [gender, setGender] = useState<"male" | "female">("female");
  const [regionQuery, setRegionQuery] = useState("Seoul");
  const [selectedRegion, setSelectedRegion] = useState<RegionSuggestion | null>(null);
  const [regionOptions, setRegionOptions] = useState<RegionSuggestion[]>([]);
  const [debug, setDebug] = useState(true);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SajuPreviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [apiHealth, setApiHealth] = useState<ApiHealth | null>(null);
  const copy = t(locale);

  useEffect(() => {
    const onPopState = () => setMode(getMode(window.location.pathname));
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    async function loadHealth() {
      const response = await fetch(`${API_BASE_URL}/health`);
      if (!response.ok) throw new Error("health");
      setApiHealth((await response.json()) as ApiHealth);
    }
    void loadHealth().catch(() => setApiHealth(null));
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function loadRegions() {
      try {
        const items = await searchRegionSuggestions(regionQuery);
        if (cancelled) return;
        setRegionOptions(items);
        if (!selectedRegion && items.length > 0) setSelectedRegion(items[0]);
      } catch (_error) {
        if (!cancelled) setRegionOptions([]);
      }
    }
    void loadRegions();
    return () => {
      cancelled = true;
    };
  }, [regionQuery, selectedRegion]);

  function navigate(nextMode: Mode) {
    window.history.pushState({}, "", nextMode === "dev" ? "/dev" : "/");
    setMode(nextMode);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedRegion) {
      setError(copy.regionValidation);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await createSajuPreview(
        {
          calendar_type: calendarType,
          birth_date: birthDate,
          birth_time: birthTime,
          is_birth_time_estimated: isBirthTimeEstimated,
          is_lunar_leap_month: isLunarLeapMonth,
          gender,
          region_id: selectedRegion.id,
          debug,
        },
        debug,
      );
      setResult(data);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : copy.fallback);
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-shell">
      <main className="app-frame">
        <header className="topbar">
          <div className="brand-block">
            <span className="brand-mark">命</span>
            <div>
              <p className="nav-badge">{copy.badge}</p>
              <h1 className="brand-name">{copy.brand}</h1>
            </div>
          </div>
          <div className="topbar-actions">
            <div className="view-switch">
              <button className={`switch-button${mode === "service" ? " active" : ""}`} type="button" onClick={() => navigate("service")}>{copy.service}</button>
              <button className={`switch-button${mode === "dev" ? " active" : ""}`} type="button" onClick={() => navigate("dev")}>{copy.dev}</button>
            </div>
            <label className="language-picker">
              <span>{copy.language}</span>
              <select value={locale} onChange={(event) => setLocale(event.target.value as Locale)}>
                <option value="ko">한국어</option>
                <option value="en">English</option>
              </select>
            </label>
          </div>
        </header>

        <section className="hero-panel">
          <div className="hero-copy">
            <p className="eyebrow">{copy.heroEyebrow}</p>
            <h2>{copy.heroTitle}</h2>
            <p>{copy.heroText}</p>
          </div>
          <div className="hero-side">
            <div className="live-status">
              <span className={`status-dot${apiHealth ? " online" : ""}`} />
              <strong>{apiHealth ? copy.online : copy.offline}</strong>
            </div>
          </div>
        </section>

        <section className="main-grid">
          <article className="panel-card input-panel">
            <div className="panel-head">
              <p className="section-label">{copy.service}</p>
              <h3>{copy.formTitle}</h3>
              <p>{copy.formLead}</p>
            </div>
            <form className="saju-form" onSubmit={handleSubmit}>
              <div className="field-group">
                <span className="field-label">{copy.calendarType}</span>
                <div className="segment-row">
                  <button className={`segment-button${calendarType === "solar" ? " active" : ""}`} type="button" onClick={() => setCalendarType("solar")}>{copy.solar}</button>
                  <button className={`segment-button${calendarType === "lunar" ? " active" : ""}`} type="button" onClick={() => setCalendarType("lunar")}>{copy.lunar}</button>
                </div>
              </div>
              <div className="field-row">
                <label className="field-block"><span className="field-label">{copy.birthDate}</span><input type="date" value={birthDate} onChange={(event) => setBirthDate(event.target.value)} /></label>
                <label className="field-block"><span className="field-label">{copy.birthTime}</span><input type="time" value={birthTime} onChange={(event) => setBirthTime(event.target.value)} /></label>
              </div>
              <div className="field-row compact">
                <label className="toggle-row"><input type="checkbox" checked={isBirthTimeEstimated} onChange={(event) => setIsBirthTimeEstimated(event.target.checked)} /><span>{copy.estimatedTime}</span></label>
                {calendarType === "lunar" ? <label className="toggle-row"><input type="checkbox" checked={isLunarLeapMonth} onChange={(event) => setIsLunarLeapMonth(event.target.checked)} /><span>{copy.leapMonth}</span></label> : null}
              </div>
              <div className="field-group">
                <span className="field-label">{copy.gender}</span>
                <div className="segment-row">
                  <button className={`segment-button${gender === "female" ? " active" : ""}`} type="button" onClick={() => setGender("female")}>{copy.female}</button>
                  <button className={`segment-button${gender === "male" ? " active" : ""}`} type="button" onClick={() => setGender("male")}>{copy.male}</button>
                </div>
              </div>
              <div className="field-group">
                <label className="field-block"><span className="field-label">{copy.region}</span><input value={regionQuery} onChange={(event) => { setRegionQuery(event.target.value); setSelectedRegion(null); }} placeholder={copy.regionPlaceholder} /></label>
                <div className="suggestion-list">
                  {regionOptions.map((item) => (
                    <button className={`suggestion-item${selectedRegion?.id === item.id ? " selected" : ""}`} type="button" key={item.id} onClick={() => { setSelectedRegion(item); setRegionQuery(item.display_name); }}>
                      <strong>{item.display_name}</strong>
                      <span>{item.tzid}</span>
                    </button>
                  ))}
                </div>
                <div className="selected-region-card"><span>{copy.selectedRegion}</span><strong>{selectedRegion ? selectedRegion.display_name : copy.noRegion}</strong></div>
              </div>
              <details className="advanced-box">
                <summary>{copy.advanced}</summary>
                <label className="toggle-row compact-toggle"><input type="checkbox" checked={debug} onChange={(event) => setDebug(event.target.checked)} /><span>{copy.debug}</span></label>
              </details>
              <button className="primary-button" type="submit" disabled={loading}>{loading ? copy.submitting : copy.submit}</button>
            </form>
            {error ? <p className="error-message">{error}</p> : null}
          </article>

          <div className="result-column">
            {mode === "service" ? (
              <article className="panel-card summary-panel">
                <div className="panel-head">
                  <p className="section-label">{copy.resultTitle}</p>
                  <h3>{copy.resultTitle}</h3>
                  <p>{result ? result.result.overview : copy.resultEmpty}</p>
                </div>
                {result ? (
                  <>
                    <div className="summary-chip-row">
                      <div className="summary-chip"><span>{copy.regionLabel}</span><strong>{result.region.display_name}</strong></div>
                      <div className="summary-chip"><span>{copy.hourLabel}</span><strong>{result.result.hour_pillar_enabled ? copy.hourEnabled : copy.hourLimited}</strong></div>
                      <div className="summary-chip"><span>{copy.modeLabel}</span><strong>{result.response_mode}</strong></div>
                    </div>
                    <div className="three-card-grid">
                      <article className="reading-card"><h4>{copy.strengths}</h4><ul>{result.result.strengths.map((item) => <li key={item}>{item}</li>)}</ul></article>
                      <article className="reading-card"><h4>{copy.cautions}</h4><ul>{result.result.cautions.map((item) => <li key={item}>{item}</li>)}</ul></article>
                      <article className="reading-card"><h4>{copy.limitations}</h4>{result.result.limitations.length ? <ul>{result.result.limitations.map((item) => <li key={item}>{item}</li>)}</ul> : <p>{copy.no}</p>}</article>
                    </div>
                    <div className="three-card-grid">
                      <article className="reading-card"><h4>{copy.love}</h4><p>{result.result.love}</p></article>
                      <article className="reading-card"><h4>{copy.career}</h4><p>{result.result.career}</p></article>
                      <article className="reading-card"><h4>{copy.wealth}</h4><p>{result.result.wealth}</p></article>
                    </div>
                    <article className="reading-card wide"><h4>{copy.action}</h4><p>{result.result.action_advice}</p></article>
                    <article className="panel-card inner-panel">
                      <div className="panel-head"><p className="section-label">{copy.evidence}</p><h3>{copy.evidence}</h3></div>
                      <div className="evidence-stack">
                        {Object.entries(result.result.evidence_sections).map(([key, value]) => (
                          <details className="evidence-card" key={key}>
                            <summary>
                              <span>{copy.evidenceLabel[key as keyof typeof copy.evidenceLabel] ?? value.title}</span>
                              <strong className={`stage-badge stage-${value.status}`}>{copy.state[value.status as keyof typeof copy.state] ?? value.status}</strong>
                            </summary>
                            <p>{value.summary}</p>
                          </details>
                        ))}
                      </div>
                    </article>
                  </>
                ) : <div className="empty-state-card"><p>{copy.resultEmpty}</p></div>}
              </article>
            ) : (
              <>
                <article className="panel-card">
                  <div className="panel-head">
                    <p className="section-label">{copy.devTitle}</p>
                    <h3>{copy.devTitle}</h3>
                    <p>{copy.devLead}</p>
                  </div>
                </article>
                <div className="side-grid">
                  <article className="panel-card">
                    <div className="panel-head"><p className="section-label">{copy.system}</p><h3>{copy.system}</h3></div>
                    {apiHealth ? <div className="status-card"><strong>{apiHealth.service} {apiHealth.version}</strong><p>{apiHealth.message}</p><div className="status-chip-row">{apiHealth.focus.map((item) => <span className="soft-pill" key={item}>{item}</span>)}</div></div> : <div className="status-card"><p>{copy.offline}</p></div>}
                  </article>
                  <article className="panel-card">
                    <div className="panel-head"><p className="section-label">{copy.pipeline}</p><h3>{copy.pipeline}</h3></div>
                    {result ? <div className="timeline-list">{Object.entries(result.pipeline_status).map(([key, value]) => <div className="timeline-item" key={key}><span>{copy.stage[key as keyof typeof copy.stage] ?? key}</span><strong className={`stage-badge stage-${value}`}>{copy.state[value as keyof typeof copy.state] ?? value}</strong></div>)}</div> : <div className="empty-state-card"><p>{copy.resultEmpty}</p></div>}
                  </article>
                </div>
                {result?.debug_trace ? (
                  <article className="panel-card">
                    <div className="panel-head"><p className="section-label">{copy.checkpoints}</p><h3>{copy.checkpoints}</h3></div>
                    <div className="debug-grid">
                      <div className="timeline-list">
                        {result.debug_trace.checkpoints.map((checkpoint) => (
                          <div className="timeline-item block" key={checkpoint.stage}>
                            <div><span>{copy.stage[checkpoint.stage as keyof typeof copy.stage] ?? checkpoint.stage}</span>{checkpoint.note ? <p>{checkpoint.note}</p> : null}</div>
                            <strong className={`stage-badge stage-${checkpoint.status}`}>{copy.state[checkpoint.status as keyof typeof copy.state] ?? checkpoint.status}</strong>
                          </div>
                        ))}
                      </div>
                      <pre className="debug-panel">{JSON.stringify(result.debug_trace.request_echo, null, 2)}</pre>
                    </div>
                  </article>
                ) : null}
              </>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
