import type { Locale } from "../../../shared/copy";
import { DokkaebiSticker } from "../../character/DokkaebiSticker";
import type { DokkaebiExpression } from "../../character/dokkaebiCatalog";
import {
  entryTopics,
  experienceCopy,
  type ReadingTopicKey,
} from "./experienceCopy";

export function DokkaebiLanding({
  locale,
  expression,
  onStart,
}: {
  locale: Locale;
  expression: DokkaebiExpression;
  onStart: (topic: ReadingTopicKey) => void;
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
      <div
        className="dk-entry-topics"
        role="group"
        aria-label={copy.chooseTopic}
      >
        {entryTopics.map((topic) => (
          <button
            key={topic.key}
            className={`dk-entry-topic dk-entry-topic-${topic.key}`}
            onClick={() => onStart(topic.key)}
          >
            <DokkaebiSticker
              expression={topic.expression}
              decorative
              size={64}
            />
            <strong>{topic.label[locale]}</strong>
            <b aria-hidden="true">↗</b>
          </button>
        ))}
      </div>
    </section>
  );
}
