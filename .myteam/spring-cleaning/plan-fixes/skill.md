---
name: Plan Fixes
description: |
  Turns cleanup findings into a prioritized, feature-neutral implementation plan.
  Use this skill to define safe sequencing, acceptance criteria, and verification steps.
---

Convert cleanup findings into a decision-complete plan that preserves behavior.

## Checklist

- Group fixes by type: deduplication, unused-code cleanup, reorganization, naming/consistency, and docs updates.
- Prioritize low-risk/high-value fixes first.
- Sequence changes to minimize merge risk and simplify review.
- Define acceptance criteria for each planned change.
- Add verification steps for each group (targeted tests, imports/load checks, lint/type checks when available).
- Record assumptions and exclusions explicitly, especially for medium/low-confidence findings.
- For each affected directory, explicitly plan `DOCS.md` reconciliation (what section changes and why).
- Decide whether the directory should include/update a "Potential Weak Points" section after implementation:
  - add/update entries only for real remaining weak points or likely error points,
  - if no credible weak points remain, do not add placeholder entries.

## Planning Rules

- Keep all planned changes feature-neutral.
- Split risky items into a separate follow-up queue; do not mix with safe cleanup.
- Prefer small, composable edits over large structural moves.

## Output

Produce an ordered cleanup plan with:

- change summary,
- rationale,
- risk classification,
- acceptance criteria,
- verification commands/checks.
- explicit `DOCS.md` update actions per affected directory.
