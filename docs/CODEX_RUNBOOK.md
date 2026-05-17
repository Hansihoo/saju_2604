# Codex Runbook

This file explains the safest way to run the project from Codex Desktop or any restricted Windows shell.

## Quick rules

- Prefer managed background commands when Codex is asked to run the project.
- Do not start the backend with `uvicorn --reload` inside Codex unless you have already confirmed the shell can create Windows named pipes.
- If `pnpm dev` is used from Codex, the launcher now auto-disables backend reload, but `pnpm dev:bg:start` is still the safer default.

## Recommended commands

From the repository root:

```powershell
pnpm dev:bg:start
pnpm dev:bg:status
pnpm dev:bg:stop
```

Use these when Codex needs to start, verify, and later stop the services without holding the terminal open.

If a human is running the project in a normal terminal, this is still fine:

```powershell
pnpm dev
```

For regression and accuracy checks:

```powershell
pnpm ensure:skyfield
pnpm test:api
pnpm test:accuracy
pnpm verify:kasi
```

`pnpm ensure:skyfield` downloads and verifies the Skyfield `de440s.bsp` ephemeris before runtime. Normal API requests do not download this file.

`pnpm verify:kasi` requires `KASI_SERVICE_KEY` and is an explicit live API spot check, not a normal test step.

## What each command does

- `pnpm dev:bg:start`
  Starts API and web as managed background processes and writes metadata/logs to `.dev-runtime/`.
- `pnpm dev:bg:status`
  Reports whether the managed API and web processes are running and healthy.
- `pnpm dev:bg:stop`
  Stops only the managed processes started by `pnpm dev:bg:start`.
- `pnpm dev`
  Starts the normal local development launchers. In Codex shells it automatically disables backend reload.
- `pnpm dev:api`
  Starts only the API launcher.
- `pnpm dev:web`
  Starts only the web launcher.
- `pnpm dev:api:direct`
  Runs the FastAPI server in the current shell without reload. Useful for manual debugging.
- `pnpm dev:api:reload`
  Runs the FastAPI server with reload. Use this only in a normal local shell.
- `pnpm dev:web:direct`
  Runs the Vite server in the current shell. Useful for manual debugging.
- `pnpm test:api`
  Ensures the Skyfield ephemeris, then runs API compile and unittest discovery with the LLM provider forced to fallback.
- `pnpm test:accuracy`
  Runs API tests, web build, reference table checks, diagnostic report generation, and golden validation.
- `pnpm ensure:skyfield`
  Downloads `de440s.bsp` if missing and verifies file size and SHA256.
- `pnpm verify:kasi`
  Runs selected live KASI API spot checks against the checked-in lunar reference table.

## Verification checklist

After startup, verify:

- API health: `http://127.0.0.1:8000/health`
- API docs: `http://127.0.0.1:8000/docs`
- Web: `http://127.0.0.1:5173`

Expected API health response includes:

- `status: "ok"`
- `service: "suju-insight"`

## Known failure mode

In Codex Desktop on Windows, `uvicorn --reload` can fail with repeated errors similar to:

```text
PermissionError: [WinError 5] Access is denied
```

When that happens, the reloader may keep writing tracebacks and rapidly grow `apps/api/uvicorn.stderr.log`.

## Recovery steps

1. Run `pnpm dev:bg:stop`.
2. Delete or truncate `apps/api/uvicorn.stderr.log` if it became very large from an older failed run.
3. Restart the managed services with `pnpm dev:bg:start`.
4. Check health with `pnpm dev:bg:status`.

## Instructions for future Codex runs

When asking Codex to run the project, point it to this file and ask it to use `pnpm dev:bg:start` first. Foreground commands such as `pnpm dev:api:direct` and `pnpm dev:web:direct` should be reserved for short manual debugging sessions.

Suggested prompt:

```text
Read docs/CODEX_RUNBOOK.md first, then run the project using the Codex-safe commands from that file.
```
