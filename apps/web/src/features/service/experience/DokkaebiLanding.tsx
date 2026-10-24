import type { Locale } from "../../../shared/copy";
import { DokkaebiSticker } from "../../character/DokkaebiSticker";
import type { DokkaebiExpression } from "../../character/dokkaebiCatalog";
import {
  includedReadingTopics,
  experienceCopy,
} from "./experienceCopy";

export function DokkaebiLanding({
  locale,
  expression,
  onStart,
}: {
  locale: Locale;
  expression: DokkaebiExpression;
  onStart: () => void;
}) {
  const copy = experienceCopy[locale];
  return (
    <section className="dk-landing-hero">
      <div className="dk-hero-character">
        <DokkaebiSticker expression={expression} locale={locale} size={164} />
      </div>
      <h1>
        {copy.heroTitle[0]}
        <br />
        <span>{copy.heroTitle[1]}</span>
      </h1>
      <div className="dk-landing-action">
        <button className="dk-primary" type="button" onClick={onStart}>
          {copy.submit}
          <span aria-hidden="true">→</span>
        </button>
        <p className="dk-included-readings" aria-label={copy.includedReadings}>
          {includedReadingTopics.map((topic) => topic.label[locale]).join(" · ")}
        </p>
      </div>
    </section>
  );
}
