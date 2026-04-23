# Documented Interface Test Coverage

Created on: 2026-04-23
Created by: Tyler (consolidated from spring-cleaning findings)

## Details

The documented application interface has several medium- and high-complexity
test coverage gaps. The current suite validates a few helper behaviors, but it
does not exercise large parts of the user-visible and operator-visible contract
described in `docs/application_interface.md`.

- What problem does the feature address?
  - Major documented workflows and operational promises are effectively
    untested, which raises regression risk for Discord routing, workflow
    behavior, admin commands, stats-duck behavior, and startup/config loading.
- What is the intent of the feature?
  - Add black-box and workflow-level coverage for the documented interface so
    the automated suite protects the bot's user-facing and operator-facing
    behavior rather than only internal helpers.
- What details exist so far about this feature?
  - Add startup and Discord event-handling tests around `python -m src.main`
    and the documented routing/workflow contract.
  - Add focused workflow tests for `agent_led_conversation`,
    `user_led_conversation`, `conversation_review`, `registration`, and
    `assignment_feedback`, asserting the user-visible sequences and guardrails
    described in the interface docs.
  - Add command-routing tests for the admin surface, including `!messages`,
    `!usage`, `!feedback`, and `!metrics`, covering parsing, operator-visible
    responses, aggregation, and zip export behavior.
  - Add user-level tests for the stats-oriented duck experience, including the
    documented thread workflow, attachments, prompt/response flow, and exported
    artifacts.
  - Add config-loader and startup integration tests covering `--config`,
    `CONFIG_FILE_S3_PATH` fallback, recursive `$include` resolution, deep-merge
    behavior, and the documented `Duck online` readiness message.

### Undecided Notes

- `test_sql_metric_handlers.py` appears to remain within the documented
  interface boundary because `docs/application_interface.md` promises message,
  usage, and feedback recording for export/reporting, but it is still a
  persistence-level test rather than a black-box admin command test. Undecided:
  keep it as supporting coverage, replace it with admin-surface tests later, or
  do both.
- `test_dataset_tools.py` is not clearly grounded in
  `docs/application_interface.md`. The current interface document does not
  promise dataset-list ordering, deduplication, filename fallback behavior, or
  the exact empty-state/full-list messages asserted there. Undecided: remove
  those tests, rewrite them around a documented user-visible contract, or add
  the relevant behavior to the interface doc first.
- Test-scope cleanup is not fully complete just because the helper-formatting
  tests were removed. There is still an open question of whether any remaining
  implementation-level tests should stay as internal regressions even when they
  are outside the current public interface contract. Undecided: define a policy
  for allowable implementation-level tests versus contract-only coverage.

## Out-of-scope

- Reworking low-complexity assertions that are more specific than the public
  contract, such as exact helper formatting or SQL header shape checks.
- Changing runtime behavior or expanding the documented interface beyond what
  already exists in `docs/application_interface.md`.

## Dependencies

- No backlog dependencies identified yet.
