import type { PeriodFlow, PeriodFlows } from "../../../shared/api/contracts";
import type { Locale } from "../../../shared/copy";

type PeriodFlowCardsProps = {
  locale: Locale;
  flows: PeriodFlows;
};

const flowCopy: Record<
  Locale,
  {
    title: string;
    today: string;
    month: string;
    focus: string;
    actions: string;
  }
> = {
  ko: {
    title: "오늘과 이번 달",
    today: "오늘의 운세",
    month: "이번 달",
    focus: "집중할 것",
    actions: "이렇게 해보세요",
  },
  en: {
    title: "Today and this month",
    today: "Today's flow",
    month: "This month",
    focus: "Focus on",
    actions: "Try this",
  },
};

function PeriodFlowCard({
  flow,
  locale,
  title,
}: {
  flow: PeriodFlow;
  locale: Locale;
  title: string;
}) {
  const copy = flowCopy[locale];

  return (
    <article className={`periodFlowCard periodFlowCard-${flow.kind}`}>
      <div className="periodFlowCardTitle">
        <span className="periodFlowKind">{title}</span>
        <h4>{flow.headline}</h4>
        <p>{flow.period_label}</p>
      </div>

      <p className="periodFlowSummary">{flow.summary}</p>

      {flow.focus.length ? (
        <div className="periodFlowFocus" aria-label={copy.focus}>
          <span className="periodFlowSubLabel">{copy.focus}</span>
          <div className="periodFlowChips">
            {flow.focus.map((item) => (
              <span key={item}>{item}</span>
            ))}
          </div>
        </div>
      ) : null}

      {flow.actions.length ? (
        <div className="periodFlowActions">
          <span className="periodFlowSubLabel">{copy.actions}</span>
          <ul>
            {flow.actions.map((action) => (
              <li key={action}>{action}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </article>
  );
}

export function PeriodFlowCards({ locale, flows }: PeriodFlowCardsProps) {
  const copy = flowCopy[locale];

  return (
    <section className="periodFlowBlock" aria-labelledby="period-flow-title">
      <h3 id="period-flow-title">{copy.title}</h3>
      <div className="periodFlowGrid">
        <PeriodFlowCard flow={flows.today} locale={locale} title={copy.today} />
        <PeriodFlowCard flow={flows.month} locale={locale} title={copy.month} />
      </div>
    </section>
  );
}
