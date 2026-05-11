# Grades Markdown Report Upload

## Purpose

Grade report submissions.

---

# Context

A student has started a new assignment feedback conversation thread.

---

# Action

The student follows any initial instructions and uploads a supported
markdown report for a supported assignment.

---

# Interaction

| Action | Outcome |
| --- | --- |
| Initial instructions configured | Sends the initial instructions before prompting for the report upload. |
| Ready for report upload | Lists supported assignments and prompts for a markdown upload. |
| Supported markdown report | Detects or asks for the assignment associated with the report. |
| Supported assignment | Returns rubric-based grading feedback in markdown format. |

---

# Outcome

Supported markdown report uploads produce rubric-based grading feedback
for the detected assignment.

---

# Related Scenarios

- [Rejects invalid assignment feedback uploads](rejects_invalid_assignment_feedback_uploads.md)
- [Reports missing sections as unsatisfactory](reports_missing_sections_as_unsatisfactory.md)
