# Saju project agent instructions

Read `docs/PROJECT_STATUS.md`, `docs/CODEX_RUNBOOK.md`, and the relevant planning document before changes.

For any calculation, interpretation, prompt, result, or sharing change, also read
[`docs/ai/SAJU_READING_AGENT.md`](docs/ai/SAJU_READING_AGENT.md).
That document defines the fact/rule/claim boundary and required output roles.

For question, entry, recommendation, result-copy, UX or product-planning changes, also read
[`docs/ai/PRODUCT_CONTENT_KNOWLEDGE.md`](docs/ai/PRODUCT_CONTENT_KNOWLEDGE.md) and its JSON policy.
Preserve direct user feedback: future relationships/employment are primary interests; do not
restore personality/type hooks or substitute personality readings for unsupported timing answers.

For verification-agent changes, also read `docs/ai/CODEX_AGENT_VERIFICATION.md`.
Keep role jobs independently runnable and preserve the module import boundaries.

- Keep calculation and judgment on the backend; the frontend renders supplied results.
- Preserve the primary calculation policy in `docs/planning/033-current-calculation-rules.md`.
- A project interpretation policy is not an expert-approved rule or an empirically validated prediction.
- Do not turn heuristic scores into probabilities, percentiles, or favorable event dates.
- Changes to knowledge, reasoning rules, and wording must be versioned independently.
- Run relevant tests and the fallback-only user-story verifier; never use a paid provider merely to validate local changes.
- Update `docs/PROJECT_STATUS.md` and `docs/ai/WORK_LOG.md` with completed work and remaining verification gaps.
