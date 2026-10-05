# Independent verification modules

Read the project root AGENTS.md, docs/ai/SAJU_READING_AGENT.md and docs/ai/CODEX_AGENT_VERIFICATION.md.
Read docs/ai/PRODUCT_CONTENT_KNOWLEDGE.md and its JSON before changing question-fit or voice criteria.

- A single agent can own one module or one saved role job. Do not require another live agent.
- Only calculation_adapter.py imports the saju domain. cli.py may capture app settings once.
- contracts.py, jobs.py, checks.py, storage.py, runner.py and transports.py cannot import HTTP,
  application configuration, calculation services or production generation/repair functions.
- Workers return results; they never invoke another role. Composition belongs to runner.py.
- Do not add automatic retries inside a transport. Every attempt reserves one shared call slot.
- Preserve fixture/live, content/UI, synthetic/real-user and code/semantic distinctions.
- Missing reviews stay HOLD, incorrect facts stay FAIL, execution failure stays ERROR.
- Verify changes with tests.test_agent_verification; mock Codex process calls. Paid inference is
  an explicit evaluation command, not a development test.
