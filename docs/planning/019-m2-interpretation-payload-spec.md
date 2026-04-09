# M2 Interpretation Payload Spec 019

## Purpose
- Define a stable internal payload that the future LLM layer will receive.
- Keep calculation and interpretation separated:
  - facts are produced by code
  - wording is produced by the LLM

## Design Rules
- The payload must contain only code-derived facts and policy notes.
- The payload must not depend on developer-oriented prose from the preview response.
- The payload must be serializable so it can be dumped, logged, tested, and reused.

## Payload Shape

### Top-level
- `schema_version`
- `facts_only`
- `output_sections`
- `profile`
- `time_context`
- `visible_pillars`
- `day_master`
- `element_counts`
- `ten_god_stems`
- `signals`
- `evidence`
- `luck_cycles`
- `supplementary_positions`
- `limitations`
- `disabled_sections`
- `notes`
- `narrative_rules`
- `prompt_seed`

### Why these fields exist
- `profile`: preserves user input intent and region context
- `time_context`: preserves the normalization and correction facts
- `visible_pillars`, `day_master`, `element_counts`, `ten_god_stems`: core saju facts
- `signals`: compact analysis values for summary generation
- `evidence`: short factual summaries that can ground generated text
- `luck_cycles`: decade-flow facts for future long-form interpretation
- `limitations`, `disabled_sections`, `notes`: make policy constraints explicit

## Current Usage
- M2 payload is internal only for now
- It can be dumped via:
  - `python -m app.tools.dump_interpretation_payload --calendar-type solar --birth-date 2024-02-10 --birth-time 10:30 --gender male --region-id kr-seoul`

## Validation
- Payload creation is covered by unit tests
- It reuses the already validated preview pipeline
- Golden answer validation remains the source of truth for calculation correctness

## Next Step
- Build the future LLM formatter on top of this payload instead of raw API strings
- Keep a fallback formatter available so payload changes can be validated before provider integration
