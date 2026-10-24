import type { SajuPreviewResponse } from "./contracts";

export type QuestionVersions = Record<string, string>;
export type SajuCharacteristic = {
  id: string;
  direction: "advantage" | "burden";
  title: string;
  conclusion: string;
  reason: string;
  condition: string;
  emphasis: "prominent" | "noticeable" | "supporting";
  emphasis_label: string;
  emphasis_reason: string;
  memo_body: string;
};
export type SajuChartCharacteristics = {
  status: "available" | "conditional" | "blocked_calculation" | "no_matching_rules";
  assumption: string;
  scale_note: string;
  items: SajuCharacteristic[];
  comparisons: Array<{
    label: string; chart: Record<string, string>; items: SajuCharacteristic[];
    unchanged: string[]; changed: string[]; added: string[]; removed: string[];
  }>;
  versions: Record<string, string>;
};
export type SajuQuestionOption = {
  id: string;
  category: "core" | "love" | "wealth" | "career" | "luck_flow";
  title: string;
  description: string;
  requires_context: boolean;
  context_options: Array<{ id: string; label: string }>;
};
export type SajuQuestionFlow = {
  as_of: string;
  versions: QuestionVersions;
  questions: SajuQuestionOption[];
  notices: string[];
};
export type SajuBasicReading = {
  as_of: string;
  title: string;
  headline: string;
  sections: Array<{ id: string; title: string; text: string; fact_ids: string[] }>;
  memo_sections?: Array<{ id: string; title: string; text: string; fact_ids: string[] }>;
  limitations?: string[];
  memo: { facts: string[]; reading: string };
  notices: string[];
  facts: Array<{ id: string; label: string; value: unknown; source_path: string }>;
  source_context: Record<string, unknown>;
  versions: Record<string, string>;
  provider: "deterministic";
};
export type SajuBasicResponse = SajuPreviewResponse & {
  question_flow: SajuQuestionFlow;
  basic_reading: SajuBasicReading;
  category_reading?: {
    sections: Array<{ id: SajuQuestionOption["category"]; title: string; body: string; memo_body: string;
      status: "existing_interpretation" | "blocked_calculation" | "needs_rule_review";
      information?: Array<{ id: string; title: string; body: string; kind: "calculation_description" | "traditional_term_definition"; provisional: boolean; fact_ids: string[] }>;
      visible?: boolean;
      publication?: {
        version: string;
        scope: "natal_structure" | "conditional_natal_structure" | "supported_reading_excerpt" | "conditional_traditional_themes" | "traditional_themes" | "provisional_information" | "calculation_information" | "traditional_information" | "unavailable";
        blocks: Array<{ id: string; kind: "interpretation" | "structural_reading" | "traditional_definition" | "traditional_theme" | "calculation_summary" | "heading" | "availability_notice"; title: string; text: string }>;
        memo_body: string;
        notice: string;
      } }>;
    provider: "codex" | "openai" | "fallback" | "deterministic";
    format: string;
    copy_version: string;
    source_context: Record<string, unknown>;
    characteristics?: SajuChartCharacteristics | null;
    calculation_notices?: string[];
    notices: string[];
  };
};
export type SajuQuestionResponse = {
  as_of: string;
  trace_id: string;
  response_mode: "question";
  question_id: string;
  question: string;
  title: string;
  answer: string;
  sections: Array<{ id: string; title: string; text: string; kind?: "reading" | "memo" }>;
  memo: { facts: string[]; reading: string };
  notices: string[];
  facts: Array<{ id: string; label: string; value: unknown; source_path: string }>;
  source_context: Record<string, unknown>;
  versions: QuestionVersions;
  provider: "deterministic";
  cached: boolean;
  followups?: SajuQuestionOption[];
};
