# START_HERE

## What This Project Is

`suju-insight` is an AI-assisted saju reading web service.

The service calculates the saju/manse result from user input first, then uses an LLM only to turn verified facts into readable language. The live mobile experience starts with a character and one reading button, with the included topics listed below, followed by compact input, result topic navigation, and a share card.

## Current Product Direction

- User taps `운세 보기`, then enters birth date, birth time, gender, and birth region. Today, love, work/money and luck-cycle topics are informational on entry; selection happens in the result. Personality remains supporting result content.
- Backend corrects time and region information before interpretation.
- Code owns calculation, analysis signals, and judgment.
- LLM owns phrasing only.
- A new reading opens today first; topic navigation uses the same received result. Today's reading uses existing period-flow calculations and shows the applicable date. Birthplace is required; current residence is not collected.
- The full reading remains available through an explicit button.
- `/design-lab` compares document-style layouts using a fixed saved result.

## Provider Policy

Local explicit commands: `pnpm dev:openai` (GPT-5.4/low) or
`pnpm dev:codex` (gpt-6.1-sol/xhigh). Use `pnpm check:llm:openai` /
`pnpm check:llm:codex` for a credential-safe readiness check without inference.
The launchers check readiness before replacing services and restore caller settings.
Both paths use the same validated reading/publication contract; stored-output replay
does not constitute a live API test. See [071](planning/071-dual-provider-execution.md).

Production default:

```powershell
SAJU_LLM_PROVIDER=openai
OPENAI_API_KEY=...
```

Local no-OpenAI-cost test modes:

```powershell
SAJU_LLM_PROVIDER=fallback
```

or:

```powershell
SAJU_LLM_PROVIDER=codex
SAJU_CODEX_COMMAND=codex.cmd
SAJU_CODEX_MODEL=gpt-6.1-sol
SAJU_CODEX_REASONING_EFFORT=xhigh
SAJU_CODEX_TIMEOUT_SECONDS=600
SAJU_CODEX_SANDBOX=read-only
```

Codex mode is for personal local testing only. It is not the production default.

## Where To Read Next

- `docs/planning/042-context-aware-love-readings.md`: direct feedback about single users receiving couple advice; situation/intent contracts, timing-data requirements and release gates. Design only; current generic love output is not yet replaced.

- `docs/planning/039-fortune-index-design.md`: proposed period/topic fortune index; current static-score limitations, rule/scale requirements and verification. Design only; numeric output is not enabled.
- `docs/planning/040-mobile-reading-design-review.md`: quiet Reading memo disclosure, design sources, next visual priorities, and current verification gaps.
- `docs/planning/041-honest-waiting-progress.md`: request-scoped actual stages, heartbeats and elapsed time for long readings; no extra generation or estimated percentages.
- `docs/ai/PRODUCT_CONTENT_KNOWLEDGE.md` and JSON: required direct-user-feedback policy; rejected personality hooks, future-question priorities and regression gates.
- `docs/ai/API_COST_REVIEW.md`: pre-deployment call/pricing/input review; actual production configuration and token usage remain unconfirmed, with cost-reduction recommendations.

- `docs/planning/038-interest-led-reading-experience.md`: current interest-only product plan, phased implementation, module ownership and verification criteria.
- `docs/ai/COMPETITOR_GROWTH_RESEARCH.md`: sourced research on consumer fortune service growth, product hypotheses, and supported question/content priorities.
- `docs/ai/SAJU_READING_AGENT.md`: required agent contract for calculated facts, knowledge rules, reading roles, and validation.
- `docs/planning/036-knowledge-backed-question-readings.md`: question capabilities, knowledge storage decision, and unsupported timing/comparison boundaries.
- `docs/ai/CODEX_AGENT_VERIFICATION.md`: independent role jobs, module ownership, CLI commands, execution limits, verification evidence and remaining gaps.
- `docs/planning/037-codex-three-agent-verification.md`: Codex-based user/query/supervisor design and implementation scope.

- `README.md`: setup, local execution, deployment, and provider settings.
- `docs/PROJECT_PROFILE.md`: product identity, principles, current defaults, and risks.
- `docs/PROJECT_STATUS.md`: current feature progress.
- `docs/ai/WORK_LOG.md`: recent AI-assisted implementation log.
- `docs/CODEX_RUNBOOK.md`: Codex-safe local development workflow.
- `docs/planning/`: planning history and domain decisions.
- `docs/planning/035-topic-first-reading.md`: birthplace reasoning, topic mapping, and current flow verification.
- `docs/ai/USER_STORY_VERIFICATION.md`: independent information/UX audits, runtime evidence, repeatable checks, and unresolved defects.

## Recent Notable Changes

- Added local Codex CLI provider as an optional local phrasing path.
- Kept OpenAI API as the production-oriented default provider.
- Added deterministic fallback mode for no-LLM/no-cost testing.
- Added `/design-lab` with fixed-result document design variants.
- Applied the essay-style document layout to the live result page.
- Replaced internal UI terms such as "핵심 카드" with user-facing reading labels.
