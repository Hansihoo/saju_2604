import type { PeriodFlow, PeriodFlows } from "../../../shared/api/contracts";
import type { Locale } from "../../../shared/copy";

type PeriodFlowCardsProps = {
  locale: Locale;
  flows: PeriodFlows;
  showMonthWindow?: boolean;
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
  periodLabel,
}: {
  flow: PeriodFlow;
  locale: Locale;
  title: string;
  periodLabel?: string;
}) {
  const copy = flowCopy[locale];

  return (
    <article className={`periodFlowCard periodFlowCard-${flow.kind}`}>
      <div className="periodFlowCardTitle">
        <span className="periodFlowKind">{title}</span>
        <h4>{flow.headline}</h4>
        <p>{periodLabel ?? flow.period_label}</p>
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

function formatMonthWindow(
  flow: PeriodFlow,
  locale: Locale,
): string | undefined {
  const formatDate = (value: string) => {
    const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
    if (!match) return undefined;
    const [, year, month, day] = match;
    if (locale === "ko") return `${Number(month)}월 ${Number(day)}일`;
    return new Intl.DateTimeFormat("en", {
      month: "short",
      day: "numeric",
      timeZone: "UTC",
    }).format(new Date(Date.UTC(Number(year), Number(month) - 1, Number(day))));
  };
  // Preserve dates already localized by the API instead of converting them in the browser's timezone.
  const start = formatDate(flow.period_start);
  const end = formatDate(flow.period_end);
  if (!start || !end) return undefined;
  return locale === "ko"
    ? `적용 기간: ${start}부터 ${end}까지`
    : `Applies from ${start} to ${end}`;
}

export function PeriodFlowCards({
  locale,
  flows,
  showMonthWindow = false,
}: PeriodFlowCardsProps) {
  const copy = flowCopy[locale];

  return (
    <section className="periodFlowBlock" aria-labelledby="period-flow-title">
      <h3 id="period-flow-title">
        {showMonthWindow
          ? locale === "ko"
            ? "오늘과 요즘의 흐름"
            : "Today and the current flow"
          : copy.title}
      </h3>
      <div className="periodFlowGrid">
        <PeriodFlowCard flow={flows.today} locale={locale} title={copy.today} />
        <PeriodFlowCard
          flow={flows.month}
          locale={locale}
          title={
            showMonthWindow
              ? locale === "ko"
                ? "지금의 월간 흐름"
                : "Current monthly flow"
              : copy.month
          }
          periodLabel={
            showMonthWindow ? formatMonthWindow(flows.month, locale) : undefined
          }
        />
      </div>
    </section>
  );
}
