# START_HERE

## What This Project Is

`suju-insight` is an AI-assisted saju reading web service.

The service calculates the saju/manse result from user input first, then uses an LLM only to turn verified facts into readable language. The product direction is a calm document-style personal reading, not a dashboard simulator.

## Current Product Direction

- User enters birth date, birth time, gender, and birth region.
- Backend corrects time and region information before interpretation.
- Code owns calculation, analysis signals, and judgment.
- LLM owns phrasing only.
- The live result UI uses an essay/document-style layout.
- `/design-lab` compares document-style layouts using a fixed saved result.

## Provider Policy

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
SAJU_CODEX_SANDBOX=read-only
```

Codex mode is for personal local testing only. It is not the production default.

## Where To Read Next

- `README.md`: setup, local execution, deployment, and provider settings.
- `docs/PROJECT_PROFILE.md`: product identity, principles, current defaults, and risks.
- `docs/PROJECT_STATUS.md`: current feature progress.
- `docs/ai/WORK_LOG.md`: recent AI-assisted implementation log.
- `docs/CODEX_RUNBOOK.md`: Codex-safe local development workflow.
- `docs/planning/`: planning history and domain decisions.

## Recent Notable Changes

- Added local Codex CLI provider as an optional local phrasing path.
- Kept OpenAI API as the production-oriented default provider.
- Added deterministic fallback mode for no-LLM/no-cost testing.
- Added `/design-lab` with fixed-result document design variants.
- Applied the essay-style document layout to the live result page.
- Replaced internal UI terms such as "핵심 카드" with user-facing reading labels.
