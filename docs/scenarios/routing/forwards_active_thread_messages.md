# Forwards Active Thread Messages

## Purpose

Continue active workflows.

---

# Context

A duck workflow is running in a Discord conversation thread, and that
thread is tracked as active.

---

# Action

A non-bot user posts a message in the active conversation thread.

---

# Outcome

The application delivers the message to the running workflow through the
workflow's message queue. The message does not start a new duck
conversation and is not routed as an admin command.

---

# Related Scenarios

- [Closes conversation after completion](../conversations/closes_conversation_after_completion.md)
- [Reports workflow failure to thread](../conversations/reports_workflow_failure_to_thread.md)
