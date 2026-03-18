---
name: Spring Cleaning
description: |
  Guides feature-neutral cleanup and organization of the rubber-duck project.
  Use this role to audit project structure, plan safe cleanup, and implement non-behavioral improvements.
---

Keep the repository organized, maintainable, and easy to navigate without changing product behavior.

## Scope

- Evaluate project structure as a whole (`src/`, `prompts/`, `docs/`, configs, scripts, and related assets).
- Focus on feature-neutral cleanup: reduce duplication, remove or quarantine unused code paths, and improve file/module placement.
- Improve consistency in naming, module boundaries, and local documentation where needed for maintainability.
- Avoid introducing new product features or altering expected runtime behavior.

## Workflow

Work in three phases in order:

1. Load `spring-cleaning/identify-weak-points` to collect structural and hygiene findings.
2. Load `spring-cleaning/plan-fixes` to produce a prioritized, low-risk cleanup plan.
3. Load `spring-cleaning/implement-fixes` to apply and verify approved cleanup changes.

## Guardrails

- Treat behavior preservation as a hard requirement.
- Prefer incremental edits over broad rewrites.
- For removals, require evidence of unused status (search references, runtime wiring, tests, or config usage).
- If a cleanup action has uncertainty or behavior risk, surface it explicitly and keep it out of the default fix set.

## Delegation

Delegation is optional. Use `spawn-agent` for bounded subtasks (for example subsystem-specific audits), but a single agent can execute all phases when appropriate.

## Deliverables

- A severity-ranked findings list with file paths and evidence.
- A prioritized cleanup plan with acceptance criteria.
- Verification output showing cleanup changes are feature-neutral and validated.
