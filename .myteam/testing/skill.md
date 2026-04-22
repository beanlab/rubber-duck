---
name: Testing
description: |
  This skill describes the testing philosophy and commands for this repo.
  Load this skill when you add, remove, or modify tests.
---

## Testing

### Philosophy

- tests should focus on externally observable behavior from the documented interface
- assertions should prove outcomes users/admins/operators can observe (messages, files, command results)
- avoid coupling tests to internal helper implementation details unless unavoidable
- new or changed behavior should trace back to `docs/application_interface.md`
- tests should be clear evidence that the documented contract is satisfied

### Process

Run tests from repo root with:

```
poetry run pytest -q
```

Alternative (if Poetry env is already active):

```
python -m pytest -q
```

Tests are in `tests/`.
