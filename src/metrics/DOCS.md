## Purpose

`src/metrics` captures runtime usage/message/feedback data and exposes reporting/review workflows.

## Operational Flow

- `AIClient` writes message and usage metrics through `SQLMetricsHandler` hooks.
- `DuckOrchestrator` calls `FeedbackManager.remember_conversation(...)` after a conversation closes.
- The builder in `src/workflows/conversation_review/` serves queued conversations in reviewer threads; `main.py` constructs persistent FIFO queues from configured review targets, and `SQLMetricsHandler` records ratings/comments.
- `Reporter` reads metrics tables and generates predefined or argument-driven plots for `!report`.

## Dependencies

- Depends on `src/storage/sql_metrics.py` for persistent metrics storage.
- `FeedbackManager` provides access to the per-target queues constructed by `main.py` using `utils.persistent_queue`.

## Failure Modes and Guardrails

- TA-review timeouts re-queue pending conversations.
- Reporter command parsing raises `ArgumentError` for invalid flag combinations/fields and returns help text from command handlers.
