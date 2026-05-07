# Serves Queued Conversations For Review

## Purpose

Present feedback queue items.

---

# Context

A configured duck has `duck_type` set to `conversation_review`, and
student conversations have been recorded for feedback-queue processing.

---

# Action

A TA or reviewer starts a conversation review workflow.

---

# Outcome

The application serves queued student conversations into the reviewer
thread so the reviewer can score or skip each conversation and optionally
provide written feedback.

---

# Related Scenarios

- [Records reaction-based scores](records_reaction_based_scores.md)
- [Closes inactive review sessions](closes_inactive_review_sessions.md)
- [Closes conversation after completion](../conversations/closes_conversation_after_completion.md)
