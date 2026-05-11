# Conversation Review Scores Queued Conversations

## Purpose

Review student conversations.

---

# Context

Student conversations have been recorded for feedback-queue processing.

---

# Action

A TA or reviewer starts a conversation review session and reviews queued
student conversations.

---

# Interaction

| Action | Outcome |
| --- | --- |
| Review session starts. | Serves a queued student conversation into the reviewer thread. |
| Reviewer continues through the queue. | Presents each available queued conversation for scoring or skipping. |
| Numeric reaction from `1️⃣` through `5️⃣`. | Records the numeric review score. |
| `⏭️` reaction. | Records that the conversation was skipped. |
| Optional written feedback after numeric scoring. | Records the written feedback with the review result. |
| Session remains inactive until the configured timeout condition is reached. | Ends the inactive review session with timeout messaging. |

---

# Outcome

Queued student conversations are presented in the reviewer thread so the
reviewer can score, skip, or comment on them. Reaction-based review
input is recorded for later metrics and reporting.

---

# Related Scenarios

- [Ends conversation threads](../conversations/ends_conversation_threads.md)
- [Exports metric tables](../admin/exports_metric_tables.md)
