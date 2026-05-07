# Closes Conversation After Completion

## Purpose

Close completed threads.

---

# Context

A duck workflow is running inside its Discord conversation thread.

---

# Action

The workflow completes normally or reaches a handled completion
condition such as timeout.

---

# Outcome

The application sends `*This conversation has been closed.*` in the
thread. Completed duck conversations are recorded for feedback-queue
processing when that workflow type participates in feedback review.

---

# Related Scenarios

- [Reports workflow failure to thread](reports_workflow_failure_to_thread.md)
- [Forwards active thread messages](../routing/forwards_active_thread_messages.md)
