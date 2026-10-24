import type { SajuBasicReading } from "../../../shared/api/questionContracts";
import type { Locale } from "../../../shared/copy";
import { experienceCopy } from "./experienceCopy";

export function DokkaebiBasicReading({ reading, locale, notices = [] }: { reading: SajuBasicReading; locale: Locale; notices?: string[] }) {
  const memoNotices = [...new Set([...notices, ...(reading.limitations ?? [])])];
  return (
    <section className="dk-basic-reading" aria-labelledby="dk-basic-reading-title" data-basic-reading>
      <h2 id="dk-basic-reading-title">{reading.title}</h2>
      <p className="dk-basic-reading-headline">{reading.headline}</p>
      {reading.sections.map((section) => (
        <section className="dk-basic-reading-section" key={section.id}>
          <h3>{section.title}</h3>
          {section.text.split(/\n\s*\n/).map((paragraph, index) => <p key={index}>{paragraph}</p>)}
        </section>
      ))}
      <details className="dk-reading-basis" key={reading.as_of}>
        <summary className="dk-basis-heading">{experienceCopy[locale].readingMemo}<span aria-hidden="true">⌄</span></summary>
        <div className="dk-basis-content">
          {memoNotices.map((notice) => <p key={notice}>{notice}</p>)}
          <p>{reading.memo.reading}</p>
          <ul>{reading.memo.facts.map((fact) => <li key={fact}>{fact}</li>)}</ul>
          {reading.memo_sections?.map((section) => (
            <section className="dk-memo-section" key={section.id}>
              <h4>{section.title}</h4>
              {section.text.split(/\n\s*\n/).map((paragraph, index) => <p key={index}>{paragraph}</p>)}
            </section>
          ))}
        </div>
      </details>
    </section>
  );
}
