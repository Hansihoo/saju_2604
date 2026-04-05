import { FormEvent, useEffect, useState } from "react";

import {
  RegionSuggestion,
  SajuPreviewResponse,
  createSajuPreview,
  searchRegionSuggestions,
} from "./shared/api/saju";

type ApiHealth = {
  status: string;
  service: string;
  version: string;
  message: string;
  focus: string[];
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

const pipelineLabels: Record<string, string> = {
  input_validation: "Input validation",
  region_resolution: "Region resolution",
  time_correction: "Time correction",
  calendar_normalization: "Calendar normalization",
  saju_calculation: "Saju calculation",
  analysis_engine: "Analysis engine",
  llm_formatting: "LLM formatting",
};

export default function App() {
  const [calendarType, setCalendarType] = useState<"solar" | "lunar">("solar");
  const [birthDate, setBirthDate] = useState("1994-10-13");
  const [birthTime, setBirthTime] = useState("08:30");
  const [isBirthTimeEstimated, setIsBirthTimeEstimated] = useState(false);
  const [gender, setGender] = useState<"male" | "female">("female");
  const [regionQuery, setRegionQuery] = useState("Seoul");
  const [selectedRegion, setSelectedRegion] = useState<RegionSuggestion | null>(null);
  const [regionOptions, setRegionOptions] = useState<RegionSuggestion[]>([]);
  const [debug, setDebug] = useState(true);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SajuPreviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [apiHealth, setApiHealth] = useState<ApiHealth | null>(null);

  useEffect(() => {
    async function loadHealth() {
      const response = await fetch(`${API_BASE_URL}/health`);
      if (!response.ok) {
        throw new Error(`Health request failed with ${response.status}`);
      }
      const data = (await response.json()) as ApiHealth;
      setApiHealth(data);
    }

    void loadHealth().catch(() => {
      setApiHealth(null);
    });
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadRegions() {
      try {
        const items = await searchRegionSuggestions(regionQuery);
        if (cancelled) {
          return;
        }
        setRegionOptions(items);
        if (!selectedRegion && items.length > 0) {
          setSelectedRegion(items[0]);
        }
      } catch (_error) {
        if (!cancelled) {
          setRegionOptions([]);
        }
      }
    }

    void loadRegions();

    return () => {
      cancelled = true;
    };
  }, [regionQuery, selectedRegion]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedRegion) {
      setError("Pick one region from the suggestion list before submitting.");
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
          gender,
          region_id: selectedRegion.id,
          debug,
        },
        debug,
      );
      setResult(data);
    } catch (requestError) {
      const message =
        requestError instanceof Error
          ? requestError.message
          : "The preview request failed.";
      setError(message);
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-shell">
      <main className="layout">
        <section className="hero-card">
          <div className="hero-copy">
            <p className="eyebrow">STEP 2 BUILD</p>
            <h1>Time correction is now part of the preview pipeline.</h1>
            <p className="hero-text">
              This sprint still uses mock reading content, but the request now resolves a
              region, normalizes the local birth time, and exposes the corrected time
              context through the contract and debug trace.
            </p>
          </div>

          <div className="hero-stats">
            <div className="stat-card">
              <span>Current goal</span>
              <strong>Time correction + diagnostics</strong>
            </div>
            <div className="stat-card">
              <span>Must prove</span>
              <strong>region -> tzid -> normalized local/UTC time</strong>
            </div>
            <div className="stat-card accent">
              <span>Next big step</span>
              <strong>calendar normalization + real saju engine</strong>
            </div>
          </div>
        </section>

        <section className="workspace-grid">
          <article className="panel-card">
            <p className="section-label">INPUT CONTRACT</p>
            <h2>Mock preview request</h2>

            <form className="preview-form" onSubmit={handleSubmit}>
              <label>
                Calendar type
                <select value={calendarType} onChange={(event) => setCalendarType(event.target.value as "solar" | "lunar")}>
                  <option value="solar">Solar</option>
                  <option value="lunar">Lunar</option>
                </select>
              </label>

              <label>
                Birth date
                <input
                  type="date"
                  value={birthDate}
                  onChange={(event) => setBirthDate(event.target.value)}
                />
              </label>

              <label>
                Birth time
                <input
                  type="time"
                  value={birthTime}
                  onChange={(event) => setBirthTime(event.target.value)}
                />
              </label>

              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={isBirthTimeEstimated}
                  onChange={(event) => setIsBirthTimeEstimated(event.target.checked)}
                />
                <span>Birth time is estimated</span>
              </label>

              <label>
                Gender
                <select value={gender} onChange={(event) => setGender(event.target.value as "male" | "female")}>
                  <option value="female">Female</option>
                  <option value="male">Male</option>
                </select>
              </label>

              <label>
                Region search
                <input
                  value={regionQuery}
                  onChange={(event) => {
                    setRegionQuery(event.target.value);
                    setSelectedRegion(null);
                  }}
                  placeholder="Type a city name"
                />
              </label>

              <div className="suggestion-list">
                {regionOptions.map((item) => {
                  const selected = selectedRegion?.id === item.id;
                  return (
                    <button
                      className={`suggestion-item${selected ? " selected" : ""}`}
                      type="button"
                      key={item.id}
                      onClick={() => {
                        setSelectedRegion(item);
                        setRegionQuery(item.display_name);
                      }}
                    >
                      <strong>{item.display_name}</strong>
                      <span>{item.tzid}</span>
                    </button>
                  );
                })}
              </div>

              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={debug}
                  onChange={(event) => setDebug(event.target.checked)}
                />
                <span>Include debug trace in the response</span>
              </label>

              <button className="primary-button" type="submit" disabled={loading}>
                {loading ? "Normalizing preview..." : "Request mock preview"}
              </button>
            </form>

            {error ? <p className="error-message">{error}</p> : null}
          </article>

          <article className="panel-card">
            <p className="section-label">API STATUS</p>
            <h2>Backend readiness</h2>
            {apiHealth ? (
              <div className="status-panel">
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
              <div className="status-panel">
                <p>The backend is not reachable yet.</p>
              </div>
            )}
          </article>
        </section>

        <section className="result-grid">
          <article className="panel-card result-main">
            <p className="section-label">PREVIEW RESULT</p>
            <h2>{result ? "Mock preview response" : "No preview yet"}</h2>

            {result ? (
              <>
                <p className="trace-line">
                  trace_id: <code>{result.trace_id}</code>
                </p>
                <p>{result.result.overview}</p>

                <div className="chip-row">
                  <span className="chip">mode: {result.response_mode}</span>
                  <span className="chip">region: {result.region.display_name}</span>
                  <span className="chip">
                    hour pillar: {result.result.hour_pillar_enabled ? "enabled" : "limited"}
                  </span>
                </div>

                <div className="time-card">
                  <h3>Time correction</h3>
                  <p>Local input: {result.time_correction.source_local_datetime}</p>
                  <p>Normalized local: {result.time_correction.normalized_local_datetime}</p>
                  <p>Normalized UTC: {result.time_correction.normalized_utc_datetime}</p>
                  <div className="chip-row">
                    <span className="chip">tzid: {result.time_correction.tzid}</span>
                    <span className="chip">offset: {result.time_correction.offset_minutes} min</span>
                    <span className="chip">
                      ambiguous: {result.time_correction.ambiguous ? "yes" : "no"}
                    </span>
                    <span className="chip">fold: {result.time_correction.fold}</span>
                  </div>
                </div>

                <div className="detail-columns">
                  <div>
                    <h3>Strengths</h3>
                    <ul>
                      {result.result.strengths.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>

                  <div>
                    <h3>Cautions</h3>
                    <ul>
                      {result.result.cautions.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                </div>

                <div className="reading-grid">
                  <article className="reading-card">
                    <h3>Love</h3>
                    <p>{result.result.love}</p>
                  </article>
                  <article className="reading-card">
                    <h3>Career</h3>
                    <p>{result.result.career}</p>
                  </article>
                  <article className="reading-card">
                    <h3>Wealth</h3>
                    <p>{result.result.wealth}</p>
                  </article>
                  <article className="reading-card">
                    <h3>Action advice</h3>
                    <p>{result.result.action_advice}</p>
                  </article>
                </div>

                {result.result.limitations.length > 0 ? (
                  <div className="notice-card">
                    <h3>Limitations</h3>
                    <ul>
                      {result.result.limitations.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </>
            ) : (
              <p className="muted-copy">
                Submit the form to verify the contract, region selection, and time correction flow.
              </p>
            )}
          </article>

          <article className="panel-card">
            <p className="section-label">PIPELINE STATUS</p>
            <h2>Stage visibility</h2>

            {result ? (
              <div className="stage-list">
                {Object.entries(result.pipeline_status).map(([key, value]) => (
                  <div className="stage-item" key={key}>
                    <span>{pipelineLabels[key] ?? key}</span>
                    <strong className={`stage-badge stage-${value}`}>{value}</strong>
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted-copy">The stage map will appear here after the first request.</p>
            )}

            {result ? (
              <div className="evidence-stack">
                {Object.entries(result.result.evidence_sections).map(([key, value]) => (
                  <details className="evidence-card" key={key}>
                    <summary>
                      <span>{value.title}</span>
                      <strong className={`stage-badge stage-${value.status}`}>{value.status}</strong>
                    </summary>
                    <p>{value.summary}</p>
                  </details>
                ))}
              </div>
            ) : null}
          </article>
        </section>

        {result?.debug_trace ? (
          <section className="panel-card">
            <p className="section-label">DEBUG TRACE</p>
            <h2>Developer-only diagnostics</h2>

            <div className="debug-grid">
              <div>
                <h3>Checkpoints</h3>
                <div className="stage-list">
                  {result.debug_trace.checkpoints.map((checkpoint) => (
                    <div className="stage-item stage-item-block" key={checkpoint.stage}>
                      <div>
                        <span>{pipelineLabels[checkpoint.stage] ?? checkpoint.stage}</span>
                        {checkpoint.note ? <p>{checkpoint.note}</p> : null}
                      </div>
                      <strong className={`stage-badge stage-${checkpoint.status}`}>
                        {checkpoint.status}
                      </strong>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <h3>Request echo</h3>
                <pre className="debug-panel">
                  {JSON.stringify(result.debug_trace.request_echo, null, 2)}
                </pre>
              </div>
            </div>
          </section>
        ) : null}
      </main>
    </div>
  );
}
