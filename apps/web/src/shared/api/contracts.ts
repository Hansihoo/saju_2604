export type ApiHealth = {
  status: string;
  service: string;
  version: string;
  message: string;
  focus: string[];
};

export type RegionSuggestion = {
  id: string;
  display_name: string;
  country: string;
  province: string;
  city: string;
  tzid: string;
  longitude: number;
  regional_time_offset_minutes: number;
  correction_basis: string;
  aliases: string[];
  latitude?: number | null;
  admin_code?: string | null;
  source: string;
  is_active: boolean;
};

export type RegionSearchResponse = {
  trace_id: string;
  items: RegionSuggestion[];
  total: number;
};

export type AccuracyMode = "legacy" | "standard_time" | "mean_solar_time" | "compare";

export type SajuPreviewRequest = {
  locale: "ko" | "en";
  calendar_type: "solar" | "lunar";
  birth_date: string;
  birth_time: string;
  is_birth_time_estimated: boolean;
  is_lunar_leap_month: boolean;
  gender: "male" | "female";
  region_id: string;
  accuracy_mode?: AccuracyMode;
  debug: boolean;
};

export type PipelineStatus = {
  input_validation: string;
  region_resolution: string;
  time_correction: string;
  calendar_normalization: string;
  regional_solar_correction: string;
  saju_calculation: string;
  analysis_engine: string;
  llm_formatting: string;
  free_preview_formatting?: string;
};

export type EvidenceSection = {
  title: string;
  status: "ready" | "disabled" | "coming_soon";
  summary: string;
};

export type UncertaintyFlag = {
  code: string;
  severity: "info" | "warning" | "critical";
  affected_fields: string[];
  user_message: string;
  developer_message: string;
  evidence: Record<string, unknown>;
};

export type CalculationBasis = {
  accuracy_mode: AccuracyMode;
  primary_candidate_id: string;
  primary_time_basis: string;
  primary_midnight_rule: string;
  primary_input_datetime_to_lunar_python: string;
  primary_day_pillar_basis_datetime: string;
  legacy_corrected_solar_datetime: string;
  compare_candidates_enabled: boolean;
};

export type TimeCorrectionSummary = {
  tzid: string;
  source_local_datetime: string;
  normalized_local_datetime: string;
  normalized_utc_datetime: string;
  offset_minutes: number;
  ambiguous: boolean;
  fold: number;
  is_placeholder_time: boolean;
  placeholder_reason?: string | null;
};

export type RegionalSolarCorrectionSummary = {
  source_solar_datetime: string;
  corrected_solar_datetime: string;
  longitude: number;
  regional_time_offset_minutes: number;
  daylight_saving_offset_minutes: number;
  correction_basis: string;
  is_placeholder_time: boolean;
  placeholder_reason?: string | null;
};

export type BirthTimeContext = {
  legal_local_datetime: string;
  normalized_local_datetime: string;
  normalized_utc_datetime: string;
  timezone_id: string;
  utc_offset_minutes: number;
  dst_offset_minutes: number;
  normalized_solar_datetime: string;
  standard_local_datetime: string;
  mean_solar_datetime: string;
  legacy_corrected_solar_datetime: string;
  corrected_solar_datetime: string;
  longitude: number;
  standard_meridian: number;
  regional_time_offset_minutes: number;
  daylight_saving_offset_minutes: number;
  ambiguous: boolean;
  fold: number;
  warnings: string[];
};

export type CandidateChart = {
  candidate_id: string;
  time_basis: string;
  midnight_rule: string;
  input_datetime_to_lunar_python: string;
  day_pillar_basis_datetime: string;
  iljin_query_date: string;
  day_pillar_rule: string;
  year_pillar: string;
  month_pillar: string;
  day_pillar: string;
  hour_pillar: string;
  luck_cycle_start_age?: number | null;
  luck_cycle_start_age_years?: number | null;
  luck_cycle_start_age_months?: number | null;
  luck_cycle_start_age_total_months?: number | null;
  luck_cycle_first_ganzhi?: string | null;
  differences_from_primary: Record<
    string,
    {
      primary?: string | null;
      candidate?: string | null;
    }
  >;
  aliases: string[];
};

export type MansePillar = {
  key: "year" | "month" | "day" | "time";
  label: string;
  enabled: boolean;
  gan_zhi?: string | null;
  stem?: string | null;
  branch?: string | null;
  stem_element?: string | null;
  branch_element?: string | null;
  stem_ten_god?: string | null;
  branch_ten_god?: string | null;
  branch_ten_gods: string[];
  hidden_stems: string[];
  twelve_fortune?: string | null;
  twelve_shinsal?: string | null;
  na_yin?: string | null;
  xun?: string | null;
  xun_kong?: string | null;
};

export type MansePillarSet = {
  year: MansePillar;
  month: MansePillar;
  day: MansePillar;
  time: MansePillar;
};

export type ManseTableRow = {
  label: string;
  year: string;
  month: string;
  day: string;
  time: string;
};

export type ManseSpecialStarMatch = {
  pillar_key: "year" | "month" | "day" | "time";
  pillar_label: string;
  gan_zhi: string;
  stem: string;
  branch: string;
  matched_field: "stem" | "branch" | "gan_zhi" | "pair";
  matched_value: string;
  counterpart_pillar_key?: "year" | "month" | "day" | "time" | null;
  counterpart_pillar_label?: string | null;
  counterpart_gan_zhi?: string | null;
  counterpart_branch?: string | null;
};

export type ManseSpecialStar = {
  key: string;
  family: string;
  label: string;
  category: "auspicious" | "sinsal";
  tier: "S" | "A" | "B";
  scope: "core" | "expanded" | "optional";
  weight: number;
  method_id: string;
  basis_key: string;
  basis: string;
  anchor_value: string;
  target_values: string[];
  usage_summary: string;
  usage_keywords: string[];
  note?: string | null;
  active: boolean;
  count: number;
  matches: ManseSpecialStarMatch[];
};

export type ManseLuckCycle = {
  index: number;
  gan_zhi: string;
  start_year: number;
  end_year: number;
  start_age: number;
  end_age: number;
  start_age_years?: number | null;
  start_age_months?: number | null;
  start_age_total_months?: number | null;
  change_age_years?: number | null;
  change_age_months?: number | null;
  change_age_total_months?: number | null;
  start_datetime?: string | null;
  change_datetime?: string | null;
};

export type ManseSupplementaryPosition = {
  key: string;
  label: string;
  gan_zhi: string;
  na_yin: string;
};

export type ManseSupplementaryPositionSet = {
  tai_yuan: ManseSupplementaryPosition;
  ming_gong: ManseSupplementaryPosition;
  shen_gong: ManseSupplementaryPosition;
  tai_xi: ManseSupplementaryPosition;
};

export type ManseElementSummary = {
  wood: number;
  fire: number;
  earth: number;
  metal: number;
  water: number;
};

export type ManseElementPercentageSummary = {
  wood: number;
  fire: number;
  earth: number;
  metal: number;
  water: number;
};

export type ManseMeta = {
  schema_version: "v1";
  day_master: string;
  pillar_order: Array<"year" | "month" | "day" | "time">;
  visible_pillar_keys: Array<"year" | "month" | "day" | "time">;
  hour_pillar_enabled: boolean;
  day_pillar_rule: string;
  day_time_basis_datetime: string;
  civil_date: string;
  day_pillar_basis_date: string;
  iljin_query_date: string;
  day_pillar_source: string;
  day_pillar_reference_matched_lunar_python: string;
};

export type ManseAnalysisSummary = {
  visible_element_total: number;
  imbalance_gap: number;
  dominant_elements: Array<"wood" | "fire" | "earth" | "metal" | "water">;
  missing_elements: Array<"wood" | "fire" | "earth" | "metal" | "water">;
  element_percentages: ManseElementPercentageSummary;
  visible_ten_god_distribution: Record<string, number>;
  balance_score: number;
  internal_grade: "S" | "A" | "B" | "C";
  charm_score: number;
  wealth_score: number;
  career_score: number;
  leadership_score: number;
  first_luck_cycle_direction?: "forward" | "backward" | null;
  first_luck_cycle_exact_start_age_years?: number | null;
  first_luck_cycle_precise_start_age_years?: number | null;
  first_luck_cycle_start_age_years?: number | null;
  first_luck_cycle_start_age_months?: number | null;
  first_luck_cycle_start_age_total_months?: number | null;
  first_luck_cycle_boundary_datetime?: string | null;
};

export type ManseData = {
  meta: ManseMeta;
  pillars: MansePillarSet;
  table_rows: ManseTableRow[];
  elements: ManseElementSummary;
  analysis: ManseAnalysisSummary;
  luck_cycles_enabled: boolean;
  luck_cycles: ManseLuckCycle[];
  supplementary_positions: ManseSupplementaryPositionSet;
  special_stars: ManseSpecialStar[];
  notes: string[];
};

export type SajuResultSignals = {
  visible_pillar_keys: Array<"year" | "month" | "day" | "time">;
  visible_pillar_values: string[];
  dominant_elements: Array<"wood" | "fire" | "earth" | "metal" | "water">;
  missing_elements: Array<"wood" | "fire" | "earth" | "metal" | "water">;
  balance_score: number;
  charm_score: number;
  wealth_score: number;
  career_score: number;
  leadership_score: number;
  internal_grade: "S" | "A" | "B" | "C";
};

export type InterpretationNarrativeSection = {
  title: string;
  body: string;
  evidence_ids: string[];
};

export type InterpretationSummaryBlock = {
  headline: string;
  overview: string;
  confidence: "low" | "medium" | "high";
  evidence_ids: string[];
};

export type InterpretationAttemptDiagnostic = {
  attempt_index: number;
  mode: "generate" | "repair";
  token_budget: number;
  status: "success" | "json_invalid" | "validation_error" | "provider_error" | "skipped";
  response_id?: string | null;
  output_chars: number;
  output_excerpt?: string | null;
  error_type?: string | null;
  error_message?: string | null;
  issues: string[];
};

export type InterpretationDiagnostics = {
  configured_provider: string;
  final_provider: "openai" | "fallback";
  model?: string | null;
  prompt_version: string;
  payload_chars: number;
  duration_ms: number;
  final_response_id?: string | null;
  fallback_reason?: string | null;
  validation_issues: string[];
  attempts: InterpretationAttemptDiagnostic[];
};

export type InterpretationReport = {
  schema_version: "m2-llm-v5";
  provider: "openai" | "fallback";
  model?: string | null;
  prompt_version: string;
  summary: InterpretationSummaryBlock;
  core_analysis: InterpretationNarrativeSection;
  love: InterpretationNarrativeSection;
  career: InterpretationNarrativeSection;
  wealth: InterpretationNarrativeSection;
  luck_flow: InterpretationNarrativeSection;
  warnings: string[];
  diagnostics?: InterpretationDiagnostics | null;
};

export type FreePreviewDiagnosisKey = "strongest_point" | "repeating_pattern" | "current_task";

export type FreePreviewCardKey = "core" | "work_money" | "love" | "luck_flow";

export type FreePreviewDiagnosis = {
  key: FreePreviewDiagnosisKey;
  title: string;
  body: string;
};

export type FreePreviewCard = {
  key: FreePreviewCardKey;
  title: string;
  subtitle: string;
  chips: string[];
  preview_paragraphs: string[];
  user_takeaway: string;
  next_question: string;
  basis_line: string;
};

export type FreePreviewReport = {
  schema_version: "free-preview-v1";
  provider: "openai" | "fallback";
  model?: string | null;
  prompt_version: string;
  headline: string;
  hero_overview: string[];
  core_diagnoses: FreePreviewDiagnosis[];
  cards: FreePreviewCard[];
  warnings: string[];
  diagnostics?: InterpretationDiagnostics | null;
};

export type SajuPreviewResponse = {
  trace_id: string;
  response_mode: "preview";
  pipeline_status: PipelineStatus;
  region: RegionSuggestion;
  time_correction: TimeCorrectionSummary;
  regional_solar_correction: RegionalSolarCorrectionSummary;
  manse: ManseData;
  calendar_normalization: {
    calendar_type: "solar" | "lunar";
    is_lunar_leap_month: boolean;
    input_date: string;
    input_time: string;
    normalized_solar_datetime: string;
    normalized_lunar_datetime: string;
    solar_year: number;
    solar_month: number;
    solar_day: number;
    solar_hour: number;
    solar_minute: number;
    lunar_year: number;
    lunar_month: number;
    lunar_day: number;
    is_placeholder_time: boolean;
    placeholder_reason?: string | null;
  };
  result: {
    overview: string;
    strengths: string[];
    cautions: string[];
    love: string;
    career: string;
    wealth: string;
    action_advice: string;
    interpretation?: InterpretationReport | null;
    free_preview?: FreePreviewReport | null;
    limitations: string[];
    disabled_sections: string[];
    evidence_sections: Record<string, EvidenceSection>;
    calculation_basis: CalculationBasis;
    uncertainty_summary: UncertaintyFlag[];
    hour_pillar_enabled: boolean;
    signals: SajuResultSignals;
  };
  debug_trace?: {
    stage_order: string[];
    failed_stage?: string | null;
    checkpoints: Array<{
      stage: string;
      status: string;
      note?: string | null;
      error_code?: string | null;
    }>;
    request_echo: Record<string, string>;
    accuracy_mode?: AccuracyMode;
    calculation_basis?: CalculationBasis;
    birth_time_context?: BirthTimeContext | null;
    year_month_boundary_context?: Record<string, unknown>;
    candidate_charts?: CandidateChart[];
    uncertainty_flags?: UncertaintyFlag[];
  } | null;
};

export type SajuFreeDetailResponse = {
  trace_id: string;
  response_mode: "free_detail";
  pipeline_status: PipelineStatus;
  interpretation: InterpretationReport;
  detail_report: InterpretationReport;
  debug_trace?: SajuPreviewResponse["debug_trace"];
};

export type SajuDetailType =
  | "love_timing"
  | "ideal_partner"
  | "wealth_timing"
  | "career_timing"
  | "yearly_caution"
  | "monthly_flow"
  | "relationship_support"
  | "health_condition"
  | "compatibility_compare";

export type SajuDetailPreparedReport = {
  schema_version: "saju-detail-v1";
  report_id: string;
  input_hash: string;
  prepared_at: string;
  base_context: Record<string, unknown>;
  detail_analysis_bundle: Record<string, Record<string, unknown>>;
};

export type SajuDetailPeriod = {
  label: string;
  period: string;
  description: string;
};

export type SajuDetailRenderedReport = {
  schema_version: "saju-detail-render-v1";
  detail_type: SajuDetailType;
  title: string;
  summary: string;
  body: {
    conclusion: string;
    periods: SajuDetailPeriod[];
    cautions: string[];
    advice: string[];
    basis_chips: string[];
  };
};

export type SajuDetailPrepareResponse = {
  trace_id: string;
  response_mode: "detail_prepare";
  report_id: string;
  input_hash: string;
  cached: boolean;
  available_detail_types: SajuDetailType[];
  bundle: SajuDetailPreparedReport;
};

export type SajuDetailRenderResponse = {
  trace_id: string;
  response_mode: "detail_render";
  report_id: string;
  input_hash: string;
  detail_type: SajuDetailType;
  provider: "openai" | "fallback";
  model?: string | null;
  prompt_version: string;
  cached: boolean;
  report: SajuDetailRenderedReport;
  warnings: string[];
};
