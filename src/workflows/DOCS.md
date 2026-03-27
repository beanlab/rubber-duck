## Purpose

`src/workflows` contains multi-step product workflows that run as duck implementations.

## Operational Flow

- `main.build_ducks(...)` maps workflow duck types to concrete classes:
  - `registration` -> `RegistrationWorkflow`
  - `assignment_feedback` -> `AssignmentFeedbackWorkflow`
- `RegistrationWorkflow` runs `Registration.run(...)`, summarizes progress, and hands off continuation guidance to the configured registration bot tool.
- `AssignmentFeedbackWorkflow` collects a markdown report, resolves assignment/project, loads rubric/rules, grades each rubric item, and returns markdown-formatted feedback.

## Dependencies

- Uses `AIClient` agents for project detection fallback and rubric-item grading.
- Uses Discord messaging/read-url hooks passed in from runtime wiring.

## Failure Modes and Guardrails

- Registration handles timeout/permission errors and can notify TA channel on failures.
- Assignment feedback requires markdown uploads and supported assignment names; unsupported or missing inputs terminate with explicit conversation messages.
