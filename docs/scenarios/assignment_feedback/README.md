# Assignment Feedback Scenarios

Assignment feedback scenarios describe Discord-thread report grading
workflows for ducks configured with `duck_type` set to
`assignment_feedback`.

The shared assignment feedback context is:

- a student has started an assignment feedback conversation thread
- the workflow accepts supported markdown report uploads
- the workflow detects or validates the assignment being graded
- grading feedback is returned to the student in markdown format

## Scenarios

- [Grades markdown report upload](grades_markdown_report_upload.md)
- [Rejects invalid assignment feedback uploads](rejects_invalid_assignment_feedback_uploads.md)
- [Reports missing sections as unsatisfactory](reports_missing_sections_as_unsatisfactory.md)
