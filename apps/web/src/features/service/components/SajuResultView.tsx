import { SajuPreviewResponse } from "../../../shared/api/contracts";
import { Locale, getCopy } from "../../../shared/copy";

type SajuResultViewProps = {
  locale: Locale;
  result: SajuPreviewResponse;
  onReset: () => void;
};

export function SajuResultView({ locale, result, onReset }: SajuResultViewProps) {
  const texts = getCopy(locale);

  return (
    <section className="result-screen">
      <div className="result-header">
        <h2>{texts.resultTitle}</h2>
        <button className="secondary-button" type="button" onClick={onReset}>
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
  );
}
