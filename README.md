# suju-insight

Saju web service workspace with a React frontend and a FastAPI backend.

## Project overview

`suju-insight` is an AI-assisted saju reading service.

The product receives a user's birth date, birth time, gender, and birth region, then:

1. corrects the time and region data,
2. calculates the saju/manse result,
3. builds deterministic analysis signals in code,
4. uses an LLM only as a phrasing layer,
5. renders the result as a document-style personal reading.

Core product rule:

```text
Facts and judgment live in code. The LLM only rewrites verified facts into readable language.
```

For the full product profile, see [docs/PROJECT_PROFILE.md](docs/PROJECT_PROFILE.md).

## Documentation map

- [README.md](README.md): setup, local development, deployment, and provider settings.
- [docs/PROJECT_PROFILE.md](docs/PROJECT_PROFILE.md): product identity, principles, scope, risks, and defaults.
- [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md): current feature-level progress ledger.
- [docs/ai/WORK_LOG.md](docs/ai/WORK_LOG.md): recent AI-assisted implementation log.
- [docs/operations/PUBLIC_BETA_RUNBOOK.md](docs/operations/PUBLIC_BETA_RUNBOOK.md): public-beta environment, privacy, WAF, and observation checklist.
- [docs/CODEX_RUNBOOK.md](docs/CODEX_RUNBOOK.md): Codex-safe local development workflow.
- [docs/planning/](docs/planning/): planning history and domain decisions.
- [docs/delivery/](docs/delivery/): implementation handoff and delivery logs.

## Recent changes

- Added a local Codex CLI phrasing provider for personal local testing.
- Kept `openai` as the default and production-oriented LLM provider.
- Added `/design-lab` to compare document-style result layouts without calling any LLM.
- Applied the essay/document-style result layout to the live service result page.
- Reworded internal UI labels such as "핵심 카드" into user-facing reading labels.
- Softened result CTA/button styling so the reading feels more like a document than an app simulator.
- Split the initial free preview from the lazy full interpretation so one user flow does not generate the full report twice.
- Kept heuristic scores internal, added PII-safe request logging defaults, and bounded detail caches for public-beta preparation.

## Structure

```text
apps/
  api/   FastAPI backend
  web/   React + Vite frontend
docs/
  planning/
  delivery/
scripts/
  dev.ps1
  dev-common.ps1
  start-dev-background.ps1
  stop-dev-background.ps1
  status-dev-background.ps1
  run-api.ps1
  test-api.ps1
```

## Requirements

- Node.js 20+
- pnpm 9+
- Python 3.8+

## One-command local development

From the repository root:

```powershell
pnpm dev
```

This opens two PowerShell windows:

- API: `http://127.0.0.1:8000`
- API docs: `http://127.0.0.1:8000/docs`
- Web: `http://127.0.0.1:5173`

`pnpm dev` now auto-detects Codex Desktop / sandbox shells and starts the backend without `--reload` to avoid the Windows named-pipe permission loop that can fill `uvicorn.stderr.log`.

## Codex-safe background development

From the repository root:

```powershell
pnpm dev:bg:start
pnpm dev:bg:status
pnpm dev:bg:stop
```

This is the recommended path for Codex Desktop and other restricted shells.

- `pnpm dev:bg:start` starts API and web in managed background processes.
- `pnpm dev:bg:status` shows whether the managed services are running and healthy.
- `pnpm dev:bg:stop` stops only the managed services that were started by the background launcher.

Managed logs and process metadata are stored in `.dev-runtime/`.

You can also start only one side:

```powershell
pnpm dev:api
pnpm dev:web
```

If you only want the original foreground Vite command:

```powershell
pnpm dev:web:direct
```

Direct API startup commands:

```powershell
pnpm dev:api:direct
pnpm dev:api:reload
```

`pnpm dev:api:reload` is for a normal local terminal. In Codex / sandbox shells it fails fast instead of trying to start the unsafe reloader.

For a Codex-safe runbook, see [docs/CODEX_RUNBOOK.md](docs/CODEX_RUNBOOK.md).

## API setup

The backend launcher uses `apps/api/.venv/Scripts/python.exe` when it exists, otherwise it falls back to `python`.

Recommended first-time setup:

```powershell
cd apps/api
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

## Backend verification

From the repository root:

```powershell
pnpm test:api
```

This runs:

- `python -m compileall app`
- `python -m unittest discover -s tests -p "test_*.py"`

## Testing without OpenAI API usage

You can test most of the project without spending OpenAI API credits.

Use one of these local modes:

```powershell
SAJU_LLM_PROVIDER=fallback
```

This uses the deterministic formatter only. It is the fastest and has no LLM/API cost.

```powershell
SAJU_LLM_PROVIDER=codex
SAJU_CODEX_COMMAND=codex.cmd
SAJU_CODEX_MODEL=gpt-5.4
SAJU_CODEX_TIMEOUT_SECONDS=180
SAJU_CODEX_SANDBOX=read-only
```

This uses the local Codex CLI from the backend process. It is intended for Theo's personal local testing and does not require `OPENAI_API_KEY` in this project. It depends on a working local Codex login/config and can be slower than direct API calls.

The `/design-lab` route also uses a fixed saved result fixture, so it does not call OpenAI API or Codex at all:

```text
http://127.0.0.1:5173/design-lab
```

Production should keep:

```powershell
SAJU_LLM_PROVIDER=openai
OPENAI_API_KEY=...
```

## Vercel deployment

This repository is configured as a Vercel Services project:

- Web service: `apps/web`, mounted at `/`
- API service: `apps/api/main.py`, mounted at `/api`
- Production URL: `https://saju2604.vercel.app`

When importing `https://github.com/Hansihoo/saju_2604.git` into Vercel, set the project Framework Preset to `Services`. Vercel reads the service routing from `vercel.json`, so the frontend can call the backend with the production value below:

```powershell
VITE_API_BASE_URL=/api
```

The backend routes are declared without the `/api` prefix because Vercel strips the service route prefix before forwarding requests. For example, the deployed health check is available at `/api/health`, while the FastAPI route remains `/health`.

Recommended preflight before deploying:

```powershell
corepack pnpm install --frozen-lockfile
corepack pnpm --filter web build
powershell -ExecutionPolicy Bypass -File .\scripts\test-api.ps1
```

Optional production backend environment variables:

```powershell
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5.4
SAJU_LLM_PROVIDER=openai
SAJU_CORS_ORIGINS=https://your-production-domain.example
SAJU_LLM_STORE=0
SAJU_LLM_MAX_ATTEMPTS=1
SAJU_LLM_TIMEOUT_SECONDS=45
SAJU_LLM_ALLOW_REPAIR=0
SAJU_REQUEST_LOG_ENABLED=0
SAJU_REQUEST_LOG_INCLUDE_INPUT=0
SAJU_DETAIL_CACHE_TTL_SECONDS=900
SAJU_DETAIL_CACHE_MAX_ENTRIES=128
SAJU_INTERNAL_DEBUG_TOKEN=<long-random-secret>
SAJU_USE_CANONICAL_YEAR_MONTH_PILLARS=0
```

Before making the project public, follow the staged WAF and observation procedure in [docs/operations/PUBLIC_BETA_RUNBOOK.md](docs/operations/PUBLIC_BETA_RUNBOOK.md). The WAF publish step is intentionally a manual Vercel-owner action.

`OPENAI_API_KEY` is only needed for the OpenAI API phrasing layer. Without it, the API keeps returning the deterministic fallback interpretation.

Local Codex CLI phrasing option:

```powershell
SAJU_LLM_PROVIDER=codex
SAJU_CODEX_COMMAND=codex.cmd
SAJU_CODEX_MODEL=gpt-5.4
SAJU_CODEX_TIMEOUT_SECONDS=180
SAJU_CODEX_SANDBOX=read-only
```

Codex mode is intended for personal local use. It calls `codex exec` from the backend process, uses the local Codex login/config, and falls back to the deterministic formatter if the CLI is unavailable, times out, or returns invalid JSON.

Do not use Codex mode as the production default. The application default is still `openai`:

```python
SAJU_LLM_PROVIDER=openai
```

## Environment

Frontend:

```powershell
VITE_API_BASE_URL=/api
```

Backend:

```powershell
SAJU_APP_NAME=suju-insight
SAJU_API_VERSION=0.1.0
SAJU_CORS_ORIGINS=http://localhost:5173
SAJU_LLM_PROVIDER=openai|codex|fallback
```

## Current status

Implemented backend pipeline:

- region search
- time correction
- solar/lunar normalization
- `lunar-python` engine adapter
- estimated birth-time policy
- deterministic baseline analysis
- OpenAI API, local Codex CLI, and deterministic fallback phrasing providers
- debug trace and stage logging
- document-style result design lab
- essay/document-style live result layout

Not finished yet:

- persistent storage
- production domain and environment hardening
