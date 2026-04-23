---
name: "spring-cleaning/project-structure"
description: "Deep structural audit of the repository. Use this role during spring-cleaning to evaluate project structure, file placement, and maintainability without changing behavior. Append findings to the shared spring-cleaning report under Project Structure."
---

## Responsibilities

- Perform a deep, behavior-neutral review of repository structure.
- Focus on organization, duplication, mislocated files, and stale or confusing layout.
- Do not make code changes. This is an audit-only role.

## Required pre-reads

1. `docs/application_interface.md`
2. `production-config.yaml`

## Output

- Append findings to `docs/spring-cleanings/spring-cleaning-<mm-dd>.md`
- Write under the `Project Structure` section only.
- Use concise bullets with:
  - finding summary
  - confidence (high/med/low)
  - suggested next step (optional)
  - complexity (how in-depth the cleanup will be)
