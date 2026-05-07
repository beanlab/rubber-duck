# Reports Workflow Failure To Thread

## Purpose

Expose workflow failures.

---

# Context

A duck workflow is running inside its Discord conversation thread.

---

# Action

The workflow fails unexpectedly after the conversation thread has been
created.

---

# Outcome

The thread receives an error-code message, and the application then
sends `*This conversation has been closed.*`.

---

# Related Scenarios

- [Closes conversation after completion](closes_conversation_after_completion.md)
