---
name: Docs Assistance
description: |
  Shared guidance for reading and writing `DOCS.md` files in this repository.
  Use this skill for documentation-focused tasks and load nested read/write skills for task-specific steps.
---

This skill governs `DOCS.md` files only.

## Scope

- Provide shared standards for concise, high-signal `DOCS.md` documentation.
- Keep docs aligned with current behavior, ownership boundaries, and runtime flow.
- Avoid broad narrative explanations that increase context without improving decisions.

## Section Menu (Use Only What Adds Value)

- `Purpose`
- `Operational Flow`
- `Boundaries`
- `Dependencies`
- `Failure Modes and Guardrails`

Sections are optional. Include only sections that add unique information for the module.

## Brevity Principles

- Caps are maximums, never minimums.
- Keep sections as short as possible while preserving correctness.
- Prefer short bullets over paragraphs.
- If sections overlap, merge or remove the weaker one.
- Avoid file inventories unless they prevent ambiguity.

## Workflow

1. Load `docs-assistance/read` to extract current truth from existing docs and code.
2. Load `docs-assistance/write` when creating or updating `DOCS.md`.
3. Reconcile stale statements before adding new bullets.

