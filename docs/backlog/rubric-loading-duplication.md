# Rubric Loading Duplication

Created on: 2026-04-20
Created by: Tyler (discovered by spring-cleaning agents)

## Details

Rubric loading logic is duplicated in `src/workflows/assignment_feedback_workflow.py`.
Both `_load_rubric` and `_load_rules` iterate over the same `rubric_files` and
call `yaml.safe_load(Path(file).read_text())`, which repeats IO and parsing.

- Problem addressed: duplicated rubric parsing can drift or waste IO.
- Intent: load rubric files once and share parsed structures between callers.
- Known details:
  - `_load_rubric` and `_load_rules` both read and parse the same files.

## Out-of-scope

- Changing rubric evaluation behavior without a separate design pass.
- Reworking assignment feedback logic beyond data-loading reuse.

## Dependencies

- None noted.
