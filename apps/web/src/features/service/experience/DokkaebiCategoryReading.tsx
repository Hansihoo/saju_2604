import type { SajuBasicResponse, SajuQuestionOption } from "../../../shared/api/questionContracts";
import type { Locale } from "../../../shared/copy";
import { experienceCopy } from "./experienceCopy";
import { CharacteristicMemo, DokkaebiCharacteristics } from "./DokkaebiCharacteristics";

function InlineReading({ text }: { text: string }) {
  return <>{text.split(/(\*\*[^*]+\*\*)/g).map((part, index) => part.startsWith("**") && part.endsWith("**")
    ? <strong key={index}>{part.slice(2, -2)}</strong> : part)}</>;
}

// Render supplied Markdown as text, headings and lists. Never interpret chart data.
export function ReadingProse({ body }: { body: string }) {
  return <div className="dk-category-prose">{body.split(/\n\s*\n/).filter(Boolean).map((block, index) => {
    const lines = block.trim().split("\n");
    return <div className="dk-prose-block" key={index}>{lines.map((line, lineIndex) => {
      if (/^#{1,6}\s/.test(line)) return <h4 key={lineIndex}>{line.replace(/^#{1,6}\s+/, "")}</h4>;
      if (/^[-*]\s/.test(line)) return <p className="dk-prose-bullet" key={lineIndex}><span aria-hidden="true">· </span><InlineReading text={line.slice(2)} /></p>;
      return <p key={lineIndex}><InlineReading text={line} /></p>;
    })}</div>;
  })}</div>;
}

export function CategoryQuestions({ questions, onSelect }: { questions: SajuQuestionOption[]; onSelect: (id: string) => void }) {
  if (!questions.length) return null;
  return <div className="dk-question-options dk-category-questions">{questions.map((question) => (
    <button key={question.id} onClick={() => onSelect(question.id)}>
      <span><strong>{question.title}</strong><small>{question.description}</small></span><span aria-hidden="true">↗</span>
    </button>
  ))}</div>;
}

export function DokkaebiCategoryReading({ result, locale, notices = [], onSelect }: {
  result: SajuBasicResponse; locale: Locale; notices?: string[]; onSelect: (id: string) => void;
}) {
  if (!result.category_reading) return null;
  const reading = result.category_reading;
  const characteristics = reading.characteristics;
  const hasCharacteristics = Boolean(characteristics?.items.length);
  const sections = reading.sections.filter((section) => section.visible !== false);
  return <div className="dk-category-reading" data-category-reading>
    <nav className="dk-reading-contents" aria-label={locale === "ko" ? "풀이 목차" : "Reading contents"}>
      {sections.map((section, index) => <a href={`#reading-${section.id}`} key={section.id}><span>{String(index + 1).padStart(2, "0")}</span>{section.title}</a>)}
    </nav>
    {sections.map((section, index) => {
      // Scope and calculation details belong to the folded memo, not the reading.
      const memoNotices = [...new Set([
        ...(index === 0 ? [...notices, ...reading.notices] : []),
        ...(section.publication?.notice ? [section.publication.notice] : []),
        ...(!section.publication && section.information?.some((item) => item.provisional) && !(section.id === "core" && hasCharacteristics)
          ? [locale === "ko" ? "선택한 명식의 잠정 정보" : "Provisional information for the selected chart"] : []),
      ])];
      return (
      <section className="dk-category-section" id={`reading-${section.id}`} key={section.id} data-reading-category={section.id}>
        <span className="dk-chapter-number" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
        <h2 tabIndex={-1}>{section.title}</h2>
        {section.publication ? <>
          <div className="dk-published-reading" data-publication-version={section.publication.version}>
            {section.publication.blocks.map((block) => <div className={`dk-published-block dk-published-${block.kind}`} key={block.id} data-publication-block={block.kind}>
              {block.title ? <h3>{block.title}</h3> : null}
              {block.kind === "heading" ? <h3>{block.text}</h3> : <ReadingProse body={block.text} />}
            </div>)}
          </div>
        </> : <>
        {section.id === "core" && characteristics ? <DokkaebiCharacteristics reading={characteristics} locale={locale} /> : null}
        {section.information?.length ? <div className="dk-reading-information">{section.information.filter((item) => !(section.id === "core" && hasCharacteristics && item.id === "structure.day_month")).map((item) => (
          <div className="dk-information-item" key={item.id} data-reading-information={item.id}>
            <h3>{item.title}</h3>
            <ReadingProse body={item.body} />
          </div>
        ))}</div> : null}
        {section.status !== "blocked_calculation" && !(section.id === "core" && hasCharacteristics) ? <ReadingProse body={section.body} /> : null}
        </>}
        {result.question_flow.questions.some((question) => question.category === section.id) ? <p className="dk-related-label">{locale === "ko" ? "더 궁금하면" : "Explore further"}</p> : null}
        <CategoryQuestions questions={result.question_flow.questions.filter((question) => question.category === section.id)} onSelect={onSelect} />
        {memoNotices.length || section.publication?.memo_body || section.memo_body || (section.id === "core" && hasCharacteristics) ? <details className="dk-reading-basis" key={`${result.trace_id}-${section.id}`}>
          <summary className="dk-basis-heading">{experienceCopy[locale].readingMemo}<span aria-hidden="true">⌄</span></summary>
          <div className="dk-basis-content">
            {memoNotices.map((notice) => <p key={notice}>{notice}</p>)}
            {!section.publication && section.id === "core" && characteristics ? <CharacteristicMemo reading={characteristics} locale={locale} /> : null}
            <ReadingProse body={section.publication?.memo_body ?? section.memo_body} />
          </div>
        </details> : null}
      </section>
      );
    })}
  </div>;
}
