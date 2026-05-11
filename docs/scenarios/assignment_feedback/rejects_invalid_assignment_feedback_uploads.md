# Rejects Invalid Assignment Feedback Uploads

## Purpose

Validate feedback uploads.

---

# Context

An assignment feedback conversation is active in a Discord thread and is
waiting for the student's report upload.

---

# Action

The student submits a non-markdown upload, omits the upload, exceeds the
allowed upload attempts, or submits a report for an unsupported
assignment.

---

# Interaction

| Action | Outcome |
| --- | --- |
| Non-markdown upload | Prompts the student to retry while upload attempts remain. |
| Missing upload | Prompts the student to retry while upload attempts remain. |
| Upload attempts exceeded | Terminates the upload attempt. |
| Unsupported assignment | Ends the conversation with an explicit unsupported-assignment message. |

---

# Outcome

Invalid assignment feedback uploads do not produce grading feedback and
receive retry or termination messaging appropriate to the invalid input.

---

# Related Scenarios

- [Grades markdown report upload](grades_markdown_report_upload.md)
- [Reports missing sections as unsatisfactory](reports_missing_sections_as_unsatisfactory.md)
