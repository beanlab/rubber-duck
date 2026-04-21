---
name: Identify Weak Points
description: |
  Legacy spring-cleaning audit role. Superseded by the multi-agent deep review
  workflow, but kept for backward compatibility when invoked directly.
---

## Status

This role is superseded by:
- `spring-cleaning/project-structure`
- `spring-cleaning/prompt-evaluator`
- `spring-cleaning/src-evaluator`

Prefer the multi-agent workflow in `.myteam/spring-cleaning/skill.md`.

Audit the repository to identify cleanup opportunities that do not change product behavior.
Do not modify files during this identify phase.

## Checklist

- Read each relevant directory `DOCS.md` first to gather expected boundaries, known error points, and any existing "Potential Weak Points" notes.
- Use any existing "Potential Weak Points" entries as initial audit seeds, then verify them against current code before carrying them forward.
- Map current structure and boundaries across `src/`, `prompts/`, `docs/`, configs, and scripts.
- Find duplicated logic, near-duplicate helpers, and repeated prompt/config patterns.
- Identify likely unused code, stale files, dead modules, and disconnected assets.
- Check for file placement issues (module responsibility mismatch, confusing folder location, mixed concerns).
- Flag weak or stale local docs and missing context that makes ownership/boundaries unclear.
- Note consistency issues in naming, layering, and dependency direction.
- Flag findings that touch the external application interface contract
  so follow-up can load `application-docs`.

## Evidence Requirements

- For every finding, include supporting evidence (reference search results, import/call sites, config wiring, or test
  coverage signals).
- Mark findings with confidence (`high`, `medium`, `low`) and risk level.
- Evidence must include categories, when applicable:
  - imports/references
  - runtime wiring/config
  - tests/CI signals

## Output

Return findings ordered by severity with:

- exact file path(s),
- concise issue statement,
- evidence summary,
- confirmed vs suspected tag,
- recommended cleanup direction.

Do not edit `DOCS.md` during this identify phase. Report proposed doc updates as part of findings/planning outputs.
