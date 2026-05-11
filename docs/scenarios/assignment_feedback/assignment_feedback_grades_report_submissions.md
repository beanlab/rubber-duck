# Assignment Feedback Grades Report Submissions

## Purpose

Grade report submissions.

---

# Context

A student has started an assignment feedback conversation thread.

---

# Action

The student follows any initial instructions and submits a report upload
for assignment feedback.

---

# Interaction

| Action | Outcome |
| --- | --- |
| Initial instructions configured. | Sends the initial instructions before prompting for the report upload. |
| Ready for report upload. | Lists supported assignments and prompts for a markdown upload. |
| Supported markdown report for a supported assignment. | Detects or asks for the assignment and returns rubric-based grading feedback in markdown format. |
| Report is missing sections required by the assignment rubric. | Includes explicit unsatisfactory rubric feedback for each missing required section. |
| Non-markdown upload. | Prompts the student to retry while upload attempts remain. |
| Missing upload. | Prompts the student to retry while upload attempts remain. |
| Upload attempts exceeded. | Ends the upload attempt. |
| Unsupported assignment. | Ends the conversation with an explicit unsupported-assignment message. |

---

# Outcome

Supported markdown report uploads produce rubric-based grading feedback
for the detected assignment. Invalid uploads do not produce grading
feedback and receive retry or termination messaging appropriate to the
invalid input.
