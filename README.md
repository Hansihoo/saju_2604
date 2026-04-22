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
```

## Current status

Implemented backend pipeline:

- region search
- time correction
- solar/lunar normalization
- `lunar-python` engine adapter
- estimated birth-time policy
- deterministic baseline analysis
- debug trace and stage logging

Not finished yet:

- LLM phrasing layer
- final result UI polish
- persistent storage
- deployment automation
