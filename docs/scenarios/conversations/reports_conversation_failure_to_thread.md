# Reports Conversation Failure To Thread

## Purpose

Expose conversation failures.

---

# Context

A duck conversation is active in its private Discord thread.

---

# Action

An unexpected failure prevents the conversation from continuing after
the thread has been created.

---

# Outcome

The thread receives an error-code message, and the bot then sends
`*This conversation has been closed.*`.

---

# Related Scenarios

- [Closes conversation after completion](closes_conversation_after_completion.md)
