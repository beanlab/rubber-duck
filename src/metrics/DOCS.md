## Purpose

`src/metrics` captures runtime usage/message/feedback data and exposes reporting/review workflows.

## Operational Flow

- `AIClient` writes message and usage metrics through `SQLMetricsHandler` hooks.
- `DuckOrchestrator` calls `FeedbackManager.remember_conversation(...)` after a conversation closes.
- `HaveTAGradingConversation` serves queued conversations in TA review threads, captures emoji/written feedback, and writes feedback records.
- `Reporter` reads metrics tables and generates predefined or argument-driven plots for `!report`.

## Dependencies

- Depends on `src/storage/sql_metrics.py` for persistent metrics storage.
- Depends on queue state from `utils.persistent_queue` via `FeedbackManager`.

## Failure Modes and Guardrails

- TA-review timeouts re-queue pending conversations.
- Reporter command parsing raises `ArgumentError` for invalid flag combinations/fields and returns help text from command handlers.
