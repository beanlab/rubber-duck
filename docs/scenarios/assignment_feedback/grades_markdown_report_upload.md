# Grades Markdown Report Upload

## Purpose

Grade report submissions.

---

# Context

A configured duck has `duck_type` set to `assignment_feedback`, and a
student has started a new assignment feedback conversation thread.

---

# Action

The student follows any initial instructions and uploads a supported
markdown report for a supported assignment.

---

# Interaction

| Action | Outcome |
| --- | --- |
| Initial instructions are configured. | The application sends the initial instructions before prompting for the report upload. |
| The workflow is ready for the report upload. | The application lists supported assignments and prompts for a markdown upload. |
| The student uploads a supported markdown report. | The application detects the assignment from report headers, using AI fallback selection when needed. |
| The assignment is supported. | The application returns rubric-based grading feedback in markdown format. |

---

# Outcome

Supported markdown report uploads produce rubric-based grading feedback
for the detected assignment.

---

# Related Scenarios

- [Rejects invalid assignment feedback uploads](rejects_invalid_assignment_feedback_uploads.md)
- [Reports missing sections as unsatisfactory](reports_missing_sections_as_unsatisfactory.md)
