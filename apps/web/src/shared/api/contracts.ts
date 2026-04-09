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

export type SajuPreviewRequest = {
  calendar_type: "solar" | "lunar";
  birth_date: string;
  birth_time: string;
  is_birth_time_estimated: boolean;
  is_lunar_leap_month: boolean;
  gender: "male" | "female";
  region_id: string;
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
};

export type EvidenceSection = {
  title: string;
  status: "ready" | "disabled" | "coming_soon";
  summary: string;
};

export type TimeCorrectionSummary = {
  tzid: string;
  source_local_datetime: string;
  normalized_local_datetime: string;
  normalized_utc_datetime: string;
  offset_minutes: number;
  ambiguous: boolean;
  fold: number;
};

export type RegionalSolarCorrectionSummary = {
  source_solar_datetime: string;
  corrected_solar_datetime: string;
  longitude: number;
  regional_time_offset_minutes: number;
  daylight_saving_offset_minutes: number;
  correction_basis: string;
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

export type ManseLuckCycle = {
  index: number;
  gan_zhi: string;
  start_year: number;
  end_year: number;
  start_age: number;
  end_age: number;
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
  };
  result: {
    overview: string;
    strengths: string[];
    cautions: string[];
    love: string;
    career: string;
    wealth: string;
    action_advice: string;
    limitations: string[];
    disabled_sections: string[];
    evidence_sections: Record<string, EvidenceSection>;
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
  } | null;
};
