import { SajuPreviewResponse } from "../../../shared/api/contracts";
import { Locale, getCopy } from "../../../shared/copy";
import { buildResultNarrative } from "../resultNarrative";
import { ManseTestPanel } from "./ManseTestPanel";

type SajuResultViewProps = {
  locale: Locale;
  result: SajuPreviewResponse;
  onReset: () => void;
};

export function SajuResultView({ locale, result, onReset }: SajuResultViewProps) {
  const texts = getCopy(locale);
  const narrative = buildResultNarrative(locale, result);
  const visiblePillars = result.result.signals.visible_pillar_values.join(" / ");

  return (
    <section className="result-screen">
      <div className="result-header">
        <div className="result-header-copy">
          <h2>{texts.resultTitle}</h2>
          <p>{visiblePillars}</p>
        </div>
        <button className="secondary-button" type="button" onClick={onReset}>
          {texts.backToForm}
        </button>
      </div>

      <div className="result-section">
        <h3>{texts.overview}</h3>
        <p>{narrative.overview}</p>
      </div>
      <div className="result-section">
        <h3>{texts.strengths}</h3>
        <p>{narrative.strength}</p>
      </div>
      <div className="result-section">
        <h3>{texts.cautions}</h3>
        <p>{narrative.caution}</p>
      </div>
      <div className="result-section">
        <h3>{texts.love}</h3>
        <p>{narrative.love}</p>
      </div>
      <div className="result-section">
        <h3>{texts.career}</h3>
        <p>{narrative.career}</p>
      </div>
      <div className="result-section">
        <h3>{texts.wealth}</h3>
        <p>{narrative.wealth}</p>
      </div>
      <div className="result-section">
        <h3>{texts.action}</h3>
        <p>{narrative.action}</p>
      </div>

      <ManseTestPanel locale={locale} result={result} />
    </section>
  );
}
