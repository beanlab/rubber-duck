## Purpose

`src/workflows` contains multi-step product workflows that run as duck implementations.

## Operational Flow

- `main.build_ducks(...)` maps workflow duck types to concrete classes:
  - `registration` -> `RegistrationWorkflow`
  - `assignment_feedback` -> `AssignmentFeedbackWorkflow`
  - `student_duck` -> `StudentDuckWorkflow`
- `RegistrationWorkflow` runs `Registration.run(...)`, summarizes progress, and hands off continuation guidance to the configured registration bot tool.
- `AssignmentFeedbackWorkflow` collects a markdown report, resolves assignment/project, loads rubric/rules, grades each rubric item, and returns markdown-formatted feedback.
- `StudentDuckWorkflow` sends an initial topic prompt, uses the first user reply only to select the topic/rubric, then reviews each following user response with separate error and omission checker agents, forces their structured output schemas in code, attaches their structured results to that user turn, and asks a learner-style follow-up through a user-facing student agent.
- `StudentDuckRubricTools` exposes `select_student_duck_rubric` so workflow-owned topic selection or the user-facing student agent can choose a YAML rubric from configured roots; the workflow stores that selection by thread and passes it into subsequent checker calls.

## Dependencies

- Uses `AIClient` agents for project detection fallback and rubric-item grading.
- Uses `AIClient` agents for student-duck error checks, omission checks, and learner-style follow-up generation.
- Uses Discord messaging/read-url hooks passed in from runtime wiring.
- Uses `rubric_roots` to constrain student-duck dynamic rubric selection.

## Failure Modes and Guardrails

- Registration handles timeout/permission errors and can notify TA channel on failures.
- Assignment feedback requires markdown uploads and supported assignment names; unsupported or missing inputs terminate with explicit conversation messages.
- Student-duck error and omission checks receive the accumulated conversation context. Empty rubric files are treated as no rubric criteria.
- Student-duck checker configs do not need `output_format`; checker outputs are always constrained to `check_type` and `assessment` by the workflow.
- Student-duck user-message collection stays workflow-owned; the user-facing student agent may use `conclude_conversation`, but not `talk_to_user`, without bypassing review checks.
- Student-duck rubric selection does not expose arbitrary file access; only non-empty YAML rubrics under configured roots are cataloged.
