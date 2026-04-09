import { SajuPreviewResponse } from "../../../shared/api/contracts";
import { Locale } from "../../../shared/copy";

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
            <strong>{result.manse.meta.day_master}</strong>
          </div>
          <div className="result-meta-item">
            <span>{text.grade}</span>
            <strong>{result.manse.analysis.internal_grade}</strong>
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
                  <td>{row.year || "-"}</td>
                  <td>{row.month || "-"}</td>
                  <td>{row.day || "-"}</td>
                  <td>{row.time || "-"}</td>
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
                    <td>{cycle.start_age}</td>
                    <td>{cycle.gan_zhi}</td>
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
              <strong>{position.gan_zhi}</strong>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
