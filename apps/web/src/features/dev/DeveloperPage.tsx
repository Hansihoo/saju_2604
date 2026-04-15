import { FormEvent } from "react";

import { ApiHealth, SajuPreviewResponse } from "../../shared/api/contracts";
import { Locale } from "../../shared/copy";
import { useSajuInputForm } from "../shared/useSajuInputForm";
import { DeveloperInputPanel } from "./components/DeveloperInputPanel";
import { DeveloperManseInspector } from "./components/DeveloperManseInspector";
import { getDevCopy } from "./devCopy";

type DeveloperPageProps = {
  locale: Locale;
  onLocaleChange: (locale: Locale) => void;
  apiHealth: ApiHealth | null;
  result: SajuPreviewResponse | null;
  onResultChange: (result: SajuPreviewResponse | null) => void;
  onNavigateToService: () => void;
};

export function DeveloperPage({
  locale,
  onLocaleChange,
  apiHealth,
  result,
  onResultChange,
  onNavigateToService,
}: DeveloperPageProps) {
  const text = getDevCopy(locale);
  const form = useSajuInputForm({
    locale,
    debug: true,
    onSuccess: onResultChange,
    onErrorResult: () => onResultChange(null),
  });

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await form.submit();
  }

  return (
    <main className="dev-container">
      <header className="dev-header">
        <div className="dev-header-copy">
          <h1>{text.title}</h1>
          <p>{text.lead}</p>
        </div>
        <div className="dev-header-actions">
          <button className="dev-link-button" type="button" onClick={onNavigateToService}>
            {text.serviceLink}
          </button>
          <label className="locale-select">
            <span>{text.languageLabel}</span>
            <select value={locale} onChange={(event) => onLocaleChange(event.target.value as Locale)}>
              <option value="ko">{text.koreanOption}</option>
              <option value="en">English</option>
            </select>
          </label>
        </div>
      </header>

      <section className="dev-section dev-system-strip">
        <span>API</span>
        <strong>{apiHealth ? text.apiReady : text.apiWaiting}</strong>
      </section>

      <div className="dev-workbench">
        <DeveloperInputPanel locale={locale} form={form} onSubmit={handleSubmit} />
        <DeveloperManseInspector locale={locale} result={result} />
      </div>
    </main>
  );
}
