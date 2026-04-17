---
name: Feature Pipeline
description: |
    This skill defines the process for implementing project features.
    Load this skill when changing runtime behavior, tests, or
    behavior-facing docs.
---

## Feature Pipeline

Follow these steps in order.

### Create the git branch

Check the current branch.
If you are on `main`, ask the user to create a feature branch before proceeding.

### Understand the feature and update the interface document

First read `docs/application_interface.md` to understand the current
black-box contract.

Then confirm the requested behavior change:

- what behavior should change
- what behavior should remain unchanged

Update `docs/application_interface.md` to reflect the intended contract.
Review the changes with the user before moving on.

When this step is complete, commit changes before continuing.

### Design the feature

The goal is to produce a decision-complete implementation design before coding.

#### Understand context

Load `framework-oriented-design` and inspect existing patterns in `src/`.

#### Plan the feature

Decide whether framework refactoring is needed before adding behavior.
Prefer the simplest design that fits existing project conventions.

Create a plan document at:

- `docs/plans/<branch_name>.md`

Plan sections:

1. Framework refactor (feature-neutral prep work)
2. Feature addition (behavior implementation)

Get user approval before continuing.

When this step is complete, commit changes before continuing.

### Refactor the framework

Apply planned framework refactors without introducing new feature behavior.
Existing tests should still pass.

Review refactor changes with the user.
When this step is complete, commit changes before continuing.

### Update the test suite

Load `testing` skill.

Update `tests/` so coverage matches the interface document.
Prioritize black-box behavior validation.

Review test updates with the user.
When this step is complete, commit changes before continuing.

### Implement the feature

Implement feature behavior using the planned approach and updated framework.
Tests should pass.

Review implementation changes with the user.
When this step is complete, commit changes before continuing.

### Concluding the feature

Follow the `conclusion` subskill instructions.

### Notify the user

Notify the user when the feature is ready to push and merge.
