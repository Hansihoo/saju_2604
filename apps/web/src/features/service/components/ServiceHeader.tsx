import { Locale } from "../../../shared/copy";

type ServiceHeaderProps = {
  title: string;
  subtitle: string;
  locale: Locale;
  languageLabel: string;
  onLocaleChange: (locale: Locale) => void;
};

export function ServiceHeader({
  title,
  subtitle,
  locale,
  languageLabel,
  onLocaleChange,
}: ServiceHeaderProps) {
  return (
    <header className="service-header">
      <div className="service-header-top">
        <span className="service-icon" aria-hidden="true">
          ○
        </span>
        <label className="locale-select">
          <span>{languageLabel}</span>
          <select value={locale} onChange={(event) => onLocaleChange(event.target.value as Locale)}>
            <option value="ko">한국어</option>
            <option value="en">English</option>
          </select>
        </label>
      </div>
      <h1>{title}</h1>
      <p>{subtitle}</p>
    </header>
  );
}
