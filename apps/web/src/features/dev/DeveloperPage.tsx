import { ApiHealth, SajuPreviewResponse } from "../../shared/api/contracts";
import { Locale, getCopy } from "../../shared/copy";

type DeveloperPageProps = {
  locale: Locale;
  onLocaleChange: (locale: Locale) => void;
  apiHealth: ApiHealth | null;
  result: SajuPreviewResponse | null;
  onNavigateToService: () => void;
};

export function DeveloperPage({
  locale,
  onLocaleChange,
  apiHealth,
  result,
  onNavigateToService,
}: DeveloperPageProps) {
  const texts = getCopy(locale);

  return (
    <main className="dev-container">
      <header className="dev-header">
        <button className="dev-link-button" type="button" onClick={onNavigateToService}>
          {texts.backToService}
        </button>
        <label className="locale-select">
          <span>{texts.language}</span>
          <select value={locale} onChange={(event) => onLocaleChange(event.target.value as Locale)}>
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
      ) : (
        <section className="dev-section">
          <p>{texts.noDebugData}</p>
        </section>
      )}
    </main>
  );
}
