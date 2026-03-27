---
name: Dev Assistance
description: |
  Software delivery workflow for feature work in the rubber-duck project.
  Load this skill when implementing or modifying features and choose either the full multi-agent workflow or a lightweight path based on task size/risk.
---

This project provides AI assistants to users through chat platforms like Discord.

The flagship assistant is the "Rubber Duck", a virtual TA for computer science classes.

The prompts for these agents are in `prompts/`.

## Shared Plan Artifact

- The shared workflow plan file is `docs/plans/PLAN.md`.
- The canonical template is `docs/plans/PLAN_TEMPLATE.md`.
- Every role in this workflow reads and updates this file as needed.
- If any role discovers plan changes are required, the first priority is to update `docs/plans/PLAN.md` before making or requesting additional code/doc changes.

## Process

1. Triage with the user before execution:
   - Ask if they want to activate the full `dev-assistance` workflow.
   - If yes, run the Full Workflow below.
   - If no and the task is small/low risk, run the Lightweight Workflow below.

### Full Workflow

1. Call role `dev-assistance/planner`.
2. Planner initializes `docs/plans/PLAN.md` from `docs/plans/PLAN_TEMPLATE.md`, runs multi-turn discovery with the user, updates the plan, and asks for explicit plan approval.
3. Only after explicit user approval, spawn `dev-assistance/test-writer`.
4. Test writer creates tests only (no production-code edits) based on the approved plan and updates `docs/plans/PLAN.md`.
5. Spawn `dev-assistance/implementer` to make the approved tests pass while keeping `docs/plans/PLAN.md` current.
6. If implementer believes tests are incorrect or inconsistent with the project/plan, hand the task back to `dev-assistance/planner` for clarification and user re-approval before continuing.
7. After implementation, spawn `dev-assistance/reviewer`.
8. Reviewer reports findings to the user, especially required fixes or risks, and ensures required plan updates are captured first in `docs/plans/PLAN.md`.
9. If review findings require changes, return to implementer (and planner when re-planning is needed), then re-run reviewer.
10. After review passes, spawn `dev-assistance/docs-writer` to update docs.
11. Confirm with the user that everything has been fully implemented.
12. After user confirmation, move `docs/plans/PLAN.md` to an archive path (for example `docs/plans/archive/PLAN-<timestamp>.md`) instead of deleting it.

### Lightweight Workflow (Small Changes)

Use this only for small, low-risk changes where a full planning cycle would be overhead.

1. Confirm with the user that lightweight mode is acceptable.
2. Capture a short implementation note in the task response:
   - user intent,
   - expected behavior,
   - affected files,
   - quick risk check.
3. Implement directly with these baseline best practices:
   - keep changes minimal and scoped,
   - preserve module boundaries and naming conventions,
   - add/update focused tests for changed behavior,
   - run targeted validation (`pytest` subset or equivalent),
   - update only docs that changed behavior or usage.
4. If scope/risk grows or ambiguity appears, stop and switch to the Full Workflow starting with `dev-assistance/planner`.

## Role Loading Guidance

- Planner may load `src` and/or `config` skills while shaping the plan.
- Test writer should load `src` and/or `config` skills to design test scope and constraints.
- Implementer should load `src` and/or `config` skills based on the approved scope.
- Docs writer must load `docs-assistance`.
