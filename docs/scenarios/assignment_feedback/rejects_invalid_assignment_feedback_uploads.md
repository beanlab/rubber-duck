# Rejects Invalid Assignment Feedback Uploads

## Purpose

Validate feedback uploads.

---

# Context

An assignment feedback workflow is running in a Discord conversation
thread and is waiting for the student's report upload.

---

# Action

The student submits a non-markdown upload, omits the upload, exceeds the
allowed upload attempts, or submits a report for an unsupported
assignment.

---

# Interaction

| Action | Outcome |
| --- | --- |
| The student submits a non-markdown upload. | The application prompts the student to retry while upload attempts remain. |
| The student omits the upload. | The application prompts the student to retry while upload attempts remain. |
| The student exceeds the allowed upload attempts. | The application terminates the upload attempt. |
| The student submits a report for an unsupported assignment. | The application terminates the workflow with an explicit unsupported-assignment message. |

---

# Outcome

Invalid assignment feedback uploads do not produce grading feedback and
receive retry or termination messaging appropriate to the invalid input.

---

# Related Scenarios

- [Grades markdown report upload](grades_markdown_report_upload.md)
- [Reports missing sections as unsatisfactory](reports_missing_sections_as_unsatisfactory.md)
