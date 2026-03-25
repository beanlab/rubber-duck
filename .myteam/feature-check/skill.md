---
name: Feature Checklist
description: |
  Specific instructions for ensuring a new feature is ready to merge. Use this skill when a new feature is finished.
---

## Pre-merge Feature Checklist

Before a feature is ready to merge, we need to ensure the following.
Please go through each section below and verify that everything is ready.

### Sanity check the changes to the code

- Make sure the changes are logically correct. Are there any obvious errors?
- Check that there are not python syntax errors. Everything should load properly.

### Check style

- All changed files should have consistent formatting following PEP8 style.
- There should not be significant duplicated code.

### The CHANGELOG.md and DOCS.md files should be updated

`CHANGELOG.md`:

- For the changelog entry, we want to use the latest change timestamp in the current branch.
- Update the changelog entry for this branch to use the latest timestamp.
- Update the changelog entry content to reflect the full changes of this branch.

`DOCS.md`:

- Each `DOCS.md` file within each directory should be updated with the current function and structure of the code.
  Reconcile it if they are misaligned.

### All pytests should pass

Please run `poetry run pytest -q` to make sure all tests are passing.

### Conclusion

At the end, present your findings to the user. If everything checks out, draft a pr description that includes what was
changed.
