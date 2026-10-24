import type { Locale } from "../../../shared/copy";
import { experienceCopy } from "./experienceCopy";
import { getReadingBasis } from "./readingBasis";
import type { ReadingCard } from "./readingModel";

export function DokkaebiReadingBasis({
  card,
  locale,
}: {
  card: ReadingCard;
  locale: Locale;
}) {
  const copy = experienceCopy[locale];
  const basis = getReadingBasis(card);
  if (!basis) return null;

  return (
    <details className="dk-reading-basis">
      <summary className="dk-basis-heading">
        {copy.readingMemo}
        <svg className="dk-basis-chevron" viewBox="0 0 12 12" aria-hidden="true">
          <path d="m3 4.5 3 3 3-3" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </summary>
      <div className="dk-basis-content">
        <dl>
          <div>
            <dt>{basis.reading ? copy.basisFacts : copy.basisReportedFacts}</dt>
            <dd>
              {basis.facts.map((fact) => <p key={fact}>{fact}</p>)}
            </dd>
          </div>
          {basis.reading ? (
            <div>
              <dt>{copy.basisReading}</dt>
              <dd>{basis.reading}</dd>
            </div>
          ) : null}
        </dl>
      </div>
    </details>
  );
}
