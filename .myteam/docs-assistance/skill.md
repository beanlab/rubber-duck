---
name: Docs Assistance
description: |
  Guidance for creating, reviewing, and updating documentation in this repository. Load this skill when editing `DOCS.md`, `README.md`, `CHANGELOG.md`, or related developer-facing docs.
---

This skill governs developer-facing project docs, with `DOCS.md` as the primary focus.

## Scope

- Provide shared standards for concise, high-signal `DOCS.md` documentation.
- Apply the same clarity/accuracy standard to `README.md`, `CHANGELOG.md`, and plan-adjacent docs when a workflow role requires those updates.
- Keep docs aligned with current behavior, ownership boundaries, and runtime flow.
- Avoid broad narrative explanations that increase context without improving decisions.

## Section Menu (Use Only What Adds Value)

- `Purpose`: why this module exists and what it achieves.
- `Operational Flow`: entry points and behavior sequence.
- `Boundaries`: ownership lines and out-of-scope responsibilities.
- `Dependencies`: only high-impact dependencies that affect correctness.
- `Failure Modes and Guardrails`: common break points and safe-refactor notes.

Sections are optional. Include only sections that add unique information for the module.

## Writing Workflow

1. Confirm current behavior from code/config before writing.
2. Remove stale bullets first.
3. Add only unique, decision-relevant statements.
4. Keep sections optional; skip any section that adds no value.

## Concision Guardrails

- Prefer short bullets over prose blocks.
- Do not pad sections to satisfy structure.
- Avoid repeating details already clear from code unless they prevent mistakes.
- Prioritize clarity that helps future agents edit safely.
- If sections overlap, merge or remove the weaker one.
- Avoid file inventories unless they prevent ambiguity.
