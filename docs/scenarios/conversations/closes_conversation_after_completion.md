# Closes Conversation After Completion

## Purpose

Close completed threads.

---

# Context

A duck conversation is active inside its private Discord thread.

---

# Action

The conversation ends normally or reaches a handled completion condition
such as timeout.

---

# Outcome

The bot sends `*This conversation has been closed.*` in the thread.
Completed duck conversations that are eligible for review are available
for later feedback processing.

---

# Related Scenarios

- [Reports conversation failure to thread](reports_conversation_failure_to_thread.md)
- [Forwards active thread messages](../routing/forwards_active_thread_messages.md)
