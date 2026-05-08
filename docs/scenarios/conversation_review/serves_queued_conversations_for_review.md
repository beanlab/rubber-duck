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

# Interaction

| Action | Outcome |
| --- | --- |
| A reviewer starts the conversation review workflow. | The application serves a queued student conversation into the reviewer thread. |
| The reviewer continues through the queue. | The application presents each available queued conversation for scoring or skipping. |
| The reviewer chooses to provide written feedback. | The application accepts optional written feedback for the reviewed conversation. |

---

# Outcome

Queued student conversations are presented in the reviewer thread so the
reviewer can score, skip, or comment on them.

---

# Related Scenarios

- [Records reaction-based scores](records_reaction_based_scores.md)
- [Closes inactive review sessions](closes_inactive_review_sessions.md)
- [Closes conversation after completion](../conversations/closes_conversation_after_completion.md)
