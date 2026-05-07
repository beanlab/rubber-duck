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

# Outcome

The application lists supported assignments, prompts for a markdown
upload, detects the assignment from report headers with AI fallback
selection when needed, and returns rubric-based grading feedback in
markdown format. If initial instructions are configured, the application
sends them before prompting for the report upload.

---

# Related Scenarios

- [Rejects invalid assignment feedback uploads](rejects_invalid_assignment_feedback_uploads.md)
- [Reports missing sections as unsatisfactory](reports_missing_sections_as_unsatisfactory.md)
