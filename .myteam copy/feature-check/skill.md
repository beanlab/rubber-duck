---
name: feature-checklist
description: |
  Specific instructions for ensuring a new feature is ready to merge. Use this skill when a feature is finished.
---

## Pre-merge Feature Checklist

Before a feature is ready to merge or create a pull request, verify each section below.

### Sanity check the code changes

- Validate that branch changes are logically correct and match requirements.
- Check for syntax/runtime errors in changed Python files.

### Check style and maintainability

- Ensure changed files follow existing formatting conventions.
- Confirm no significant duplicated logic was introduced.

### Relevant documentation should be updated

`README.md`:

- Update when setup, runtime behavior, or user workflow changed.

`CHANGELOG.md`:

- For the changelog entry, we want to use the latest change timestamp in the current branch.
- Update the changelog entry for this branch to use the latest timestamp.
- Update the changelog entry content to reflect the full changes of this branch.

`DOCS.md`:

- Update only `DOCS.md` files for directories touched by the feature.
- Reconcile each touched `DOCS.md` with current behavior and structure.
- Do not mass-edit unrelated docs.

### Tests should pass

- Run targeted tests during development and `poetry run pytest -q` before merge.

### Conclusion

Present findings to the user. If everything checks out, draft a PR description that summarizes what changed.
