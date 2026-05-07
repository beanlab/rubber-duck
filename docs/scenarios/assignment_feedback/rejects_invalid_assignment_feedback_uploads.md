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

# Outcome

Non-markdown or missing uploads trigger retry prompts for up to three
attempts. Unsupported assignment names terminate the workflow with an
explicit unsupported-assignment message.

---

# Related Scenarios

- [Grades markdown report upload](grades_markdown_report_upload.md)
- [Reports missing sections as unsatisfactory](reports_missing_sections_as_unsatisfactory.md)
