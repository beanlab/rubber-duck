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
- Ensure removed files/code were truly unused based on the plan evidence and information in the respective `_docs.md`
  file.
- Confirm `_docs.md` references match current code locations and ownership boundaries after edits.

## Done Criteria

- Implemented changes match the approved plan.
- No behavior-affecting regressions are observed in verification.
- Duplication, unused artifacts, and structural inconsistencies are measurably reduced.

## Update Documentation

- Once implementation is complete, update each affected directory `_docs.md` to reflect the final state.
- Include a `## Potential Weak Points` section when meaningful for future audits.
- Add or keep entries in `Potential Weak Points` only when real residual weak points or likely error points remain.
- If no credible weak points remain in that area, do not add a `Potential Weak Points` section and do not add placeholder bullets.
- Keep each potential weak point concise with:
  - issue summary,
  - why it is risky,
  - recommended next cleanup direction.
