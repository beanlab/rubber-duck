## Purpose

`src/workflows` contains multi-step product workflows that run as duck implementations.

## Operational Flow

- `main.build_ducks(...)` maps workflow duck types to concrete classes:
  - `registration` -> `RegistrationWorkflow`
  - `assignment_feedback` -> `AssignmentFeedbackWorkflow`
  - `debugging_practice_duck` -> `DebuggingPracticeDuckWorkflow`
  - `conversation_review` -> `CoversationReviewWorkflow`
- `RegistrationWorkflow` runs `Registration.run(...)` in a fixed sequence and sends the completion message directly; it does not use an agent.
- `AssignmentFeedbackWorkflow` collects a markdown report, resolves assignment/project, loads rubric/rules, grades each rubric item, and returns markdown-formatted feedback.
- The conversation-review builder consumes the target-channel queues that `main.py` constructs from its settings; reviewers receive a jump link to the opening message and a link to its thread.
- Configure it as a named duck with `builder: src.workflows.conversation_review.conversation_review_workflow:build` and `settings.target_channel_ids`, then reference that duck from the reviewer channel.

## Dependencies

- Uses `AIClient` agents for project detection fallback and rubric-item grading.
- Uses Discord messaging/read-url hooks passed in from runtime wiring.

## Failure Modes and Guardrails

- Registration handles timeout/permission errors and can notify TA channel on failures.
- Assignment feedback requires markdown uploads and supported assignment names; unsupported or missing inputs terminate with explicit conversation messages.
- Debugging-practice has no separate free-form user-facing chat agent. Student-facing text comes from prefab workflow responses or tightly scoped process-agent JSON fields.
