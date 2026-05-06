# Code Duck Traceback Rubric Plan

## Framework Refactor

No framework refactor is needed.

`CodeDuckWorkflow` uses one conversation-review agent to decide and send the next student-facing response:

- conversation review receives the rubric, current project, and script-style conversation transcript
- the workflow sends the review response directly to the thread
- an empty review response ends the workflow

## Feature Addition

Update the code-duck behavior-facing assets so they match the intended TA/student debugging workflow:

- document that code-duck rubrics include complete learner-level projects and exact traceback scenarios
- replace the empty conversation-review prompt with instructions for selecting the next student question from the full conversation
- make the conversation-review prompt produce the student-facing response directly
- rewrite `rubrics/CS110/code-duck/variables.yaml` around one complete `grade_summary.py` program with documented traceback strings captured from actual runs
- update focused tests for the user-facing payload and rubric shape where needed
