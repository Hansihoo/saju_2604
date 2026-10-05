import { useId } from "react";
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
  const headingId = useId();
  const copy = experienceCopy[locale];
  const basis = getReadingBasis(card);
  if (!basis) return null;

  return (
    <aside className="dk-reading-basis" aria-labelledby={headingId}>
      <h3 className="dk-basis-heading" id={headingId}>
        {copy.analysisNote}
      </h3>
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
    </aside>
  );
}
