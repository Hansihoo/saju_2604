# Project Status

| Feature Name | Feature Description | Progress Status | Notes |
| --- | --- | --- | --- |
| Local Codex LLM provider | Allow the saju phrasing layer to use local `codex exec` instead of the OpenAI API. | Done | Added `SAJU_LLM_PROVIDER=codex` path for full report, free preview, and detail render. Actual local Codex calls passed for free preview and full report; related unit tests passed. |
| Result design lab | Compare document-style treatments using a fixed saju result without API or Codex calls. | Done | Reworked `/design-lab` around premium report, essay report, and one-page brief variants. `pnpm build:web` passed; desktop and 390px mobile browser checks showed no console errors or horizontal overflow. |
| Essay result layout | Apply the document-lab essay treatment to the live saju result page. | Done | Added `essay-result` mode to `SajuResultView` and restyled the result shell, outline, hero, insight cards, narrative sections, and data cards as a document-style reading. `pnpm build:web` passed. |
| Project documentation refresh | Make the project identity, recent changes, and no-OpenAI-cost local testing path easier to find. | Done | Updated README and PROJECT_PROFILE, added `docs/START_HERE.md`, and documented fallback/Codex local test modes versus OpenAI production default. |
