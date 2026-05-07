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

# Outcome

The application uses reaction-based scoring for `1️⃣` through `5️⃣`,
supports skipping with `⏭️`, prompts for optional written feedback after
numeric scoring, and records the review result for later metrics and
reporting.

---

# Related Scenarios

- [Serves queued conversations for review](serves_queued_conversations_for_review.md)
- [Exports metric tables](../admin/exports_metric_tables.md)
