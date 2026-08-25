import { SajuPreviewResponse } from "../../../shared/api/contracts";
import { Locale } from "../../../shared/copy";
import { formatManseList, formatManseText } from "../../shared/manseDisplay";

type ManseTestPanelProps = {
  locale: Locale;
  result: SajuPreviewResponse;
};

const ui = {
  ko: {
    title: "테스트용 만세력 정보",
    lead: "현재 계산 결과를 검증하기 위한 출력입니다. 최종 사용자용 문구는 아닙니다.",
    overview: "기본 정보",
    region: "출생 지역",
    correctedTime: "보정 시각",
    dayMaster: "일간",
    grade: "내부 등급",
    table: "만세력 표",
    year: "년주",
    month: "월주",
    day: "일주",
    time: "시주",
    elements: "오행 분석",
    count: "개수",
    ratio: "비율",
    luckCycles: "대운 흐름",
    startAge: "시작 나이",
    period: "구간",
    supplementary: "보조 위치",
    specialStars: "신살 / 길성",
    auspicious: "길성",
    sinsal: "신살",
    starLabel: "항목",
    tier: "등급",
    method: "메서드",
    weight: "가중치",
    starCount: "매칭 수",
    usage: "용도",
    basis: "기준",
    anchor: "기준값",
    target: "목표",
    matches: "적중 기둥",
    inactive: "해당 없음",
    noLuckCycles: "출생시간 미상으로 대운 정보가 비활성화되었습니다.",
  },
  en: {
    title: "Testing Manse Data",
    lead: "This output is for verifying the current calculation result, not the final user-facing narrative.",
    overview: "Overview",
    region: "Birth region",
    correctedTime: "Corrected time",
    dayMaster: "Day master",
    grade: "Internal grade",
    table: "Manse table",
    year: "Year",
    month: "Month",
    day: "Day",
    time: "Time",
    elements: "Element analysis",
    count: "Count",
    ratio: "Ratio",
    luckCycles: "Luck cycles",
    startAge: "Start age",
    period: "Period",
    supplementary: "Supplementary positions",
    specialStars: "Special stars",
    auspicious: "Auspicious",
    sinsal: "Shinsal",
    starLabel: "Star",
    tier: "Tier",
    method: "Method",
    weight: "Weight",
    starCount: "Match count",
    usage: "Usage",
    basis: "Basis",
    anchor: "Anchor",
    target: "Target",
    matches: "Matches",
    inactive: "No match",
    noLuckCycles: "Luck-cycle data is disabled because the birth time is estimated.",
  },
} as const;

const elementLabels = {
  ko: {
    wood: "목",
    fire: "화",
    earth: "토",
    metal: "금",
    water: "수",
  },
  en: {
    wood: "Wood",
    fire: "Fire",
    earth: "Earth",
    metal: "Metal",
    water: "Water",
  },
} as const;

export function ManseTestPanel({ locale, result }: ManseTestPanelProps) {
  const text = ui[locale];
  const elementText = elementLabels[locale];
  const internalAnalysis = result.debug_trace?.internal_analysis;
  const pillarLabels = {
    year: text.year,
    month: text.month,
    day: text.day,
    time: text.time,
  } as const;

  const specialStarGroups = [
    { category: "auspicious" as const, title: text.auspicious },
    { category: "sinsal" as const, title: text.sinsal },
  ];

  return (
    <section className="result-test-panel" aria-label={text.title}>
      <div className="result-test-header">
        <h3>{text.title}</h3>
        <p>{text.lead}</p>
      </div>

      <div className="result-test-section">
        <h4>{text.overview}</h4>
        <div className="result-meta-grid">
          <div className="result-meta-item">
            <span>{text.region}</span>
            <strong>{result.region.display_name}</strong>
          </div>
          <div className="result-meta-item">
            <span>{text.correctedTime}</span>
            <strong>{result.regional_solar_correction.corrected_solar_datetime}</strong>
          </div>
          <div className="result-meta-item">
            <span>{text.dayMaster}</span>
            <strong>{formatManseText(result.manse.meta.day_master, locale)}</strong>
          </div>
          <div className="result-meta-item">
            <span>{text.grade}</span>
            <strong>{internalAnalysis?.internal_grade ?? "-"}</strong>
          </div>
        </div>
      </div>

      <div className="result-test-section">
        <h4>{text.table}</h4>
        <div className="result-table-wrap">
          <table className="result-table">
            <thead>
              <tr>
                <th />
                <th>{text.year}</th>
                <th>{text.month}</th>
                <th>{text.day}</th>
                <th>{text.time}</th>
              </tr>
            </thead>
            <tbody>
              {result.manse.table_rows.map((row) => (
                <tr key={row.label}>
                  <th>{row.label}</th>
                  <td>{formatManseText(row.year, locale)}</td>
                  <td>{formatManseText(row.month, locale)}</td>
                  <td>{formatManseText(row.day, locale)}</td>
                  <td>{formatManseText(row.time, locale)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="result-test-section">
        <h4>{text.elements}</h4>
        <div className="result-table-wrap">
          <table className="result-table compact">
            <thead>
              <tr>
                <th />
                <th>{text.count}</th>
                <th>{text.ratio}</th>
              </tr>
            </thead>
            <tbody>
              {(["wood", "fire", "earth", "metal", "water"] as const).map((key) => (
                <tr key={key}>
                  <th>{elementText[key]}</th>
                  <td>{result.manse.elements[key]}</td>
                  <td>{result.manse.analysis.element_percentages[key]}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="result-test-section">
        <h4>{text.luckCycles}</h4>
        {result.manse.luck_cycles_enabled ? (
          <div className="result-table-wrap">
            <table className="result-table compact">
              <thead>
                <tr>
                  <th>{text.startAge}</th>
                  <th>干支</th>
                  <th>{text.period}</th>
                </tr>
              </thead>
              <tbody>
                {result.manse.luck_cycles.map((cycle) => (
                  <tr key={`${cycle.index}-${cycle.gan_zhi}`}>
                    <td>
                      {cycle.start_age_years != null && cycle.start_age_months != null
                        ? `${cycle.start_age_years}y ${cycle.start_age_months}m (${cycle.start_age})`
                        : cycle.start_age}
                    </td>
                    <td>{formatManseText(cycle.gan_zhi, locale)}</td>
                    <td>
                      {cycle.start_year} - {cycle.end_year}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="result-test-empty">{text.noLuckCycles}</p>
        )}
      </div>

      <div className="result-test-section">
        <h4>{text.supplementary}</h4>
        <div className="result-meta-grid">
          {Object.values(result.manse.supplementary_positions).map((position) => (
            <div className="result-meta-item" key={position.key}>
              <span>{position.label}</span>
              <strong>{formatManseText(position.gan_zhi, locale)}</strong>
            </div>
          ))}
        </div>
      </div>

      <div className="result-test-section">
        <h4>{text.specialStars}</h4>
        {specialStarGroups.map((group) => {
          const items = result.manse.special_stars.filter((star) => star.category === group.category);

          return (
            <div key={group.category} className="result-table-wrap">
              <table className="result-table compact">
                <thead>
                  <tr>
                    <th colSpan={10}>{group.title}</th>
                  </tr>
                  <tr>
                    <th>{text.starLabel}</th>
                    <th>{text.tier}</th>
                    <th>{text.method}</th>
                    <th>{text.weight}</th>
                    <th>{text.starCount}</th>
                    <th>{text.usage}</th>
                    <th>{text.basis}</th>
                    <th>{text.anchor}</th>
                    <th>{text.target}</th>
                    <th>{text.matches}</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((star) => (
                    <tr key={star.key}>
                      <th>{star.label}</th>
                      <td>{star.tier}</td>
                      <td>{star.method_id}</td>
                      <td>{star.weight}</td>
                      <td>{star.count}</td>
                      <td>{star.usage_summary}</td>
                      <td>{star.basis}</td>
                      <td>{formatManseText(star.anchor_value, locale)}</td>
                      <td>{formatManseList(star.target_values, locale)}</td>
                      <td>
                        {star.matches.length
                          ? star.matches
                              .map(
                                (match) =>
                                  match.counterpart_pillar_key
                                    ? `${pillarLabels[match.pillar_key]} ${formatManseText(match.gan_zhi, locale)} ↔ ${pillarLabels[match.counterpart_pillar_key]} ${formatManseText(match.counterpart_gan_zhi ?? "", locale)}`
                                    : `${pillarLabels[match.pillar_key]} ${formatManseText(match.gan_zhi, locale)}`,
                              )
                              .join(", ")
                          : text.inactive}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        })}
      </div>
    </section>
  );
}
