# Conversation Scenarios

Conversation scenarios describe behavior inside private Discord threads
created for duck conversations.

The shared conversation context is:

- a routable Discord message has started a private duck conversation
- subsequent thread messages continue the active conversation
- duck responses are sent back to Discord in the thread
- completed or failed conversations close visibly

Platform scenarios describe thread lifecycle behavior. Duck behavior
scenarios describe the response contract for a named duck from the
student or reviewer point of view.

## Scenarios

- [Closes conversation after completion](closes_conversation_after_completion.md)
- [Reports conversation failure to thread](reports_conversation_failure_to_thread.md)
- [Standard Duck supports student learning](standard_duck_supports_student_learning.md)
- [Stats Duck provides statistical outputs](stats_duck_provides_statistical_outputs.md)
