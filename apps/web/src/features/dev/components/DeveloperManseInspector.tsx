import { ManseSpecialStar, SajuPreviewResponse } from "../../../shared/api/contracts";
import { Locale } from "../../../shared/copy";
import { formatManseJsonValue, formatManseList, formatManseText } from "../../shared/manseDisplay";
import { getDevCopy } from "../devCopy";

type DeveloperManseInspectorProps = {
  locale: Locale;
  result: SajuPreviewResponse | null;
};

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

const pillarKeys = ["year", "month", "day", "time"] as const;

function formatSpecialStarMatches(
  star: ManseSpecialStar,
  locale: Locale,
  pillarLabels: Record<(typeof pillarKeys)[number], string>,
  inactiveLabel: string,
): string {
  if (!star.matches.length) {
    return inactiveLabel;
  }

  return star.matches
    .map((match) => {
      const source = `${pillarLabels[match.pillar_key]} ${formatManseText(match.gan_zhi, locale)}`;

      if (!match.counterpart_pillar_key) {
        return source;
      }

      const counterpartValue = formatManseText(
        match.counterpart_gan_zhi ?? match.counterpart_branch ?? "",
        locale,
      );

      return `${source} <-> ${pillarLabels[match.counterpart_pillar_key]} ${counterpartValue}`;
    })
    .join(", ");
}

function formatStarRule(star: ManseSpecialStar, locale: Locale) {
  const anchor = formatManseText(star.anchor_value, locale);
  const target = formatManseList(star.target_values, locale);
  return `${anchor} -> ${target}`;
}

export function DeveloperManseInspector({ locale, result }: DeveloperManseInspectorProps) {
  const text = getDevCopy(locale);
  const elementText = elementLabels[locale];
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
  const specialStarScopes = [
    { scope: "core" as const, title: text.coreScope },
    { scope: "expanded" as const, title: text.expandedScope },
    { scope: "optional" as const, title: text.optionalScope },
  ];

  if (!result) {
    return (
      <section className="dev-section dev-output-panel">
        <h2>{text.resultTitle}</h2>
        <p>{text.noResult}</p>
      </section>
    );
  }

  const firstLuckCycle = result.manse.luck_cycles[0];
  const activeSpecialStars = result.manse.special_stars.filter((star) => star.active);
  const activeAuspiciousStars = activeSpecialStars.filter((star) => star.category === "auspicious");
  const activeSinsalStars = activeSpecialStars.filter((star) => star.category === "sinsal");
  const internalAnalysis = result.debug_trace?.internal_analysis;
  const interpretationDiagnostics = result.result.interpretation?.diagnostics;
  const displayManseJson = formatManseJsonValue(
    {
      ...result.manse,
      special_stars: activeSpecialStars,
    },
    locale,
  );

  return (
    <section className="dev-section dev-output-panel">
      <h2>{text.resultTitle}</h2>
      <p>{text.resultLead}</p>

      <div className="dev-review-block">
        <h3>{text.basic}</h3>
        <div className="dev-summary-grid">
          <div className="dev-summary-item">
            <span>{text.region}</span>
            <strong>{result.region.display_name}</strong>
          </div>
          <div className="dev-summary-item">
            <span>{text.correctedTime}</span>
            <strong>{result.regional_solar_correction.corrected_solar_datetime}</strong>
          </div>
          <div className="dev-summary-item">
            <span>Accuracy mode</span>
            <strong>{result.result.calculation_basis.accuracy_mode}</strong>
          </div>
          <div className="dev-summary-item">
            <span>Primary basis</span>
            <strong>{result.result.calculation_basis.primary_time_basis}</strong>
            <small>{result.result.calculation_basis.primary_input_datetime_to_lunar_python}</small>
          </div>
          <div className="dev-summary-item">
            <span>Day pillar basis</span>
            <strong>{result.manse.meta.day_pillar_rule || "-"}</strong>
            <small>{result.result.calculation_basis.primary_day_pillar_basis_datetime}</small>
          </div>
          <div className="dev-summary-item">
            <span>Iljin query date</span>
            <strong>{result.manse.meta.iljin_query_date || "-"}</strong>
            <small>{result.manse.meta.day_pillar_source || "-"}</small>
          </div>
          <div className="dev-summary-item">
            <span>{text.dayMaster}</span>
            <strong>{formatManseText(result.manse.meta.day_master, locale)}</strong>
          </div>
          <div className="dev-summary-item">
            <span>{text.grade}</span>
            <strong>{internalAnalysis?.internal_grade ?? "-"}</strong>
          </div>
          <div className="dev-summary-item">
            <span>{text.direction}</span>
            <strong>{result.manse.analysis.first_luck_cycle_direction ?? "-"}</strong>
          </div>
          <div className="dev-summary-item">
            <span>{text.exactAge}</span>
            <strong>
              {result.manse.analysis.first_luck_cycle_exact_start_age_years?.toFixed(4) ?? "-"}
            </strong>
          </div>
          <div className="dev-summary-item">
            <span>{text.preciseAge}</span>
            <strong>
              {result.manse.analysis.first_luck_cycle_precise_start_age_years?.toFixed(4) ?? "-"}
            </strong>
          </div>
          <div className="dev-summary-item">
            <span>{text.boundary}</span>
            <strong>{result.manse.analysis.first_luck_cycle_boundary_datetime ?? "-"}</strong>
          </div>
          <div className="dev-summary-item">
            <span>{text.activeAuspicious}</span>
            <strong>{activeAuspiciousStars.length}</strong>
            <small>
              {activeAuspiciousStars.length
                ? activeAuspiciousStars.map((star) => star.label).join(", ")
                : text.inactive}
            </small>
          </div>
          <div className="dev-summary-item">
            <span>{text.activeSinsal}</span>
            <strong>{activeSinsalStars.length}</strong>
            <small>
              {activeSinsalStars.length
                ? activeSinsalStars.map((star) => star.label).join(", ")
                : text.inactive}
            </small>
          </div>
        </div>
      </div>

      {interpretationDiagnostics ? (
        <div className="dev-review-block">
          <h3>{text.llmDiagnostics}</h3>
          <div className="dev-summary-grid">
            <div className="dev-summary-item">
              <span>{text.finalProvider}</span>
              <strong>{interpretationDiagnostics.final_provider}</strong>
            </div>
            <div className="dev-summary-item">
              <span>{text.configuredProvider}</span>
              <strong>{interpretationDiagnostics.configured_provider}</strong>
            </div>
            <div className="dev-summary-item">
              <span>{text.promptVersion}</span>
              <strong>{interpretationDiagnostics.prompt_version}</strong>
            </div>
            <div className="dev-summary-item">
              <span>{text.responseId}</span>
              <strong>{interpretationDiagnostics.final_response_id ?? text.none}</strong>
            </div>
            <div className="dev-summary-item">
              <span>{text.payloadChars}</span>
              <strong>{interpretationDiagnostics.payload_chars}</strong>
            </div>
            <div className="dev-summary-item">
              <span>{text.durationMs}</span>
              <strong>{interpretationDiagnostics.duration_ms}ms</strong>
            </div>
            <div className="dev-summary-item">
              <span>{text.fallbackReason}</span>
              <strong>{interpretationDiagnostics.fallback_reason ?? text.none}</strong>
            </div>
            <div className="dev-summary-item">
              <span>{text.validationIssues}</span>
              <small>
                {interpretationDiagnostics.validation_issues.length
                  ? interpretationDiagnostics.validation_issues.join(", ")
                  : text.none}
              </small>
            </div>
          </div>

          <div className="dev-table-wrap">
            <table className="dev-table compact">
              <caption>{text.attemptLogs}</caption>
              <thead>
                <tr>
                  <th>{text.attempt}</th>
                  <th>{text.mode}</th>
                  <th>{text.tokenBudget}</th>
                  <th>{text.status}</th>
                  <th>{text.responseId}</th>
                  <th>{text.outputChars}</th>
                  <th>{text.error}</th>
                  <th>{text.outputExcerpt}</th>
                </tr>
              </thead>
              <tbody>
                {interpretationDiagnostics.attempts.map((attempt) => (
                  <tr key={`${attempt.attempt_index}-${attempt.mode}-${attempt.status}`}>
                    <td>{attempt.attempt_index}</td>
                    <td>{attempt.mode}</td>
                    <td>{attempt.token_budget}</td>
                    <td>{attempt.status}</td>
                    <td>{attempt.response_id ?? text.none}</td>
                    <td>{attempt.output_chars}</td>
                    <td>
                      {attempt.error_type || attempt.error_message || attempt.issues.length
                        ? [attempt.error_type, attempt.error_message, attempt.issues.join(", ")]
                            .filter(Boolean)
                            .join(" / ")
                        : text.none}
                    </td>
                    <td>{attempt.output_excerpt ?? text.none}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      <div className="dev-review-block">
        <h3>{text.pillars}</h3>
        <div className="dev-pillars-grid">
          {pillarKeys.map((key) => {
            const pillar = result.manse.pillars[key];

            return (
              <div className="dev-pillar-card" key={pillar.key}>
                <span>{pillarLabels[key]}</span>
                <strong>{formatManseText(pillar.gan_zhi, locale)}</strong>
                <small>
                  {formatManseText(pillar.stem, locale)} / {formatManseText(pillar.branch, locale)}
                </small>
              </div>
            );
          })}
        </div>
      </div>

      <div className="dev-review-block">
        <h3>{text.manseTable}</h3>
        <div className="dev-table-wrap">
          <table className="dev-table">
            <caption>{text.manseTable}</caption>
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
                  <th scope="row">{row.label}</th>
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

      <div className="dev-review-grid">
        <div className="dev-review-block">
          <h3>{text.elements}</h3>
          <div className="dev-table-wrap">
            <table className="dev-table compact">
              <caption>{text.elements}</caption>
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
                    <th scope="row">{elementText[key]}</th>
                    <td>{result.manse.elements[key]}</td>
                    <td>{result.manse.analysis.element_percentages[key]}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <pre className="dev-pre">
            {JSON.stringify(result.manse.analysis.visible_ten_god_distribution, null, 2)}
          </pre>
        </div>

        <div className="dev-review-block">
          <h3>{text.luckCycles}</h3>
          {result.manse.luck_cycles_enabled ? (
            <div className="dev-table-wrap">
              <table className="dev-table compact">
                <caption>{text.luckCycles}</caption>
                <thead>
                  <tr>
                    <th>{text.startAge}</th>
                    <th>{text.ganZhi}</th>
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
            <p>{text.noLuckCycles}</p>
          )}

          {firstLuckCycle ? (
            <div className="dev-first-cycle-note">
              <strong>
                {firstLuckCycle.start_age_years != null && firstLuckCycle.start_age_months != null
                  ? `${firstLuckCycle.start_age_years}y ${firstLuckCycle.start_age_months}m`
                  : firstLuckCycle.start_age}{" "}
                / {formatManseText(firstLuckCycle.gan_zhi, locale)}
              </strong>
            </div>
          ) : null}
        </div>
      </div>

      <div className="dev-review-grid">
        <div className="dev-review-block">
          <h3>{text.supplementary}</h3>
          <div className="dev-summary-grid">
            {Object.values(result.manse.supplementary_positions).map((position) => (
              <div className="dev-summary-item" key={position.key}>
                <span>{position.label}</span>
                <strong>{formatManseText(position.gan_zhi, locale)}</strong>
              </div>
            ))}
          </div>
        </div>

        <div className="dev-review-block">
          <h3>{text.pipeline}</h3>
          <ul className="dev-list">
            {Object.entries(result.pipeline_status).map(([key, value]) => (
              <li key={key}>
                <span>{key}</span>
                <strong>{value}</strong>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="dev-review-block">
        <div className="dev-review-heading">
          <div>
            <h3>{text.activeStarsTitle}</h3>
            <p>{text.activeStarsLead}</p>
          </div>
          <strong>{activeSpecialStars.length}</strong>
        </div>

        <div className="dev-star-overview-grid">
          <div className="dev-star-overview-card">
            <span>{text.totalActive}</span>
            <strong>{activeSpecialStars.length}</strong>
          </div>
          <div className="dev-star-overview-card">
            <span>{text.activeAuspicious}</span>
            <strong>{activeAuspiciousStars.length}</strong>
          </div>
          <div className="dev-star-overview-card">
            <span>{text.activeSinsal}</span>
            <strong>{activeSinsalStars.length}</strong>
          </div>
          {specialStarScopes.map((scope) => (
            <div className="dev-star-overview-card" key={scope.scope}>
              <span>{scope.title}</span>
              <strong>
                {activeSpecialStars.filter((star) => star.scope === scope.scope).length}
              </strong>
            </div>
          ))}
        </div>

        {specialStarGroups.map((group) => {
          const items = activeSpecialStars.filter((star) => star.category === group.category);

          return (
            <div className="dev-review-block" key={group.category}>
              <h4 className="dev-subheading">{group.title}</h4>
              {items.length ? (
                <div className="dev-star-card-grid">
                  {items.map((star) => (
                    <article className="dev-star-card is-active" key={star.key}>
                      <div className="dev-star-card-head">
                        <div className="dev-star-card-title">
                          <div className="dev-star-card-title-row">
                            <strong>{star.label}</strong>
                            <span className="dev-star-badge">{star.tier}</span>
                          </div>
                          <p>{star.usage_summary}</p>
                        </div>
                        <div className="dev-star-badge-row">
                          <span
                            className={`dev-star-badge ${
                              star.category === "auspicious"
                                ? "is-auspicious"
                                : "is-sinsal"
                            }`}
                          >
                            {star.category === "auspicious" ? text.auspicious : text.sinsal}
                          </span>
                          <span className="dev-star-badge">
                            {
                              specialStarScopes.find((scope) => scope.scope === star.scope)?.title
                            }
                          </span>
                          <span className="dev-star-badge">{star.method_id}</span>
                        </div>
                      </div>

                      <div className="dev-star-detail-grid">
                        <div className="dev-star-detail-item">
                          <span>{text.basis}</span>
                          <p>{star.basis}</p>
                        </div>
                        <div className="dev-star-detail-item">
                          <span>{text.weight}</span>
                          <p>{star.weight}</p>
                        </div>
                        <div className="dev-star-detail-item">
                          <span>{text.rule}</span>
                          <p>{formatStarRule(star, locale)}</p>
                        </div>
                        <div className="dev-star-detail-item">
                          <span>{text.starCount}</span>
                          <p>{star.count}</p>
                        </div>
                        <div className="dev-star-detail-item dev-star-detail-item-wide">
                          <span>{text.matches}</span>
                          <p>{formatSpecialStarMatches(star, locale, pillarLabels, text.inactive)}</p>
                        </div>
                      </div>

                      <div className="dev-star-keywords">
                        {star.usage_keywords.map((keyword) => (
                          <span className="dev-star-keyword" key={`${star.key}-${keyword}`}>
                            {keyword}
                          </span>
                        ))}
                      </div>

                      {star.note ? (
                        <div className="dev-star-detail-item">
                          <span>{text.noteLabel}</span>
                          <p>{star.note}</p>
                        </div>
                      ) : null}
                    </article>
                  ))}
                </div>
              ) : (
                <p className="dev-star-empty">{text.noActiveStars}</p>
              )}
            </div>
          );
        })}
      </div>

      {result.debug_trace ? (
        <div className="dev-review-grid">
          <div className="dev-review-block">
            <h3>{text.checkpoints}</h3>
            <ul className="dev-list stacked">
              {result.debug_trace.checkpoints.map((checkpoint) => (
                <li key={`${checkpoint.stage}-${checkpoint.status}`}>
                  <strong>{checkpoint.stage}</strong>
                  <span>{checkpoint.status}</span>
                  {checkpoint.note ? <small>{checkpoint.note}</small> : null}
                </li>
              ))}
            </ul>
          </div>

          {result.debug_trace.birth_time_context ? (
            <div className="dev-review-block">
              <h3>Birth time context</h3>
              <pre className="dev-pre">
                {JSON.stringify(result.debug_trace.birth_time_context, null, 2)}
              </pre>
            </div>
          ) : null}

          {result.debug_trace.calculation_basis ? (
            <div className="dev-review-block">
              <h3>Calculation basis</h3>
              <pre className="dev-pre">
                {JSON.stringify(result.debug_trace.calculation_basis, null, 2)}
              </pre>
            </div>
          ) : null}

          {result.debug_trace.year_month_boundary_context ? (
            <div className="dev-review-block">
              <h3>Year/month boundary context</h3>
              <pre className="dev-pre">
                {JSON.stringify(result.debug_trace.year_month_boundary_context, null, 2)}
              </pre>
            </div>
          ) : null}

          {result.debug_trace.candidate_charts?.length ? (
            <div className="dev-review-block">
              <h3>Candidate charts</h3>
              <pre className="dev-pre">
                {JSON.stringify(result.debug_trace.candidate_charts, null, 2)}
              </pre>
            </div>
          ) : null}

          {result.debug_trace.uncertainty_flags?.length ? (
            <div className="dev-review-block">
              <h3>Uncertainty flags</h3>
              <pre className="dev-pre">
                {JSON.stringify(result.debug_trace.uncertainty_flags, null, 2)}
              </pre>
            </div>
          ) : null}

          <div className="dev-review-block">
            <h3>{text.requestEcho}</h3>
            <pre className="dev-pre">
              {JSON.stringify(result.debug_trace.request_echo, null, 2)}
            </pre>
          </div>
        </div>
      ) : null}

      <div className="dev-review-block">
        <h3>{text.rawJson}</h3>
        <pre className="dev-pre">{JSON.stringify(displayManseJson, null, 2)}</pre>
      </div>
    </section>
  );
}
