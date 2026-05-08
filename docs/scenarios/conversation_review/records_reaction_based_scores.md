# Records Reaction-Based Scores

## Purpose

Capture reviewer scores.

---

# Context

A conversation review workflow has presented a queued student
conversation to a reviewer in a Discord thread.

---

# Action

The reviewer reacts with a numeric score from `1️⃣` through `5️⃣`, skips
with `⏭️`, or enters optional written feedback after numeric scoring.

---

# Interaction

| Action | Outcome |
| --- | --- |
| Numeric reaction from `1️⃣` through `5️⃣` | Records the numeric review score. |
| `⏭️` reaction | Records that the conversation was skipped. |
| Optional written feedback after numeric scoring | Records the written feedback with the review result. |

---

# Outcome

Reaction-based review input is recorded for later metrics and reporting.

---

# Related Scenarios

- [Serves queued conversations for review](serves_queued_conversations_for_review.md)
- [Exports metric tables](../admin/exports_metric_tables.md)
