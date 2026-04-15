# Developer Manse Inspector UI 022

## Goal
- Add a developer-only workbench for verifying manse output directly in the browser.
- Keep the service page simple while making the developer page dense and review-friendly.

## Why the developer page needs a separate layout
- The developer page is not a reading experience.
- It is a verification workspace:
  - input on one side
  - computed output on the other side
  - tables and debug values visible at the same time

## Readability guidance used

### Dense tables should be split by purpose
- Use one table for the canonical manse rows.
- Use separate smaller tables for elements and luck cycles.
- This follows the same practical direction used in structured design systems where large data sets are broken into smaller, scannable sections rather than one oversized surface.
- Reference:
  - [GOV.UK Design System: Table](https://design-system.service.gov.uk/components/table/)

### Labels and values should be separated visually
- Summary metadata works better as key-value blocks than as a raw JSON wall.
- High-signal items such as corrected datetime, day master, and internal grade should appear before the full table.

### Tables need strong headers and stable scanning lines
- Use captions, sticky headers, and clear row labels for repeated comparison work.
- Reference:
  - [Atlassian Design System: Table](https://atlassian.design/components/dynamic-table/)

### Raw JSON should remain available, but last
- Raw output is useful for exact debugging, but not as the primary inspection surface.
- The readable view should come first, raw JSON after that.

## Implemented structure
- Left panel:
  - developer input form
- Right panel:
  - basic meta
  - four pillars
  - canonical manse table
  - element analysis
  - luck cycles
  - supplementary positions
  - pipeline/debug sections
  - raw JSON

## Intent
- Make it easy for a human reviewer to compare the browser output against a known answer sheet.
- Avoid mixing the final service UX with the developer verification workflow.
