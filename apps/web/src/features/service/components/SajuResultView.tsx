import type { ReactNode } from "react";
import {
  InterpretationNarrativeSection,
  SajuPreviewResponse,
} from "../../../shared/api/contracts";
import { Locale, getCopy } from "../../../shared/copy";
import { formatManseText } from "../../shared/manseDisplay";

type SajuResultViewProps = {
  locale: Locale;
  result: SajuPreviewResponse;
  onReset: () => void;
};

type SectionKey = "core_analysis" | "love" | "career" | "wealth" | "luck_flow";
type VisiblePillarKey = "year" | "month" | "day" | "time";

const visiblePillarKeys = ["year", "month", "day", "time"] as const;

const sectionViewCopy: Record<
  Locale,
  {
    summaryLabel: string;
    outlineLabel: string;
    basisLabel: string;
    basisItems: string[];
    sectionLabels: Record<SectionKey, string>;
  }
> = {
  ko: {
    summaryLabel: "핵심 요약",
    outlineLabel: "빠르게 보기",
    basisLabel: "이 풀이가 보는 것",
    basisItems: [
      "만세력 계산을 먼저 확인한 뒤 해석합니다.",
      "강점과 약점을 함께 보여주도록 구성했습니다.",
      "내 사주 특징, 연애운, 직장운, 금전운, 흐름 순서로 읽을 수 있습니다.",
    ],
    sectionLabels: {
      core_analysis: "내 사주 특징",
      love: "연애운",
      career: "직장운",
      wealth: "금전운",
      luck_flow: "대운 흐름",
    },
  },
  en: {
    summaryLabel: "Quick summary",
    outlineLabel: "Jump to section",
    basisLabel: "What this reading uses",
    basisItems: [
      "The manse calculation is checked before the interpretation is written.",
      "The reading is designed to show both strengths and weak points.",
      "You can read it in order: core traits, love, career, wealth, and luck flow.",
    ],
    sectionLabels: {
      core_analysis: "Core traits",
      love: "Love",
      career: "Career",
      wealth: "Wealth",
      luck_flow: "Luck flow",
    },
  },
};

const resultDataCopy: Record<
  Locale,
  {
    pillarTitle: string;
    pillarSubtitle: string;
    correctedTimeLabel: string;
    ganZhiRow: string;
    stemRow: string;
    branchRow: string;
    luckTimelineTitle: string;
    luckTimelineSubtitle: string;
    luckPillarColumn: string;
    luckStartColumn: string;
    luckChangeColumn: string;
    unavailable: string;
    pillarColumns: Record<VisiblePillarKey, string>;
  }
> = {
  ko: {
    pillarTitle: "사주팔자",
    pillarSubtitle: "만세력 기준 핵심 기둥",
    correctedTimeLabel: "보정 기준",
    ganZhiRow: "간지",
    stemRow: "천간",
    branchRow: "지지",
    luckTimelineTitle: "대운 전환 시점",
    luckTimelineSubtitle: "대운의 시작과 다음 전환 시점을 년/월 기준으로 정리했습니다.",
    luckPillarColumn: "대운",
    luckStartColumn: "시작 시점",
    luckChangeColumn: "변경 시점",
    unavailable: "-",
    pillarColumns: {
      year: "년주",
      month: "월주",
      day: "일주",
      time: "시주",
    },
  },
  en: {
    pillarTitle: "Four pillars",
    pillarSubtitle: "Core pillars from the manse data",
    correctedTimeLabel: "Corrected base",
    ganZhiRow: "Ganji",
    stemRow: "Stem",
    branchRow: "Branch",
    luckTimelineTitle: "Luck-cycle transition points",
    luckTimelineSubtitle: "Luck-cycle starts and transitions are shown by year and month.",
    luckPillarColumn: "Cycle",
    luckStartColumn: "Starts",
    luckChangeColumn: "Changes",
    unavailable: "-",
    pillarColumns: {
      year: "Year",
      month: "Month",
      day: "Day",
      time: "Time",
    },
  },
};

const disabledStateCopy: Record<
  Locale,
  {
    disabledBadge: string;
    disabledValue: string;
    unknownTimeNoticeTitle: string;
    unknownTimeNoticeBody: string;
    unknownTimeMetaLabel: string;
    unknownTimeMetaValue: string;
    timePillarDisabledNote: string;
    luckTimelineDisabledNote: string;
  }
> = {
  ko: {
    disabledBadge: "비활성화",
    disabledValue: "비활성화",
    unknownTimeNoticeTitle: "출생시간을 몰라 시주 기반 항목을 비활성화했어요.",
    unknownTimeNoticeBody:
      "시주, 시주 기반 대운, 시간 의존 해석은 숨기지 않고 비활성 상태로 표시합니다. 정확한 시간이 확인되면 다시 계산해 전체 결과를 열 수 있어요.",
    unknownTimeMetaLabel: "출생시간 상태",
    unknownTimeMetaValue: "시간 모름",
    timePillarDisabledNote: "시주는 정확한 출생시간이 확인되면 다시 열립니다.",
    luckTimelineDisabledNote: "대운 시작 시점과 흐름은 출생시간이 확인되면 다시 계산됩니다.",
  },
  en: {
    disabledBadge: "Disabled",
    disabledValue: "Disabled",
    unknownTimeNoticeTitle: "Birth time is unknown, so hour-based items are disabled.",
    unknownTimeNoticeBody:
      "The time pillar, hour-based luck-cycle details, and time-dependent interpretation stay visible in a disabled state until the real birth time is known.",
    unknownTimeMetaLabel: "Birth-time status",
    unknownTimeMetaValue: "Unknown time",
    timePillarDisabledNote: "The time pillar will unlock after the birth time is confirmed.",
    luckTimelineDisabledNote:
      "Luck-cycle start points and transitions will be recalculated after the birth time is confirmed.",
  },
};

type PillarEntry = {
  key: VisiblePillarKey;
  label: string;
  pillar: SajuPreviewResponse["manse"]["pillars"][VisiblePillarKey];
};

function getPillarEntries(result: SajuPreviewResponse, locale: Locale): PillarEntry[] {
  const labels = resultDataCopy[locale].pillarColumns;
  return visiblePillarKeys.map((key) => ({
    key,
    label: labels[key],
    pillar: result.manse.pillars[key],
  }));
}

function getDisabledClassName(enabled: boolean) {
  return enabled ? undefined : "is-disabled";
}

function renderPillarValue(
  value: string | null | undefined,
  options: {
    locale: Locale;
    enabled: boolean;
  },
) {
  if (!options.enabled) {
    return disabledStateCopy[options.locale].disabledValue;
  }

  return formatManseText(value, options.locale);
}

function formatYearMonth(value: string | null | undefined, locale: Locale) {
  if (!value) {
    return resultDataCopy[locale].unavailable;
  }

  const match = value.match(/^(\d{4})-(\d{2})/);
  if (!match) {
    return value;
  }

  const year = match[1];
  const month = String(Number(match[2]));

  if (locale === "ko") {
    return `${year}년 ${month}월`;
  }

  const monthNames = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
  ];
  return `${monthNames[Number(month) - 1]} ${year}`;
}

function CompactPillarTable({
  locale,
  result,
}: {
  locale: Locale;
  result: SajuPreviewResponse;
}) {
  const ui = resultDataCopy[locale];
  const statusTexts = disabledStateCopy[locale];
  const pillars = getPillarEntries(result, locale);
  const isBirthTimeUnknown = !result.result.hour_pillar_enabled;

  return (
    <section className="result-pillar-overview">
      <div className="result-pillar-overview-head">
        <div>
          <p className="result-panel-label">{ui.pillarTitle}</p>
          <p className="result-pillar-overview-note">{ui.pillarSubtitle}</p>
        </div>
        <div className={`result-pillar-overview-meta${isBirthTimeUnknown ? " is-disabled" : ""}`}>
          <span>{isBirthTimeUnknown ? statusTexts.unknownTimeMetaLabel : ui.correctedTimeLabel}</span>
          <strong>
            {isBirthTimeUnknown
              ? statusTexts.unknownTimeMetaValue
              : result.regional_solar_correction.corrected_solar_datetime}
          </strong>
          {isBirthTimeUnknown ? <small>{statusTexts.timePillarDisabledNote}</small> : null}
        </div>
      </div>

      <div className="reading-table-wrap">
        <table className="reading-table result-pillar-table compact">
          <thead>
            <tr>
              {pillars.map(({ key, label, pillar }) => (
                <th key={key} className={getDisabledClassName(pillar.enabled)}>
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              {pillars.map(({ key, pillar }) => (
                <td key={key} className={getDisabledClassName(pillar.enabled)}>
                  <strong>
                    {renderPillarValue(pillar.gan_zhi, {
                      locale,
                      enabled: pillar.enabled,
                    })}
                  </strong>
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  );
}

function DetailedPillarTable({
  locale,
  result,
}: {
  locale: Locale;
  result: SajuPreviewResponse;
}) {
  const ui = resultDataCopy[locale];
  const pillars = getPillarEntries(result, locale);

  return (
    <div className="reading-data-card">
      <div className="reading-data-card-head">
        <div>
          <p className="result-panel-label">{ui.pillarTitle}</p>
          <p className="reading-data-card-note">{ui.pillarSubtitle}</p>
        </div>
      </div>

      <div className="reading-table-wrap">
        <table className="reading-table result-pillar-table">
          <thead>
            <tr>
              <th />
              {pillars.map(({ key, label, pillar }) => (
                <th key={key} className={getDisabledClassName(pillar.enabled)}>
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <th>{ui.ganZhiRow}</th>
              {pillars.map(({ key, pillar }) => (
                <td key={key} className={getDisabledClassName(pillar.enabled)}>
                  <strong>
                    {renderPillarValue(pillar.gan_zhi, {
                      locale,
                      enabled: pillar.enabled,
                    })}
                  </strong>
                </td>
              ))}
            </tr>
            <tr>
              <th>{ui.stemRow}</th>
              {pillars.map(({ key, pillar }) => (
                <td key={key} className={getDisabledClassName(pillar.enabled)}>
                  {renderPillarValue(pillar.stem, {
                    locale,
                    enabled: pillar.enabled,
                  })}
                </td>
              ))}
            </tr>
            <tr>
              <th>{ui.branchRow}</th>
              {pillars.map(({ key, pillar }) => (
                <td key={key} className={getDisabledClassName(pillar.enabled)}>
                  {renderPillarValue(pillar.branch, {
                    locale,
                    enabled: pillar.enabled,
                  })}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

function LuckTimelineTable({
  locale,
  result,
}: {
  locale: Locale;
  result: SajuPreviewResponse;
}) {
  const ui = resultDataCopy[locale];
  const statusTexts = disabledStateCopy[locale];
  const isDisabled = !result.manse.luck_cycles_enabled || !result.manse.luck_cycles.length;

  return (
    <div className={`reading-data-card${isDisabled ? " is-disabled" : ""}`}>
      <div className="reading-data-card-head">
        <div>
          <p className="result-panel-label">{ui.luckTimelineTitle}</p>
          <p className="reading-data-card-note">{ui.luckTimelineSubtitle}</p>
        </div>
      </div>

      <div className="reading-table-wrap">
        <table className="reading-table result-luck-table">
          <thead>
            <tr>
              <th>{ui.luckPillarColumn}</th>
              <th>{ui.luckStartColumn}</th>
              <th>{ui.luckChangeColumn}</th>
            </tr>
          </thead>
          <tbody>
            {isDisabled ? (
              <tr>
                <td className="is-disabled">
                  <strong>{statusTexts.disabledValue}</strong>
                </td>
                <td className="is-disabled">{statusTexts.disabledValue}</td>
                <td className="is-disabled">{statusTexts.disabledValue}</td>
              </tr>
            ) : (
              result.manse.luck_cycles.map((cycle) => (
                <tr key={`${cycle.index}-${cycle.gan_zhi}`}>
                  <td>
                    <strong>{formatManseText(cycle.gan_zhi, locale)}</strong>
                  </td>
                  <td>{formatYearMonth(cycle.start_datetime, locale)}</td>
                  <td>{formatYearMonth(cycle.change_datetime, locale)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {isDisabled ? (
        <p className="reading-disabled-note">{statusTexts.luckTimelineDisabledNote}</p>
      ) : null}
    </div>
  );
}

function renderInlineText(text: string) {
  const tokens = text.split(/(\*\*[^*]+\*\*)/g).filter(Boolean);
  return tokens.map((token, index) => {
    if (token.startsWith("**") && token.endsWith("**")) {
      return <strong key={`strong-${index}`}>{token.slice(2, -2)}</strong>;
    }

    return <span key={`text-${index}`}>{token}</span>;
  });
}

function isMarkdownTableRow(line: string) {
  return line.startsWith("|") && line.endsWith("|") && line.split("|").length > 3;
}

function isMarkdownSeparatorRow(line: string) {
  return /^\|[\s:\-|\u2500]+\|$/.test(line);
}

function parseTableCells(line: string) {
  return line
    .split("|")
    .slice(1, -1)
    .map((cell) => cell.trim());
}

function isNumberedHeading(line: string) {
  return /^((\d+[.)])|([①-⑩])|(\d+️⃣))\s*/.test(line);
}

function renderRichBody(text: string) {
  const nodes: ReactNode[] = [];
  const lines = text.split(/\r?\n/);
  let bullets: string[] = [];
  let tableRows: string[][] = [];
  let hasTableHeader = false;
  let keyIndex = 0;

  const flushBullets = () => {
    if (!bullets.length) {
      return;
    }
    nodes.push(
      <ul className="reading-bullets" key={`bullets-${keyIndex++}`}>
        {bullets.map((bullet, index) => (
          <li key={`bullet-${keyIndex}-${index}`}>{bullet}</li>
        ))}
      </ul>,
    );
    bullets = [];
  };

  const flushTable = () => {
    if (!tableRows.length) {
      hasTableHeader = false;
      return;
    }

    const headerCells = hasTableHeader ? tableRows[0] : null;
    const bodyRows = hasTableHeader ? tableRows.slice(1) : tableRows;

    nodes.push(
      <div className="reading-table-wrap" key={`table-${keyIndex++}`}>
        <table className="reading-table">
          {headerCells ? (
            <thead>
              <tr>
                {headerCells.map((cell, index) => (
                  <th key={`th-${keyIndex}-${index}`}>{renderInlineText(cell)}</th>
                ))}
              </tr>
            </thead>
          ) : null}
          <tbody>
            {bodyRows.map((row, rowIndex) => (
              <tr key={`tr-${keyIndex}-${rowIndex}`}>
                {row.map((cell, cellIndex) => (
                  <td key={`td-${keyIndex}-${rowIndex}-${cellIndex}`}>
                    {renderInlineText(cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>,
    );

    tableRows = [];
    hasTableHeader = false;
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();

    if (!line) {
      flushBullets();
      flushTable();
      continue;
    }

    if (isMarkdownTableRow(line)) {
      flushBullets();

      if (isMarkdownSeparatorRow(line)) {
        hasTableHeader = true;
      } else {
        tableRows.push(parseTableCells(line));
      }
      continue;
    }

    flushTable();

    if (line.startsWith("- ")) {
      bullets.push(line.slice(2).trim());
      continue;
    }

    flushBullets();

    if (line.startsWith("### ")) {
      nodes.push(
        <h4 className="reading-subheading" key={`h4-${keyIndex++}`}>
          {renderInlineText(line.slice(4).trim())}
        </h4>,
      );
      continue;
    }

    if (line.startsWith("## ")) {
      nodes.push(
        <h3 className="reading-inline-heading" key={`h3-${keyIndex++}`}>
          {renderInlineText(line.slice(3).trim())}
        </h3>,
      );
      continue;
    }

    if (isNumberedHeading(line)) {
      nodes.push(
        <h4 className="reading-numbered-heading" key={`numbered-${keyIndex++}`}>
          {renderInlineText(line)}
        </h4>,
      );
      continue;
    }

    nodes.push(
      <p className="reading-paragraph" key={`p-${keyIndex++}`}>
        {renderInlineText(line)}
      </p>,
    );
  }

  flushBullets();
  flushTable();
  return nodes;
}

function NarrativeSection({
  section,
  anchorId,
  badge,
  index,
  prelude,
}: {
  section: InterpretationNarrativeSection;
  anchorId: string;
  badge: string;
  index: number;
  prelude?: ReactNode;
}) {
  return (
    <section className="reading-section-panel" id={anchorId}>
      <div className="reading-section-shell">
        <div className="reading-section-meta">
          <span className="reading-section-index">{String(index).padStart(2, "0")}</span>
          <div className="reading-section-head">
            <p className="reading-section-label">{badge}</p>
            <h3>{section.title}</h3>
          </div>
        </div>
        {prelude ? <div className="reading-section-prelude">{prelude}</div> : null}
        <div className="reading-article">{renderRichBody(section.body)}</div>
      </div>
    </section>
  );
}

export function SajuResultView({ locale, result, onReset }: SajuResultViewProps) {
  const texts = getCopy(locale);
  const viewTexts = sectionViewCopy[locale];
  const statusTexts = disabledStateCopy[locale];
  const isBirthTimeUnknown = !result.result.hour_pillar_enabled;
  const visiblePillars = result.result.signals.visible_pillar_values
    .map((value) => formatManseText(value, locale))
    .join(" / ");
  const interpretation = result.result.interpretation;

  if (!interpretation) {
    return (
      <section className="result-screen">
        <div className="result-header">
          <div className="result-header-copy">
            <h2>{texts.resultTitle}</h2>
            <p>{visiblePillars}</p>
          </div>
          <button className="secondary-button" type="button" onClick={onReset}>
            {texts.backToForm}
          </button>
        </div>

        <div className="result-section">
          <h3>{texts.overview}</h3>
          <p>{result.result.overview}</p>
        </div>
      </section>
    );
  }

  const sections: Array<{
    key: SectionKey;
    anchorId: string;
    badge: string;
    section: InterpretationNarrativeSection;
    prelude?: ReactNode;
  }> = [
    {
      key: "core_analysis",
      anchorId: "core-analysis",
      badge: viewTexts.sectionLabels.core_analysis,
      section: interpretation.core_analysis,
      prelude: <DetailedPillarTable locale={locale} result={result} />,
    },
    {
      key: "love",
      anchorId: "love-reading",
      badge: viewTexts.sectionLabels.love,
      section: interpretation.love,
    },
    {
      key: "career",
      anchorId: "career-reading",
      badge: viewTexts.sectionLabels.career,
      section: interpretation.career,
    },
    {
      key: "wealth",
      anchorId: "wealth-reading",
      badge: viewTexts.sectionLabels.wealth,
      section: interpretation.wealth,
    },
    {
      key: "luck_flow",
      anchorId: "luck-flow-reading",
      badge: viewTexts.sectionLabels.luck_flow,
      section: interpretation.luck_flow,
      prelude: <LuckTimelineTable locale={locale} result={result} />,
    },
  ];

  return (
    <section className="result-screen">
      <div className="result-header">
        <div className="result-header-copy">
          <h2>{texts.resultTitle}</h2>
          <p>{visiblePillars}</p>
        </div>
        <button className="secondary-button" type="button" onClick={onReset}>
          {texts.backToForm}
        </button>
      </div>

      <div className="result-layout">
        <div className="result-main-column">
          {isBirthTimeUnknown ? (
            <section className="result-disabled-banner">
              <div className="result-disabled-banner-head">
                <span className="result-panel-label">{statusTexts.disabledBadge}</span>
                <h3>{statusTexts.unknownTimeNoticeTitle}</h3>
              </div>
              <p>{statusTexts.unknownTimeNoticeBody}</p>
            </section>
          ) : null}

          <section className="reading-summary-card">
            <div className="reading-summary-head">
              <span className="result-panel-label">{viewTexts.summaryLabel}</span>
              <p className="reading-summary-pillars">{visiblePillars}</p>
            </div>
            <h3>{interpretation.summary.headline}</h3>
            <CompactPillarTable locale={locale} result={result} />
            <div className="reading-article reading-summary-body">
              {renderRichBody(interpretation.summary.overview)}
            </div>
          </section>

          {sections.map((section, index) => (
            <NarrativeSection
              key={section.key}
              section={section.section}
              anchorId={section.anchorId}
              badge={section.badge}
              index={index + 1}
              prelude={section.prelude}
            />
          ))}
        </div>

        <aside className="result-side-column">
          <section className="result-side-panel">
            <span className="result-panel-label">{viewTexts.outlineLabel}</span>
            <nav className="result-section-nav" aria-label={viewTexts.outlineLabel}>
              {sections.map((section) => (
                <a className="result-section-link" href={`#${section.anchorId}`} key={section.key}>
                  <span>{section.badge}</span>
                  <strong>{section.section.title}</strong>
                </a>
              ))}
            </nav>
          </section>

          <section className="result-side-panel">
            <span className="result-panel-label">{viewTexts.basisLabel}</span>
            <ul className="result-basis-list">
              {viewTexts.basisItems.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </section>
        </aside>
      </div>
    </section>
  );
}
