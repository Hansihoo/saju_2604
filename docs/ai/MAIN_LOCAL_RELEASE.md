# Main publication and local Codex runtime

Date: 2026-10-05. The user requested remote `main` publication and local
`gpt-6.1-sol` / `xhigh` operation. This explicitly supersedes the earlier local
model-switch hold; it does not change the production OpenAI API default.

## Scope

- Publish the accumulated character, mobile reading, analysis-note, knowledge,
  question-policy and independently runnable verifier changes.
- Pin project CLI `@openai/codex` to `0.160.0`. Prefer the installed project CLI
  over the global `0.144.1` CLI without changing global Codex preferences.
- Forward `SAJU_CODEX_REASONING_EFFORT` to the CLI. The local launcher explicitly
  selects `gpt-6.1-sol`, `xhigh`, read-only and a 600-second timeout.
- Provide `pnpm dev:codex` and an ignored local profile. Limit local generation
  attempts to one and disable repair. No API key is required for this account path;
  it consumes the signed-in Codex account's allowance.

## Confirmed checks

| Check | Result |
| --- | --- |
| Final API regression suite, fallback provider | 390 passed in 164.372s |
| New Codex command/settings tests | 3 passed |
| Web TypeScript and production build | Passed |
| Web reading helper checks | 12 passed |
| Fallback-only HTTP user-story verifier | 456 PASS / 3 WARN / 1 existing FAIL |
| Project CLI catalog, no model generation | GPT-6.1 Sol and xhigh available; CLI 0.160.0 |
| Local runtime health | Web 5173 and API 8000 running; provider endpoint confirms codex |
| Requested live Codex saju generation | HTTP 200; actual provider/model codex/gpt-6.1-sol; one successful attempt; response schema passed; 277.141s |
| Remote main | New local main created; commit/push pending |

The HTTP failure remains `known_issue.valid_lunar_day30`: the valid lunar date
1990-02-30 is rejected by Gregorian-shaped request validation. It predates this
publication and was deliberately kept visible. The three warnings require review
of an unobservable ten-god value, actual user interest and live LLM meaning.
Passing contracts do not establish event-prediction accuracy or user interest.

The live request used the synthetic Seoul fixture and configured `xhigh`. Provider
diagnostics report no validation issues and four rendered cards. Its first smoke
harness incorrectly asserted a nonexistent envelope `success` field; the original
receipt is retained and the saved response was validated against the real
`SajuPreviewResponse` schema and successful pipeline stage without another model
call. This is an execution/contract check, not an independent semantic review.

The final full-suite rerun exposed an old test assumption: a detail-render test
expected the unspecified-model placeholder while reading the new local model.
The test now explicitly pins its unspecified-model condition. The affected test
and three Codex settings tests passed; the final full-suite rerun passed all 390
tests. Earlier failing test output remains in the retained evidence directory.

## Run locally

```powershell
cd D:\5_project\saju_2604
pnpm install
# If the local Codex account is not signed in:
pnpm exec codex login
pnpm dev:codex
pnpm dev:bg:status
```

Open `http://127.0.0.1:5173/`. API health is `http://127.0.0.1:8000/health`.
`pnpm dev:bg:stop` stops the managed services when the user wants to stop them.
The higher effort can increase wait time and Codex account usage.

## Retained evidence

`.dev-runtime/main-local-20261005/` retains the API/build logs, CLI catalog,
fallback HTTP results, selected local configuration and the one requested live
request/result receipt. This root and the ignored local profile are registered as
preserved artifacts for the owning thread. They are excluded from Git publication.
No credentials or raw reasoning are copied into repository documents.
