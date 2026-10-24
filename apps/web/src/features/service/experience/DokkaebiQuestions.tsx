import { useEffect, useRef, useState } from "react";
import type { SajuPreviewRequest } from "../../../shared/api/contracts";
import type { SajuBasicResponse, SajuQuestionResponse } from "../../../shared/api/questionContracts";
import { createSajuQuestion } from "../../../shared/api/saju";
import type { Locale } from "../../../shared/copy";
import type { DokkaebiExpression } from "../../character/dokkaebiCatalog";
import { DokkaebiSticker } from "../../character/DokkaebiSticker";
import { formatManseText } from "../../shared/manseDisplay";
import { DokkaebiShareDialog } from "./DokkaebiShareDialog";
import { DokkaebiBasicReading } from "./DokkaebiBasicReading";
import { DokkaebiManseSheet } from "./DokkaebiManseSheet";
import { CategoryQuestions, DokkaebiCategoryReading, ReadingProse } from "./DokkaebiCategoryReading";
import { experienceCopy } from "./experienceCopy";
import { getReadingNotices } from "./readingNotices";
import { matchesQuestionResponse, questionShareContent } from "./questionModel";

type Props = {
  locale: Locale;
  result: SajuBasicResponse;
  input: SajuPreviewRequest | null;
  expression: DokkaebiExpression;
  onExpressionChange: (expression: DokkaebiExpression) => void;
  questionId: string | null;
  onQuestionChange: (id: string | null) => void;
  onEdit: () => void;
};

const copy = {
  ko: {
    basic: "내 사주팔자",
    questionList: "뭐가 궁금해?", back: "기본 사주로", loading: "이 질문의 계산값을 확인하고 있어.",
    retry: "다시 확인하기", share: "이 답으로 카드 만들기", next: "다음은 뭐가 궁금해?",
    noQuestions: "지금 입력으로 확인할 수 있는 질문이 없어. 출생 정보를 확인해줘.",
    missingInput: "출생 정보를 다시 확인해줘.", changed: "풀이 기준이 바뀌었어. 출생 정보에서 다시 시작해줘.",
    unknownHour: "출생시간 미상 · 시주와 대운 질문은 제외했어.",
    labels: { year: "년주", month: "월주", day: "일주", time: "시주" },
  },
  en: {
    basic: "My birth chart",
    questionList: "What are you curious about?", back: "Back to my chart", loading: "Checking the calculated facts for this question.",
    retry: "Try again", share: "Make a card with this answer", next: "What would you like to explore next?",
    noQuestions: "No questions are available for this input. Please check your birth details.",
    missingInput: "Please check your birth details again.", changed: "The reading rules changed. Please start again with your birth details.",
    unknownHour: "Birth time unknown · hour pillar and luck-cycle questions are excluded.",
    labels: { year: "Year", month: "Month", day: "Day", time: "Hour" },
  },
};

export function DokkaebiQuestions({ locale, result, input, expression, onExpressionChange, questionId, onQuestionChange, onEdit }: Props) {
  const text = copy[locale];
  const [answer, setAnswer] = useState<SajuQuestionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [sharing, setSharing] = useState(false);
  const [showManse, setShowManse] = useState(false);
  const answerHeading = useRef<HTMLHeadingElement>(null);
  const returnCategory = useRef<string | null>(null);
  const active = result.question_flow.questions.find((question) => question.id === questionId);
  const currentAnswer = answer?.question_id === questionId ? answer : null;
  const remainingQuestions = questionId ? (currentAnswer?.followups ?? []) : result.question_flow.questions;
  // The new backend already supplies its calculation/scope notices together.
  // Fall back to legacy notices only if no new notice was supplied.
  const notices = [...new Set(result.category_reading?.calculation_notices ?? result.basic_reading?.notices ?? [
    ...(result.question_flow.notices.length
      ? result.question_flow.notices
      : [...getReadingNotices(result, locale), ...(!result.manse.meta.hour_pillar_enabled ? [text.unknownHour] : [])]),
  ])];

  useEffect(() => {
    setAnswer(null);
    setError(null);
    setSharing(false);
    if (!questionId || !active) { setLoading(false); return; }
    if (!input) { setError(text.missingInput); setLoading(false); return; }
    const controller = new AbortController();
    setLoading(true);
    void createSajuQuestion(input, questionId, { signal: controller.signal })
      .then((response) => {
        if (controller.signal.aborted) return;
        if (!matchesQuestionResponse(response, questionId, result.question_flow.versions))
          throw new Error(text.changed);
        setAnswer(response);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted)
          setError(reason instanceof Error ? reason.message : text.missingInput);
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [questionId, active, input, result.question_flow.versions, attempt, text]);

  useEffect(() => {
    if (!questionId) {
      if (returnCategory.current) {
        const heading = document.getElementById(`reading-${returnCategory.current}`)?.querySelector("h2");
        heading?.focus({ preventScroll: true });
        heading?.scrollIntoView({ block: "start", behavior: "auto" });
      }
      return;
    }
    returnCategory.current = active?.category ?? null;
    answerHeading.current?.focus({ preventScroll: true });
    answerHeading.current?.scrollIntoView({ block: "start", behavior: "auto" });
  }, [questionId, active?.category]);

  return (
    <div className="dk-question-flow" data-overflow-audit-root>
      {!questionId ? (
        <>
          <section className="dk-basic-hero">
            <div className="dk-basic-heading"><h1>{text.basic}</h1>
              <button type="button" className="dk-manse-trigger" aria-haspopup="dialog" aria-expanded={showManse} onClick={() => setShowManse(true)}>{locale === "ko" ? "만세력 보기" : "View birth chart"}<span aria-hidden="true">↗</span></button>
            </div>
            <DokkaebiSticker expression="shrug" decorative size={88} />
          </section>
          <section className="dk-basic-chart" aria-label={locale === "ko" ? "사주팔자" : "Four pillars"}>
            <div className="dk-basic-pillars">
              {result.manse.meta.pillar_order.map((key) => {
                const pillar = result.manse.pillars[key];
                return <div key={key}>
                  <span>{text.labels[key]}</span>
                  <strong>{pillar.enabled ? pillar.gan_zhi : "—"}</strong>
                  {pillar.enabled ? <small className="dk-pillar-reading" lang={locale}>{formatManseText(pillar.gan_zhi, locale)}</small> : null}
                </div>;
              })}
            </div>
          </section>
          {result.category_reading ? <DokkaebiCategoryReading result={result} locale={locale} notices={notices} onSelect={onQuestionChange} />
            : result.basic_reading ? <DokkaebiBasicReading reading={result.basic_reading} locale={locale} notices={notices} /> : null}
        </>
      ) : (
        <section className="dk-question-answer" aria-busy={loading}>
          <button className="dk-text-button" onClick={() => onQuestionChange(null)}>← {text.back}</button>
          <div className="dk-question-answer-heading">
            <h1 ref={answerHeading} tabIndex={-1}>{active?.title}</h1>
            <DokkaebiSticker expression={loading ? "smirk" : expression} decorative size={76} />
          </div>
          {loading ? <p className="dk-question-loading" role="status">{text.loading}</p> : null}
          {error ? <div role="alert"><p>{error}</p><button className="dk-secondary" onClick={error === text.changed ? onEdit : () => setAttempt((value) => value + 1)}>{error === text.changed ? experienceCopy[locale].edit : text.retry}</button></div> : null}
          {!loading && currentAnswer ? (
            <div key={currentAnswer.trace_id} data-question-id={currentAnswer.question_id}>
              <p className="dk-small-note">{locale === "ko" ? "계산 기준일" : "Calculated as of"} · {currentAnswer.as_of.slice(0, 10)}</p>
              <div className="dk-question-takeaway"><ReadingProse body={currentAnswer.answer} /></div>
              {currentAnswer.sections.filter((section) => section.kind === "reading").map((section) => (
                <section className="dk-question-explanation" key={section.id}>
                  <h2>{section.title}</h2><ReadingProse body={section.text} />
                </section>
              ))}
              <details className="dk-reading-basis">
                <summary className="dk-basis-heading">{experienceCopy[locale].readingMemo}<span aria-hidden="true">⌄</span></summary>
                <div className="dk-basis-content">
                  {currentAnswer.notices.map((notice) => <p key={notice}>{notice}</p>)}
                  <p>{currentAnswer.memo.reading}</p><ul>{currentAnswer.memo.facts.map((fact) => <li key={fact}>{fact}</li>)}</ul>
                  {currentAnswer.sections.filter((section) => section.kind !== "reading").map((section) => <section className="dk-memo-section" key={section.id}><h3>{section.title}</h3><p>{section.text}</p></section>)}
                </div>
              </details>
              <button className="dk-primary dk-question-share" onClick={() => setSharing(true)}>{text.share}</button>
            </div>
          ) : null}
        </section>
      )}
      {(!result.category_reading || (questionId && remainingQuestions.length > 0)) ? <section className="dk-question-list" aria-labelledby="dk-question-list-heading">
        <h2 id="dk-question-list-heading">{questionId ? text.next : text.questionList}</h2>
        <CategoryQuestions questions={remainingQuestions} onSelect={onQuestionChange} />
        {!result.question_flow.questions.length ? <p>{text.noQuestions}</p> : null}
      </section> : null}
      <button className="dk-text-button dk-question-edit" onClick={onEdit}>{experienceCopy[locale].edit}</button>
      {sharing && currentAnswer ? <DokkaebiShareDialog locale={locale} content={questionShareContent(currentAnswer, locale)} topicKey={currentAnswer.question_id} expression={expression} onExpressionChange={onExpressionChange} onClose={() => setSharing(false)} /> : null}
      {showManse ? <DokkaebiManseSheet result={result} input={input} locale={locale} notices={notices} onClose={() => setShowManse(false)} /> : null}
    </div>
  );
}
