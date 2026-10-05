# Verification implementation results

Independent artifact-based role execution is implemented. Actual Codex inference was not invoked.

| Verification | Result |
| --- | --- |
| API regression checkpoint | 379 tests passed |
| Final agent regression | 41 tests passed |
| Actual engine + fixture smoke | 3 cases, 9 fixture calls; HOLD |
| Standalone supervisor | 1 fixture call; output contract passed |
| Expanded cases | 15 fixture calls; S1-S5 HOLD, known lunar S6 FAIL |
| Existing fallback HTTP verifier | 456 PASS / 3 WARN / 1 known lunar FAIL |
| Actual Codex inference | 0 calls; semantic accuracy not observed |

## Fixed case outcomes

| Case | Status |
| --- | --- |
| S1 | HOLD |
| S2 | HOLD |
| S3 | HOLD |
| S4 | HOLD |
| S5 | HOLD |
| S6 | FAIL |

HOLD preserves missing live meaning/user judgments. S1 preserves legacy today output while its new question-reading contract remains unverified. S6 preserves the existing valid lunar day-30 input-validation failure; no model generation is attempted.

[Implementation and agent contract](CODEX_AGENT_VERIFICATION.md)
[Machine-readable evidence](CODEX_AGENT_VERIFICATION_RESULT.json)
