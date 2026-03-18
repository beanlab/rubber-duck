---
name: Implement Fixes
description: |
  Applies approved feature-neutral cleanup changes and validates behavior is preserved.
  Use this skill to execute planned refactors, reorganization, and hygiene updates safely.
---

Implement the approved cleanup plan incrementally and verify no behavioral regression is introduced.

## Checklist

- Apply only approved, feature-neutral planned edits.
- Preserve public/runtime behavior while improving maintainability.
- Keep commits/changesets focused by cleanup category where possible.
- Update related docs/comments when moving or consolidating modules.
- Re-run verification after each logical batch.

## Verification

- Confirm imports, entrypoints, and workflow wiring still resolve.
- Run targeted tests for touched areas; run broader test suite when feasible.
- Validate key runtime checks used by the project (for example startup/load paths).
- Ensure removed files/code were truly unused based on the plan evidence.

## Done Criteria

- Implemented changes match the approved plan.
- No behavior-affecting regressions are observed in verification.
- Duplication, unused artifacts, and structural inconsistencies are measurably reduced.
