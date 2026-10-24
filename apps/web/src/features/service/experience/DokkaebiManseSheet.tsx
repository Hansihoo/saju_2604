import { useEffect, useId, useRef, useState } from "react";
import type { MansePillar, SajuPreviewRequest } from "../../../shared/api/contracts";
import type { SajuBasicResponse } from "../../../shared/api/questionContracts";
import type { Locale } from "../../../shared/copy";
import { formatManseList, formatManseText } from "../../shared/manseDisplay";

export const manseSheetVersion = "manse-sheet-2026-10-24.1";

const copy = {
  ko: {
    title: "내 만세력", close: "만세력 닫기", back: "풀이 이어 읽기", chart: "사주 원국", elements: "오행 분포",
    stem: "천간", branch: "지지", day: "나", details: "십성·지장간", stemGod: "천간 십성", branchGod: "지지 십성", hidden: "지장간",
    basis: "입력·계산 기준", provisional: "잠정 명식", unknown: "출생시간 미상 · 시주 제외",
    solar: "양력", lunar: "음력", leap: "윤달", input: "출생 입력", region: "출생 지역", corrected: "보정 시각",
    chartCaption: "위쪽은 천간, 아래쪽은 지지야.", elementTitle: "겉글자 오행",
    elementNote: "천간·지지 대표 오행의 개수야. 지장간과 가중치는 포함하지 않았어. 0개라고 사주 전체에 그 기운이 없다는 뜻은 아니야.",
    table: "출생정보로 계산한 사주 원국", detailTable: "계산된 십성과 지장간", info: "만세력 정보 선택",
    labels: { year: "년주", month: "월주", day: "일주", time: "시주" },
  },
  en: {
    title: "My birth chart", close: "Close birth chart", back: "Continue reading", chart: "Four pillars", elements: "Five elements",
    stem: "Stem", branch: "Branch", day: "Me", details: "Ten gods & hidden stems", stemGod: "Stem relation", branchGod: "Branch relation", hidden: "Hidden stems",
    basis: "Birth details & calculation", provisional: "Provisional chart", unknown: "Birth time unknown · hour excluded",
    solar: "Solar", lunar: "Lunar", leap: "Leap month", input: "Birth input", region: "Birth region", corrected: "Corrected time",
    chartCaption: "Stems above, branches below.", elementTitle: "Visible element counts",
    elementNote: "Counts of the visible stems and branches. Hidden stems and weighting are excluded. A zero does not mean the element is absent from the entire chart.",
    table: "Four pillars calculated from birth details", detailTable: "Calculated ten gods and hidden stems", info: "Birth chart information",
    labels: { year: "Year", month: "Month", day: "Day", time: "Hour" },
  },
} as const;

const elementNames: Record<string, { ko: string; en: string }> = {
  木: { ko: "목", en: "Wood" }, 火: { ko: "화", en: "Fire" }, 土: { ko: "토", en: "Earth" },
  金: { ko: "금", en: "Metal" }, 水: { ko: "수", en: "Water" },
};
const elementKeys = ["wood", "fire", "earth", "metal", "water"] as const;
const elementSymbols = ["木", "火", "土", "金", "水"] as const;
const tenGodNames: Record<string, string> = {
  일간: "Day master", 비견: "Peer", 겁재: "Rival", 식신: "Expression", 상관: "Output", 편재: "Indirect wealth",
  정재: "Direct wealth", 편관: "Seven killings", 정관: "Direct officer", 편인: "Indirect resource", 정인: "Direct resource",
};

function PillarCharacter({ pillar, field, locale }: { pillar: MansePillar; field: "stem" | "branch"; locale: Locale }) {
  const value = pillar.enabled ? pillar[field] : null;
  const element = pillar.enabled ? pillar[field === "stem" ? "stem_element" : "branch_element"] : null;
  return <div className="dk-manse-character" data-element={element ?? undefined}>
    <strong>{value || "—"}</strong>
    {value ? <span>{formatManseText(value, locale)}{element ? ` · ${elementNames[element]?.[locale] ?? element}` : ""}</span> : null}
  </div>;
}

export function DokkaebiManseSheet({ result, input, locale, notices, onClose }: {
  result: SajuBasicResponse; input: SajuPreviewRequest | null; locale: Locale; notices: string[]; onClose: () => void;
}) {
  const text = copy[locale];
  const titleId = useId();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [view, setView] = useState<"chart" | "elements">("chart");
  const manse = result.manse;
  const columns = manse.meta.pillar_order;
  const provisional = result.result.uncertainty_summary.some((flag) => flag.severity === "critical");
  const relation = (value: string | null | undefined) => value ? (locale === "en" ? tenGodNames[value] ?? value : value) : "—";

  useEffect(() => {
    const dialog = dialogRef.current;
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const oldOverflow = document.body.style.overflow;
    dialog?.showModal();
    document.body.style.overflow = "hidden";
    return () => {
      dialog?.close();
      document.body.style.overflow = oldOverflow;
      previousFocus?.focus({ preventScroll: true });
    };
  }, []);

  return <dialog ref={dialogRef} className="dk-manse-dialog" lang={locale} aria-labelledby={titleId}
    data-manse-presentation-version={manseSheetVersion} onCancel={onClose}
    onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <div className="dk-manse-sheet">
      <div className="dk-manse-top">
        <div className="dk-manse-handle" aria-hidden="true" />
        <div className="dk-manse-heading"><div><span className="dk-manse-eyebrow">MY BIRTH CHART</span><h2 id={titleId}>{text.title}</h2></div>
          <button type="button" className="dk-manse-close" aria-label={text.close} onClick={onClose} autoFocus>×</button></div>
        <div className="dk-manse-meta"><span>{result.region.display_name}</span><span>{input?.calendar_type === "lunar" ? text.lunar : input ? text.solar : ""}{input?.is_lunar_leap_month ? ` · ${text.leap}` : ""}</span></div>
        {provisional || !manse.meta.hour_pillar_enabled ? <p className="dk-manse-state">{!manse.meta.hour_pillar_enabled ? text.unknown : text.provisional}</p> : null}
        <div className="dk-manse-views" role="group" aria-label={text.info}>
          <button type="button" aria-pressed={view === "chart"} onClick={() => setView("chart")}>{text.chart}</button>
          <button type="button" aria-pressed={view === "elements"} onClick={() => setView("elements")}>{text.elements}</button>
        </div>
      </div>
      <div className="dk-manse-scroll">
        {view === "chart" ? <>
          <table className="dk-manse-table"><caption className="dk-sr-only">{text.table}</caption>
            <colgroup><col className="dk-manse-row-label" />{columns.map((key) => <col key={key} />)}</colgroup>
            <thead><tr><th scope="col" />{columns.map((key) => <th scope="col" key={key} data-day={key === "day"}>{text.labels[key]}{key === "day" ? <small>{text.day}</small> : null}</th>)}</tr></thead>
            <tbody>{(["stem", "branch"] as const).map((field) => <tr key={field}><th scope="row">{text[field]}</th>{columns.map((key) => <td key={key} data-day={key === "day"}><PillarCharacter pillar={manse.pillars[key]} field={field} locale={locale} /></td>)}</tr>)}</tbody>
          </table>
          <p className="dk-manse-caption">{text.chartCaption}</p>
          <details className="dk-manse-details"><summary>{text.details}<span aria-hidden="true">＋</span></summary>
            <table className="dk-manse-extra"><caption className="dk-sr-only">{text.detailTable}</caption>
              <thead><tr><th scope="col" />{columns.map((key) => <th key={key} scope="col">{text.labels[key]}</th>)}</tr></thead>
              <tbody>
                {(["stem_ten_god", "branch_ten_god"] as const).map((field) => <tr key={field}><th scope="row">{field === "stem_ten_god" ? text.stemGod : text.branchGod}</th>{columns.map((key) => <td key={key}>{manse.pillars[key].enabled ? relation(manse.pillars[key][field]) : "—"}</td>)}</tr>)}
                <tr><th scope="row">{text.hidden}</th>{columns.map((key) => <td key={key}>{manse.pillars[key].enabled && manse.pillars[key].hidden_stems.length ? formatManseList(manse.pillars[key].hidden_stems, locale) : "—"}</td>)}</tr>
              </tbody>
            </table>
          </details>
        </> : <section className="dk-manse-elements" aria-label={text.elementTitle}>
          <h3>{text.elementTitle}</h3><div>{elementKeys.map((key, index) => <div className="dk-manse-element" key={key} data-element={elementSymbols[index]}><span>{elementNames[elementSymbols[index]][locale]}</span><strong>{manse.elements[key]}</strong></div>)}</div>
          <p>{text.elementNote}</p>
        </section>}
        <details className="dk-manse-details"><summary>{text.basis}<span aria-hidden="true">＋</span></summary>
          <dl className="dk-manse-basis">
            {input ? <div><dt>{text.input}</dt><dd>{input.birth_date}{manse.meta.hour_pillar_enabled ? ` · ${input.birth_time}` : ` · ${text.unknown}`}</dd></div> : null}
            <div><dt>{text.region}</dt><dd>{result.region.display_name}</dd></div>
            {manse.meta.hour_pillar_enabled ? <div><dt>{text.corrected}</dt><dd>{result.regional_solar_correction.corrected_solar_datetime}</dd></div> : null}
          </dl>
          {notices.map((notice) => <p className="dk-manse-notice" key={notice}>{notice}</p>)}
        </details>
      </div>
      <footer className="dk-manse-footer"><button type="button" onClick={onClose}>{text.back}<span aria-hidden="true">↓</span></button></footer>
    </div>
  </dialog>;
}
