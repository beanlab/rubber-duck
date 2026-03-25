---
name: Docs Read Assistance
description: |
  Task-specific guidance for reading `DOCS.md` files quickly and extracting decision-relevant context.
  Use this skill before architecture-sensitive edits or cleanup planning.
---

Use this skill to extract concise context from existing `DOCS.md` files.

## Reading Priorities

- Identify `Purpose` and `Operational Flow` first.
- Extract `Boundaries` to understand ownership and out-of-scope concerns.
- Capture only high-impact `Dependencies`.
- Note `Failure Modes and Guardrails` that affect edit safety.

## Reconciliation Checks

- Compare doc claims with current runtime wiring and call paths.
- Flag stale statements, missing ownership notes, or drifted dependencies.
- Separate confirmed facts from assumptions.

## Output Style

- Return short, decision-relevant bullets.
- Emphasize what could cause wrong edits if misunderstood.
- Do not rewrite docs during read-only discovery tasks.

