## Relevant File Locations

- `src/metrics/csv_metrics.py`
- `src/metrics/feedback_manager.py`
- `src/metrics/feedback.py`
- `src/metrics/reporter.py`
- `src/storage/sql_metrics.py`
- `src/main.py`

## Runtime Entry Flow

- `main._main(...)` constructs `SQLMetricsHandler` and `FeedbackManager`.
- `AIClient` is initialized with metrics hooks: `record_message` and `record_usage`.
- `DuckOrchestrator` is initialized with `feedback_manager.remember_conversation` so completed conversations can be queued for review.
- `setup_workflow_manager(...)` creates `Reporter` and passes it into command handlers.

## Metrics Capture Surfaces

- Message/usage capture:
  - `AIClient` calls `record_message(...)` and `record_usage(...)` during response execution.
- Feedback capture:
  - `HaveTAGradingConversation` collects emoji/text feedback and calls `record_feedback(...)`.
- Storage backends:
  - `SQLMetricsHandler` is the primary runtime backend.
  - `CSVMetricsHandler` is a file-based alternative utility.

## Feedback Review Flow

- `FeedbackManager` keeps per-channel persistent queues of conversations awaiting review.
- `HaveTAGradingConversation` pulls queued conversations, posts student/grading thread links, and records scores from reaction events.
- Timeouts re-queue conversations for later review.

## Reporting Flow

- `Reporter` reads metrics dataframes (`messages`, `usage`, `feedback`) through the metrics handler.
- `!report` commands support predefined reports and argument-driven plots.
- Usage reports compute token-based cost with pricing from reporter config.
