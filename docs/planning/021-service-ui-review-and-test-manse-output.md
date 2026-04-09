# Service UI Review And Test Manse Output 021

## Goal
- Re-check the current service UI before moving deeper into the LLM phase.
- Keep the public-facing screen simple.
- Add a temporary testing surface so the calculated manse data can be reviewed directly in the result screen.

## Current Review

### What should stay
- Input-first flow
- Single-column form
- White background and low-contrast borders
- Region autocomplete directly under the input
- Separate developer page from the service page

### What needed adjustment
- The result state needed a wider layout than the input state.
- The header mark was visually unstable and too close to a placeholder treatment.
- The result page exposed only narrative sections, which made manse verification too hard during development.
- Testing the backend manse contract required jumping to Swagger or CLI instead of staying in the service flow.

## Updated Direction

### Input state
- Keep the form narrow and familiar.
- Keep labels above controls.
- Keep radio and checkbox controls plain.

### Result state
- Widen the result container.
- Keep the narrative sections first.
- Add a clearly separated "testing manse" block below the narrative.
- Treat the testing block as temporary verification UI, not final production UI.

## Testing Manse Output Scope
- Basic meta:
  - selected region
  - corrected solar datetime
  - day master
  - internal grade
- Manse table rows
- Five-element counts and percentages
- Luck-cycle list
- Supplementary positions

## Why this is the right midpoint
- The user flow remains simple enough for non-technical testing.
- The team can verify real backend manse output without opening debug-only screens.
- The temporary testing block can be removed later without changing the backend contract.
