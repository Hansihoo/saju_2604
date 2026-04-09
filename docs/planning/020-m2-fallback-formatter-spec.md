# M2 Fallback Formatter Spec 020

## Purpose
- Put a provider-agnostic formatter on top of the M2 payload.
- Keep the current interpretation step usable before an external LLM provider is connected.
- Make the eventual provider swap small: payload stays, formatter implementation changes.

## Scope
- Input: `InterpretationPayload`
- Output: `InterpretationNarrative`
- Locale support:
  - `ko`
  - `en`

## Rules
- Use only payload facts.
- Do not recalculate pillars, elements, or luck cycles.
- Keep wording grounded and compact.
- Preserve limitation notices such as estimated birth time.
- Treat this formatter as a fallback and validation tool, not the final expressive layer.

## Current Components
- Payload schema:
  - `apps/api/app/domain/saju/llm_payload.py`
- Narrative schema:
  - `apps/api/app/domain/saju/interpretation.py`
- Payload builder:
  - `apps/api/app/domain/saju/services/build_interpretation_payload.py`
- Fallback formatter:
  - `apps/api/app/domain/saju/services/format_interpretation_fallback.py`
- Dev render tool:
  - `python -m app.tools.render_interpretation_preview --calendar-type solar --birth-date 2024-02-10 --birth-time 10:30 --gender male --region-id kr-seoul --locale ko`

## Why this layer exists
- The frontend should not invent interpretation logic from raw numbers forever.
- The backend needs a stable place to validate narrative composition before connecting a real model.
- Tests can now verify:
  - payload generation
  - fallback narrative generation
  - policy limitation propagation

## Next Step
- Define the provider interface for the future LLM layer.
- Keep the fallback formatter as the baseline implementation and regression oracle.
