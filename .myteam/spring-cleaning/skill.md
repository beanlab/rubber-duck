---
name: Spring Cleaning
description: |
  Guides feature-neutral cleanup and general organization of the project.
  Use this skill when a user asks for spring cleaning or a deep, behavior-preserving
  audit of the repo. 
---

Keep the repository organized, maintainable, and easy to navigate without changing product behavior. Always run a
multi-agent review and consolidate findings.

## Scope

- Evaluate project structure as a whole (`src/`, `prompts/`, `docs/`, configs, scripts, and related assets).
- Focus on feature-neutral cleanup: reduce duplication, remove or quarantine unused code paths, and improve file/module
  placement.
- Improve consistency in naming, module boundaries, and local documentation where needed for maintainability.
- Avoid introducing new product features or altering expected runtime behavior.
- Treat feature-neutral cleanup as **behavior-preserving refactoring/cleanup** only.

## Workflow

1. Create (or reuse) the report directory and file:
    - `docs/spring-cleanings/spring-cleaning-<mm-dd>.md`
    - If the file does not exist, initialize it with sections:
        - `Project Structure`
        - `Prompt Evaluation`
        - `Src Evaluation`
2. Spawn the deep-review roles in parallel:
    - `spring-cleaning/project-structure`
    - `spring-cleaning/prompt-evaluator`
    - `spring-cleaning/src-evaluator`
3. Each role must:
    - Read `docs/application_interface.md` first
    - Read `production-config.yaml` second
    - Append findings to its matching section in the shared report file
4. Wait for all agents to complete.
    - If agents cannot be spawned, perform the same scoped audits manually.
5. Explain the found weaknesses and potential fixes to the user.
    - If no high/medium-confidence findings exist, report that result and stop.
6. If cleanup affects the application design contract, load `application-docs`
   and follow its change workflow.
7. If a cleanup finding should be tracked for later implementation,
   propose a backlog item to the user and, if approved, load `backlog`
   to capture it.
8. Load `feature-pipeline`
9. Implement one change at a time. After each one:
    - Explain to the user why that change is important.
    - Suggest a commit message.
    - Run relevant tests or targeted checks; if unavailable, note the risk.
    - Wait for confirmation.
    - Repeat for the rest of the changes

## Guardrails

- Treat behavior preservation as a hard requirement.
- Prefer incremental edits over broad rewrites.
- For removals, require evidence of unused status (search references, runtime wiring, tests, or config usage).
- If a cleanup action has uncertainty or behavior risk, surface it explicitly and keep it out of the default fix set.
- Expect verification after each change; record risk when tests are unavailable.
- When files/modules are moved or ownership boundaries change, update both source and destination directory `DOCS.md`
  files in the same cleanup batch.
- Treat `DOCS.md` as maintained source-of-truth context: reconcile docs with code before and after cleanup changes.
- Do not refactor application-design documents yourself. Delegate to
  `application-docs/refactoring`.

## Verification Guidance

- Prefer the smallest test/check that exercises the changed area.
- If a targeted test does not exist, run the closest available suite.
- If no tests are available, document the gap and the risk explicitly.
