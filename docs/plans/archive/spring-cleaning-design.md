# Spring Cleaning Deep Review Design

## 1. Repo function + skill fit

Rubber Duck is a configurable Discord bot platform for AI-assisted learning workflows.
The spring-cleaning skill fits as a **behavior-preserving** maintenance workflow that
keeps the project organized and safe to modify while respecting the application
interface contract in `docs/application_interface.md`.

The requested update makes spring cleaning explicitly **deep** and **multi-agent**,
with findings consolidated into a single report file for auditability.

## 2. Research findings (surface-level)

The design should align with established refactoring and cleanup guidance:

- Refactoring is defined as improving internal structure without changing observable
  behavior, and it is best done via **small, behavior-preserving transformations**.
  This supports the skill’s “feature-neutral cleanup only” constraint and incremental
  change sequencing. citeturn1search4turn1search6
- Refactoring is riskier without safeguards, so **tests or verification steps** should
  be part of the process. This supports the skill’s post-change verification guidance.
  citeturn1search5
- Refactoring work benefits from clear objectives and scoped changes, which maps to
  structured multi-agent audits and a single consolidated report to avoid drift.
  citeturn0search0

## 3. Deep-dive investigation needs

Key repo-specific needs to verify during implementation:

- Confirm `print_directory_tree` exists and is importable from `myteam.utils` for
  the structure agent’s `load.py` (present in `.myteam/utils` per existing roles).
- Identify where to place new report output and how to ensure the agents append
  to a single file without clobbering prior sections.
- Ensure the agents can safely read `docs/application_interface.md` and
  `production-config.yaml` before analysis.

## 4. Proposed structural changes

### 4.1 Update existing spring-cleaning skill workflow

Current: single-agent `spring-cleaning/identify-weak-points`.

Proposed: multi-agent deep review with required reads and consolidated reporting.

Workflow update (conceptual):

1. Create or ensure `docs/spring-cleanings/` exists.
2. On “spring cleaning” request, create report file:
   `docs/spring-cleanings/spring-cleaning-<mm-dd>.md`
3. Spawn **three** roles in parallel:
   - `spring-cleaning/project-structure`
   - `spring-cleaning/prompt-evaluator`
   - `spring-cleaning/src-evaluator`
4. Each role must:
   - first read `docs/application_interface.md`
   - then read `production-config.yaml`
   - then perform its scoped audit
   - finally append findings to the shared report file
5. Once all roles complete, summarize findings to user and propose
   safe cleanup actions, one at a time, preserving behavior.

### 4.2 New report template

`docs/spring-cleanings/spring-cleaning-<mm-dd>.md`

- Header: date + branch + brief scope
- Section: `Project Structure`
- Section: `Prompt Evaluation`
- Section: `Src Evaluation`

Each section should include:
- Findings (bulleted)
- Evidence (paths, search references, config mentions)
- Confidence (high/med/low)
- Proposed next steps (optional)

## 5. New roles and responsibilities

### 5.1 `spring-cleaning/project-structure` role

Scope:
- Repository structure, file placement, duplication, stale docs
- Mislocated assets across `docs/`, `scripts/`, `prompts/`, `archive/`, etc.

Special requirement:
- The role’s `load.py` **must** print the full project tree using
  `print_directory_tree` from `myteam.utils` (not shell tree/rg).

### 5.2 `spring-cleaning/prompt-evaluator` role

Scope:
- `prompts/` only (exclude `archive/`)
- Consistency, duplication, naming, alignment with expected workflows

### 5.3 `spring-cleaning/src-evaluator` role

Scope:
- `src/` only
- Identify duplicate utilities, dead modules, mislocated files,
  and `DOCS.md` mismatches (without behavior changes)

### 5.4 Common role behaviors

All roles must:
- Read `docs/application_interface.md` and `production-config.yaml` first.
- Record findings under their section in the shared report file.
- Avoid implementation changes (audit only).

## 6. Skill/role creation mechanics

Implementation must use:
- `myteam new role <name>` for each role
- `myteam new skill <name>` for any new skill(s)

This ensures `.myteam` scaffolding is consistent with repo tooling.

## 7. Dependency and tooling notes

- `print_directory_tree` (from `myteam.utils`) is required.
- No external dependencies needed.
- No network access or credentials required for audits.

## 8. Files to create/modify (planned)

Create:
- `docs/spring-cleanings/` (new folder)
- `docs/spring-cleanings/spring-cleaning-<mm-dd>.md` (per run)
- `.myteam/spring-cleaning/project-structure/` (role)
- `.myteam/spring-cleaning/prompt-evaluator/` (role)
- `.myteam/spring-cleaning/src-evaluator/` (role)

Modify:
- `.myteam/spring-cleaning/skill.md`
- `.myteam/spring-cleaning/identify-weak-points/role.md` (if kept, clarify it is superseded or
  convert it into one of the new roles)

## 9. Open questions / user decisions (resolved)

- Report location: `docs/spring-cleanings/`
- Filename date format: `spring-cleaning-<mm-dd>.md`
- Report sections: `Project Structure`, `Prompt Evaluation`, `Src Evaluation`
- Prompt scope: `prompts/` only (exclude `archive/`)
- Structure agent directory output: use `print_directory_tree`
- All agents must read `docs/application_interface.md` and `production-config.yaml`

## 10. Risks and mitigations

- Risk: report file contention if agents append concurrently.
  - Mitigation: define a clear append protocol or serialize write steps.
- Risk: `print_directory_tree` output too large.
  - Mitigation: allow max-depth parameter and explicit excludes.
- Risk: roles drift beyond scope.
  - Mitigation: explicit role scope + “audit only, no changes” reminder.
