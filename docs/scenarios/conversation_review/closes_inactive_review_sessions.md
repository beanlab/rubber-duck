# Closes Inactive Review Sessions

## Purpose

Timeout idle reviews.

---

# Context

A conversation review session is active in a reviewer thread and is
waiting for reviewer input.

---

# Action

The session remains inactive until the configured timeout condition is
reached.

---

# Outcome

The application ends the inactive review session with timeout messaging.

---

# Related Scenarios

- [Serves queued conversations for review](serves_queued_conversations_for_review.md)
- [Closes conversation after completion](../conversations/closes_conversation_after_completion.md)
