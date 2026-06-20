# suju-insight

Saju web service workspace with a React frontend and a FastAPI backend.

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
```

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

Not finished yet:

- final result UI polish
- persistent storage
- production domain wiring
