# Debugging Practice Duck

`debugging_practice_duck` is a workflow duck for traceback-driven debugging practice. It loads a configured YAML rubric, presents one documented error scenario at a time, and asks the user to explain four priority topics before moving on:

- what the error means
- where the error is located
- what the erroneous code was intended to do
- what concrete fix is needed

## Runtime Wiring

Production wiring lives in `production-config.yaml` under the global `ducks.debugging-practice-duck` entry. The CS 110 `debugging-duck` channel references that global duck by name.

Required workflow settings:

- `rubric_path`: path or list of paths to YAML rubrics
- `first_message`: opening instructions
- `conversation_review_agent`: review agent config

Optional workflow settings:

- `review_turns`: integer count or `full`
- `incomplete_subprocess`: process-agent config for incomplete attempted answers
- `incorrect_subprocess`: process-agent config for concept-transfer support after incorrect answers

The workflow owns the JSON schemas for the review and subprocess outputs. Configured agents do not need to provide `output_format`.

## Rubric Shape

The CS 110 production rubric is `rubrics/CS110/3b-rubric.yaml`. Each traceback scenario can include:

- `traceback`
- `error line`
- `intended behavior`
- `required concept`
- `required fix`
- `code`

The workflow uses per-scenario `code` when present and falls back to `full project` for legacy rubrics. `scripts/rubricize.py` can generate line-numbered `code`, `error line`, and `correct code` fields from source-Python debugging sequences.

## Conversation Flow

The workflow sends the opening message, the current scenario code, the traceback, and a prefab prompt asking what the error type means. It then passes a script-style `Student:`/`TA:` transcript to the review agent and expects JSON containing:

- `reason for evaluations`
- `latest_attempted_priority`
- `latest_attempted_status`
- `fulfilled_priorities`
- `unrelated`

Priority progress is merged centrally by the workflow. If the user gives a complete fix that matches a documented required fix, the workflow also treats location and intended behavior as fulfilled, but still requires the user to explain what the error means.

Incorrect responses enter concept-transfer support. Incomplete responses enter incomplete-answer support once, then transfer to concept support if the same priority is still incomplete. Direct-answer requests and clearly off-topic responses use the workflow-created unrelated redirection process agent.

## User-Facing Text

Most user-facing follow-up text comes from `prompts/debugging-practice-duck/prefabs.yaml`. Process agents return structured JSON with a single response field when the workflow needs targeted feedback for incomplete, incorrect, or unrelated responses.

