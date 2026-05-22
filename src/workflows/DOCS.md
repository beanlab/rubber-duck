## Purpose

`src/workflows` contains multi-step product workflows that run as duck implementations.

## Operational Flow

- `main.build_ducks(...)` maps workflow duck types to concrete classes:
  - `registration` -> `RegistrationWorkflow`
  - `assignment_feedback` -> `AssignmentFeedbackWorkflow`
  - `debugging_practice_duck` -> `DebuggingPracticeDuckWorkflow`
- `RegistrationWorkflow` runs `Registration.run(...)`, summarizes progress, and hands off continuation guidance to the configured registration bot tool.
- `AssignmentFeedbackWorkflow` collects a markdown report, resolves assignment/project, loads rubric/rules, grades each rubric item, and returns markdown-formatted feedback.
- `DebuggingPracticeDuckWorkflow` owns the Discord conversation wiring for debugging-practice threads, including the opening message, turn loop, and closeout messaging.
- `debugging_agents.DuckAgent` owns the structured review/parsing and completion-generation decisions used by the workflow.

## Dependencies

- Uses `AIClient` agents for project detection fallback and rubric-item grading.
- Uses one configured `AIClient` agent for debugging-practice rubric assessment JSON, plus process agents for incomplete-answer support, concept-transfer support after incorrect answers, and unrelated/direct-answer redirection.
- `debugging_agents.DuckAgent` owns the completion-generation facade while reusing `Rubric` and `ValidationSchema`.
- Uses Discord messaging/read-url hooks passed in from runtime wiring.

## Failure Modes and Guardrails

- Registration handles timeout/permission errors and can notify TA channel on failures.
- Assignment feedback requires markdown uploads and supported assignment names; unsupported or missing inputs terminate with explicit conversation messages.
- Debugging-practice conversation-review configs do not need `output_format`; the workflow sets the review output format to its rubric assessment JSON schema, preserves configured tools such as `conclude_conversation`, and validates the response before using it.
- Debugging-practice subprocess configs do not need `output_format`; the workflow replaces their prompts with the current process prompts and sets their JSON schemas. If an incomplete or incorrect subprocess is omitted, the workflow creates a default process agent that inherits the review agent model and reasoning with no tools.
- Debugging-practice has no separate free-form user-facing chat agent. Student-facing text comes from prefab workflow responses or tightly scoped process-agent JSON fields.
