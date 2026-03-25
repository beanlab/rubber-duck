---
name: Docs Write Assistance
description: |
  Task-specific guidance for creating and updating concise, high-signal `DOCS.md` files.
  Use this skill when documentation must be reconciled with current code behavior.
---

Use this skill when creating or editing `DOCS.md`.

## Writing Workflow

1. Confirm current behavior from code/config before writing.
2. Remove stale bullets first.
3. Add only unique, decision-relevant statements.
4. Keep sections optional; skip any section that adds no value.

## Recommended Section Menu

- `Purpose`: why this module exists and what it should not own.
- `Operational Flow`: entry points and behavior sequence.
- `Boundaries`: ownership lines and out-of-scope responsibilities.
- `Dependencies`: only high-impact dependencies that affect correctness.
- `Failure Modes and Guardrails`: common break points and safe-refactor notes.

## Concision Guardrails

- Treat length caps as upper bounds, not targets.
- Prefer short bullets over prose blocks.
- Do not pad sections to satisfy structure.
- Avoid repeating details already clear from code unless they prevent mistakes.
- Prioritize clarity that helps future agents edit safely.

