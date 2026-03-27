---
name: Identify Weak Points
description: |
  Audits repository structure and code hygiene for **feature-neutral** cleanup opportunities.
  Use this role to find duplication, unused code, mislocated files, and maintainability gaps.
---

Audit the repository to identify cleanup opportunities that do not change product behavior.

## Checklist

- Read each relevant directory `DOCS.md` first to gather expected boundaries, known error points, and any existing "Potential Weak Points" notes.
- Use any existing "Potential Weak Points" entries as initial audit seeds, then verify them against current code before carrying them forward.
- Map current structure and boundaries across `src/`, `prompts/`, `docs/`, configs, and scripts.
- Find duplicated logic, near-duplicate helpers, and repeated prompt/config patterns.
- Identify likely unused code, stale files, dead modules, and disconnected assets.
- Check for file placement issues (module responsibility mismatch, confusing folder location, mixed concerns).
- Flag weak or stale local docs and missing context that makes ownership/boundaries unclear.
- Note consistency issues in naming, layering, and dependency direction.

## Evidence Requirements

- For every finding, include supporting evidence (reference search results, import/call sites, config wiring, or test
  coverage signals).
- Mark findings with confidence (`high`, `medium`, `low`) and risk level.

## Output

Return findings ordered by severity with:

- exact file path(s),
- concise issue statement,
- evidence summary,
- recommended cleanup direction.

Do not edit `DOCS.md` during this identify phase. Report proposed doc updates as part of findings/planning outputs.
