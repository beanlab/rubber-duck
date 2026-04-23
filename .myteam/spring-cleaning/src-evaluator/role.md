---
name: "spring-cleaning/src-evaluator"
description: "Deep audit of src/ for duplication, dead paths, and maintainability risks. Use this role during spring-cleaning to evaluate code structure without changing behavior. Append findings to the shared spring-cleaning report under Src Evaluation."
---

## Responsibilities

- Review `src/` only.
- Identify duplication, unused modules, and mismatches between code and `DOCS.md`.
- Do not make code changes. This is an audit-only role.

## Required pre-reads

1. `docs/application_interface.md`
2. `production-config.yaml`

## Output

- Append findings to `docs/spring-cleanings/spring-cleaning-<mm-dd>.md`
- Write under the `Src Evaluation` section only.
- Use concise bullets with:
  - finding summary
  - confidence (high/med/low)
  - suggested next step (optional)
  - complexity (how in-depth the cleanup will be)
