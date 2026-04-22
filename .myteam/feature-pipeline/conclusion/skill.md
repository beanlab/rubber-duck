---
name: Conclude Feature
description: |
    Work instruction for concluding a feature in this repository.
    If you are helping with implementation, testing, or docs updates,
    load this skill.
---

## Concluding a Feature

Before a feature branch is ready to merge, the following must be complete.

### Run `code-linter`

Delegate to the `code-linter` role and address any concerns.
Repeat until no actionable concerns remain.

### Run `.myteam` update check

Delegate to the `project-myteam-update` role and incorporate required
instruction updates.

### Semi-final commit

If changes have been made by this point, commit them.
Follow guidance in the `git-commit` skill.

### Version bump

If runtime behavior changed, ensure `pyproject.toml` version is bumped
appropriately.

Because the project is in 0.x:

- breaking interface change: bump minor
- non-breaking behavior/docs/test change: bump patch

Check branch history before deciding whether a bump already happened.
Do not bump twice in one branch unless explicitly requested.

### Changelog

Update `CHANGELOG.md` with the feature summary and user-visible impact.

### Documentation

Update documentation for changed behavior, especially:

- `README.md`
- `docs/application_interface.md`
- `docs/getting-started.md` (if setup/run flow changed)

### Final commit

Commit any additional changes.
