import { Locale } from "../../../shared/copy";

type ServiceHeaderProps = {
  title: string;
  subtitle: string;
  locale: Locale;
  languageLabel: string;
  mainHomeLabel: string;
  hideIntro?: boolean;
  onLocaleChange: (locale: Locale) => void;
};

export function ServiceHeader({
  title,
  subtitle,
  locale,
  languageLabel,
  mainHomeLabel,
  hideIntro = false,
  onLocaleChange,
}: ServiceHeaderProps) {
  return (
    <header className={`service-header${hideIntro ? " is-compact" : ""}`}>
      <div className="service-header-top">
        <span className="service-mark" aria-hidden="true">
          SAJU
        </span>
        <div className="service-header-actions">
          <a className="main-home-link" href="https://my-web-desktop.vercel.app">
            {mainHomeLabel}
          </a>
          <label className="locale-select">
            <span>{languageLabel}</span>
            <select value={locale} onChange={(event) => onLocaleChange(event.target.value as Locale)}>
              <option value="ko">한국어</option>
              <option value="en">English</option>
            </select>
          </label>
        </div>
      </div>
      {hideIntro ? null : (
        <>
          <h1>{title}</h1>
          <p>{subtitle}</p>
        </>
      )}
    </header>
  );
}
