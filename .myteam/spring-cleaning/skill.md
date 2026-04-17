---
name: Spring Cleaning
description: |
  Guides feature-neutral cleanup and organization of the rubber-duck project.
  Use this skill to audit project structure, plan safe cleanup, and implement non-behavioral improvements.
---

Keep the repository organized, maintainable, and easy to navigate without changing product behavior.

## Scope

- Evaluate project structure as a whole (`src/`, `prompts/`, `docs/`, configs, scripts, and related assets).
- Focus on feature-neutral cleanup: reduce duplication, remove or quarantine unused code paths, and improve file/module
  placement.
- Improve consistency in naming, module boundaries, and local documentation where needed for maintainability.
- Avoid introducing new product features or altering expected runtime behavior.

## Workflow

1. Load `spring-cleaning/identify-weak-points` role to collect structural and hygiene findings.
2. Wait for the spawned agent
3. Explain the found weaknesses and potential fixes to the user.
4. Load `feature-pipeline`
5. Implement one change at a time. After each one:
    - Explain to the user why that change is important.
    - Suggest a commit message.
    - Wait for confirmation.
    - Repeat for the rest of the changes

## Guardrails

- Treat behavior preservation as a hard requirement.
- Prefer incremental edits over broad rewrites.
- For removals, require evidence of unused status (search references, runtime wiring, tests, or config usage).
- If a cleanup action has uncertainty or behavior risk, surface it explicitly and keep it out of the default fix set.
- When files/modules are moved or ownership boundaries change, update both source and destination directory `DOCS.md`
  files in the same cleanup batch.
- Treat `DOCS.md` as maintained source-of-truth context: reconcile docs with code before and after cleanup changes.
