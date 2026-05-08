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
| The reviewer reacts with a numeric score from `1️⃣` through `5️⃣`. | The application records the numeric review score. |
| The reviewer reacts with `⏭️`. | The application records that the conversation was skipped. |
| The reviewer enters optional written feedback after numeric scoring. | The application records the written feedback with the review result. |

---

# Outcome

Reaction-based review input is recorded for later metrics and reporting.

---

# Related Scenarios

- [Serves queued conversations for review](serves_queued_conversations_for_review.md)
- [Exports metric tables](../admin/exports_metric_tables.md)
