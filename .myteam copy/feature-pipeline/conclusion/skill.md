---
name: Conclude Feature
description: |
    Work instruction for concluding a feature.
    If you helping with development in ANY way, you MUST load this skill.
---

## Concluding a Feature

Before a feature branch is ready to merge, the following must be complete.

### Run `code-linter`

Please delegate to the `code-linter` role. Address any concerns they raise. 

After addressing their concerns, run it again. Loop until no concerns are raised.

**Do not** proceed until this step is complete.

### Run `project-myteam-update`

Please delegate to the `project-myteam-update` role. 
When they are finished, proceed.

**Do not** proceed until this step is complete.

### Semi-final commit

If any changes have been made by this point, please commit them.
Follow guidance in the `git-commit` skill.

### Version bump

If any code or templates have changed, then the version in `pyproject.toml` needs to change.

Because we are still in *preview*, the leading version will stay at 0.
If the public interface has a breaking change, the minor version should increase.
If the public interface has no breaking changes, just the patch version should increase.

Please describe the scope of the changes in the current branch and determine what version bump is needed.
Then inspect the version:

- if it has been updated incorrectly, check with the user about what version they want
- if it has not been udpated at all, update the version and inform the user

Only one version bump in a branch is needed. If the version in the branch has already been bumped,
do not bump it again.

Do not decide this from the current file contents alone. Check the branch history first to see whether
this branch already includes a version-bump commit or a prior change to the version/changelog files.
Compare against the branch's earlier commits or merge-base as needed before making any new bump.
If the branch already contains a version bump, keep that version unless the user explicitly asks to change it.

### Changelog

Please update the changelog to include a helpful description of the changes made.

### Readme and Documentation

The Readme and other documentation (if relevant) must be up-to-date.
Inspect the code changes and update the documentation accordingly.

### Completed Backlog Items

If the feature branch completes one or more backlog items, move those backlog documents from
`src/governing_docs/backlog/` into `src/governing_docs/backlog/completed/`.

Only move backlog docs that are clearly complete from shipped behavior in the branch.

### Final commit

Commit any additional changes.
