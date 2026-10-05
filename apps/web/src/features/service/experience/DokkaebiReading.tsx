import { useRef, useState, type KeyboardEvent } from "react";
import type {
  SajuPreviewRequest,
  SajuPreviewResponse,
} from "../../../shared/api/contracts";
import type { Locale } from "../../../shared/copy";
import { DokkaebiSticker } from "../../character/DokkaebiSticker";
import type { DokkaebiExpression } from "../../character/dokkaebiCatalog";
import { PeriodFlowCards } from "../components/PeriodFlowCards";
import { SajuResultView } from "../components/SajuResultView";
import { DokkaebiShareDialog } from "./DokkaebiShareDialog";
import { DokkaebiReadingBasis } from "./DokkaebiReadingBasis";
import {
  experienceCopy,
  readingTopics,
  type ReadingTopicKey,
} from "./experienceCopy";
import { getReadingCard, getReadingHeadline } from "./readingModel";
import { getPrimaryReadingNotice, getReadingNotices, getShareLimitation } from "./readingNotices";

type Props = {
  locale: Locale;
  result: SajuPreviewResponse;
  detailPayload: SajuPreviewRequest | null;
  expression: DokkaebiExpression;
  onExpressionChange: (expression: DokkaebiExpression) => void;
  onEdit: () => void;
  topicKey: ReadingTopicKey;
  onTopicChange: (topic: ReadingTopicKey) => void;
};

export function DokkaebiReading({
  locale,
  result,
  detailPayload,
  expression,
  onExpressionChange,
  onEdit,
  topicKey,
  onTopicChange,
}: Props) {
  const copy = experienceCopy[locale];
  const [sharing, setSharing] = useState(false);
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const topic = readingTopics.find((item) => item.key === topicKey)!;
  const card = getReadingCard(result, topicKey, locale);
  const overview = result.result.free_preview?.hero_overview ?? [
    result.result.overview,
  ];
  const headline =
    topicKey === "core"
      ? card?.reading_structure?.question ?? getReadingHeadline(result)
      : card?.subtitle || card?.title || topic.label[locale];
  const warnings = [
    ...new Set([
      ...(result.result.free_preview?.warnings ?? []).filter((warning) => !/^[a-z][a-z0-9_]*$/i.test(warning)),
      ...result.result.limitations,
      ...(topicKey === "today" ? result.period_flows.today.notes : []),
      ...getReadingNotices(result, locale),
    ]),
  ];
  const primaryNotice = getPrimaryReadingNotice(result, locale);
  const shareLimitation = getShareLimitation(result, locale);

  function selectTopic(key: ReadingTopicKey) {
    onTopicChange(key);
  }
  function handleTabKeys(
    event: KeyboardEvent<HTMLButtonElement>,
    index: number,
  ) {
    const offsets = { ArrowRight: 1, ArrowLeft: -1 };
    let next: number;
    if (event.key === "Home") next = 0;
    else if (event.key === "End") next = readingTopics.length - 1;
    else if (event.key === "ArrowRight" || event.key === "ArrowLeft")
      next =
        (index + offsets[event.key] + readingTopics.length) %
        readingTopics.length;
    else return;
    event.preventDefault();
    selectTopic(readingTopics[next].key);
    tabRefs.current[next]?.focus();
  }

  return (
    <div className="dk-reading" data-overflow-audit-root>
      <section className="dk-reading-hero">
        <div>
          <p className="dk-reading-context">
            {topic.label[locale]}
            {card?.periodLabel ? ` · ${card.periodLabel}` : ""}
          </p>
          <h1>{headline}</h1>
        </div>
        <DokkaebiSticker expression={expression} decorative size={124} />
        {topicKey === "core" ? (
          <div className="dk-overview">
            {overview.map((paragraph, index) => (
              <p key={index}>{paragraph}</p>
            ))}
          </div>
        ) : null}
      </section>
      {primaryNotice || !result.result.hour_pillar_enabled ? (
        <aside className="dk-reading-uncertainty" aria-label={copy.notes}>
          {!result.result.hour_pillar_enabled ? <p>{copy.unknownResult}</p> : null}
          {primaryNotice ? <p>{primaryNotice}</p> : null}
        </aside>
      ) : null}
      <nav className="dk-topic-tabs" role="tablist" aria-label={copy.topicNav}>
        {readingTopics.map((item, index) => (
          <button
            role="tab"
            id={`dk-tab-${item.key}`}
            aria-controls="dk-reading-panel"
            aria-selected={item.key === topicKey}
            tabIndex={item.key === topicKey ? 0 : -1}
            ref={(element) => {
              tabRefs.current[index] = element;
            }}
            key={item.key}
            onClick={() => selectTopic(item.key)}
            onKeyDown={(event) => handleTabKeys(event, index)}
          >
            {item.label[locale]}
          </button>
        ))}
      </nav>
      <section
        className="dk-reading-panel"
        id="dk-reading-panel"
        role="tabpanel"
        aria-labelledby={`dk-tab-${topicKey}`}
        tabIndex={0}
      >
        {card ? (
          <>
            <div className="dk-topic-heading">
              <div>
                <h2>
                  {topicKey === "today"
                    ? copy.todayTakeaway
                    : topic.label[locale]}
                </h2>
              </div>
              <DokkaebiSticker
                expression={topic.expression}
                decorative
                size={82}
              />
            </div>
            {card.user_takeaway ? (
              <div className="dk-takeaway">
                <p>{card.user_takeaway}</p>
              </div>
            ) : null}
            {card.chips.length ? (
              <div className="dk-reading-tags">
                {card.chips.map((chip) => (
                  <span key={chip}>{chip}</span>
                ))}
              </div>
            ) : null}
            <div className="dk-topic-body">
              {card.preview_paragraphs.map((paragraph, index) => (
                <p
                  key={index}
                  data-reading-role={card.reading_structure?.blocks[index + 1]?.role}
                >{paragraph}</p>
              ))}
            </div>
            <DokkaebiReadingBasis
              key={`${result.trace_id}:${topicKey}`}
              card={card}
              locale={locale}
            />
          </>
        ) : (
          <p>{copy.empty}</p>
        )}
      </section>
      <div className="dk-reading-extras">
        <details className="dk-period-details">
          <summary>
            {copy.periodMore}
            <span aria-hidden="true">＋</span>
          </summary>
          <PeriodFlowCards
            locale={locale}
            flows={result.period_flows}
            showMonthWindow
          />
        </details>
        <div className="dk-deep-reading">
          <SajuResultView
            locale={locale}
            result={result}
            detailPayload={detailPayload}
            onReset={onEdit}
            readingOnly
          />
        </div>
        {warnings.length ? (
          <details className="dk-notes">
            <summary>{copy.notes}</summary>
            {warnings.map((warning, index) => (
              <p key={index}>{warning}</p>
            ))}
          </details>
        ) : null}
        <button className="dk-text-button dk-edit-button" onClick={onEdit}>
          {copy.edit} <span aria-hidden="true">↶</span>
        </button>
      </div>
      <div className="dk-result-action-bar">
        <button
          className="dk-primary"
          disabled={!card}
          onClick={() => setSharing(true)}
        >
          {copy.share}
          <span aria-hidden="true">↑</span>
        </button>
      </div>
      {sharing && card ? (
        <DokkaebiShareDialog
          locale={locale}
          topicKey={topicKey}
          content={{
            topic: topic.label[locale],
            title: headline,
            takeaway: card.user_takeaway,
            periodLabel: card.periodLabel,
            limitation: shareLimitation,
          }}
          expression={expression}
          onExpressionChange={onExpressionChange}
          onClose={() => setSharing(false)}
        />
      ) : null}
    </div>
  );
}
