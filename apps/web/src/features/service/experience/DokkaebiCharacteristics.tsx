import type { SajuChartCharacteristics } from "../../../shared/api/questionContracts";
import type { Locale } from "../../../shared/copy";

const labels = {
  ko: { advantage: "장점으로 읽는 부분", burden: "부담으로 읽는 부분", emphasis: "풀이 비중", other: "다른 기준으로 보면", selection: "아래는 본문에 선택된 항목끼리의 비교야. 빠진 항목이 그 사주에 전혀 없다는 뜻은 아니야.", unchanged: "같은 항목·비중", changed: "비중이 달라진 항목", added: "대신 선택된 항목", removed: "이번에는 선택되지 않은 항목" },
  en: { advantage: "Potential advantages", burden: "Potential burdens", emphasis: "Reading emphasis", other: "Under another convention", selection: "This compares the items selected for the main reading. An unselected item is not necessarily absent from that chart.", unchanged: "Same item and emphasis", changed: "Different emphasis", added: "Selected instead", removed: "Not selected here" },
};

export function DokkaebiCharacteristics({ reading, locale }: { reading: SajuChartCharacteristics; locale: Locale }) {
  const copy = labels[locale];
  if (!reading.items.length) return null;
  return <div className="dk-characteristics" data-chart-characteristics>
    {reading.assumption ? <p className="dk-information-scope">{reading.assumption}</p> : null}
    {(["advantage", "burden"] as const).map((direction) => {
      const items = reading.items.filter((item) => item.direction === direction);
      return items.length ? <div className={`dk-characteristic-group dk-characteristic-${direction}`} key={direction}>
        <h3>{copy[direction]}</h3>
        {items.map((item) => <article className="dk-characteristic" key={item.id} data-characteristic={item.id}>
          <div className="dk-characteristic-heading"><h4>{item.title}</h4><span>{copy.emphasis} · {item.emphasis_label}</span></div>
          <p className="dk-characteristic-conclusion">{item.conclusion}</p>
          <p>{item.reason}</p>
          <p className="dk-characteristic-emphasis">{item.emphasis_reason}</p>
          <p className="dk-characteristic-condition">{item.condition}</p>
        </article>)}
      </div> : null;
    })}
    <p className="dk-small-note">{reading.scale_note}</p>
  </div>;
}

export function CharacteristicMemo({ reading, locale }: { reading: SajuChartCharacteristics; locale: Locale }) {
  const copy = labels[locale];
  if (!reading.items.length) return null;
  const titles = new Map([...reading.items, ...reading.comparisons.flatMap((c) => c.items)].map((item) => [item.id, item.title]));
  return <div className="dk-characteristic-memo">
    {reading.items.map((item) => <div className="dk-memo-section" key={item.id}>
      <h4>{item.title} · {item.emphasis_label}</h4><p>{item.emphasis_reason}</p><p>{item.memo_body}</p>
    </div>)}
    {reading.comparisons.map((comparison) => <section className="dk-memo-section" key={comparison.label} data-characteristic-comparison>
      <h3>{copy.other}: {comparison.label}</h3>
      <p>{["year", "month", "day", "time"].map((key) => comparison.chart[key]).join(" · ")}</p>
      <p>{copy.selection}</p>
      {(["unchanged", "changed", "added", "removed"] as const).map((kind) => comparison[kind].length ?
        <p key={kind}>{copy[kind]}: {comparison[kind].map((id) => titles.get(id) ?? id).join(" · ")}</p> : null)}
      {comparison.items.map((item) => <div className="dk-memo-section" key={item.id}>
        <h4>{item.title} · {item.emphasis_label}</h4><p>{item.conclusion}</p><p>{item.reason}</p><p>{item.emphasis_reason}</p><p>{item.condition}</p><p>{item.memo_body}</p>
      </div>)}
    </section>)}
  </div>;
}
