# Application Interface

## Purpose

Rubber Duck is a configurable Discord bot platform for AI-assisted learning workflows.

At the black-box level, the application:

- receives Discord messages in configured channels
- routes each message into either admin command handling or a duck workflow
- creates and manages private thread conversations for duck workflows
- runs AI-backed conversation and workflow logic according to duck configuration
- records messages, usage, and feedback metrics for later export and reporting

The intended workflow is:

1. An operator starts the app with a configuration file.
2. The bot announces availability in the configured admin channel.
3. Users send messages in configured duck channels.
4. The app creates a private thread per new duck conversation and runs the configured workflow.
5. Admins run commands in the admin channel for health checks, metrics export, logs, reports, and workflow visibility.

## Operating Model

The runtime contract is Discord-first and config-driven.

- The app runs as a single process started from `python -m src.main`.
- Behavior is driven by a resolved config (local file or S3 URI).
- Each configured channel can map to a named global duck or an inline duck definition.
- Incoming messages are routed by channel identity and workflow state:
  - admin channel => command workflow
  - configured duck channel => new duck-orchestrator workflow
  - existing active conversation thread => forwarded into the active workflow queue
- Unmatched non-admin/non-configured messages are ignored.

## Startup Interface

### `python -m src.main [--config <path-or-s3-uri>] [--debug] [--log-path <path>]`

Starts the bot runtime.

Inputs:

- `--config`: optional local JSON/YAML path or `s3://...` URI
- `--debug`: optional flag for debug log level
- `--log-path`: optional path used for file-based logging

Expected outcome on success:

- Loads and resolves config including recursive `$include` directives.
- Connects runtime dependencies (Discord client, SQL metrics/session, configured ducks/tools).
- Starts the Discord bot loop.
- Sends `Duck online` to the configured admin channel when ready.

Config fallback behavior:

- If `--config` is omitted, the app attempts to read `CONFIG_FILE_S3_PATH` from environment variables.

User-visible/operator-visible failure behavior:

- If required runtime dependencies or configuration are invalid, startup fails and logs an error.
- If `--log-path` is omitted, runtime continues and warns that logging is console-only.

## Interface Guarantees

At the black-box level, Rubber Duck provides these behavior categories:

- Admin command handling in one configured admin channel.
- Configured duck channel conversations that always begin in a private thread.
- Thread-based AI workflow execution for supported duck types.
- SQL-backed recording of message/usage/feedback telemetry.
- Export/report surfaces through admin commands.
- Graceful close messaging for duck conversations.

Successful runtime interactions either:

- send Discord messages/reactions/files,
- create Discord threads,
- or produce command outputs and artifacts (e.g., zip/csv/image files).

When a workflow fails unexpectedly:

- the thread receives an error-code message,
- the conversation is then closed with `*This conversation has been closed.*`.

## Message Routing Contract

### General inbound message filters

The bot ignores:

- messages from itself
- messages from other bots
- messages starting with `//`

### Admin-channel behavior

Messages in the configured admin channel are treated as commands.

- `!help` returns a generated help list of registered commands.
- unknown commands return `Unknown command. Try !help`.
- command execution errors return a generic unexpected-error message.

### Duck-channel behavior

A message in a configured duck channel starts a new duck workflow.

Expected observable behavior:

- The app creates a thread using the first 20 characters of the triggering message.
- The user is mentioned in the new thread.
- The parent channel receives a join link message mentioning the user.
- If the original message contains `duck`, the app adds a 🦆 reaction to it.

### Active-thread behavior

Messages in an active conversation thread are delivered to the running workflow via its message queue.

## Duck Workflow Contract

Configured ducks are selected by `duck_type`.

Supported duck types:

- `agent_led_conversation`
- `user_led_conversation`
- `conversation_review`
- `registration`
- `assignment_feedback`

### Shared lifecycle behavior

- Duck workflows run inside the created thread.
- On completion (or handled failure), the app sends `*This conversation has been closed.*`.
- Completed duck conversations are recorded for feedback-queue processing when applicable.

### `agent_led_conversation`

- Runs a one-shot agent response flow in the thread.

### `user_led_conversation`

- Sends configured introduction text.
- Continues turn-based conversation until completion/timeout conditions are reached.

### `conversation_review`

- Serves queued student conversations to TA/reviewer threads.
- Uses reaction-based scoring (`1️⃣`-`5️⃣`, skip via `⏭️`).
- Prompts for optional written feedback after numeric scoring.
- Ends inactive sessions with timeout messaging.

### `registration`

Expected user-facing sequence:

- prompt for Net ID
- Net ID format validation
- email verification challenge with retry/resend path
- nickname selection and validation
- role assignment flow

Observable failure/guardrail behavior includes:

- timeout closes conversation with timeout message
- repeated invalid verification tokens terminate registration attempt
- permission issues during nickname/role assignment notify configured TA channel and terminate flow

### `assignment_feedback`

Expected user-facing sequence:

- optional initial instructions
- list of supported assignments
- prompt for markdown upload (up to three attempts)
- assignment detection from report headers, with AI fallback selection
- rubric-based grading response in markdown format

Observable failure/guardrail behavior includes:

- non-markdown or missing uploads trigger retry prompts
- unsupported assignment names terminate with an explicit unsupported message
- missing report sections produce explicit unsatisfactory rubric feedback for those sections

## Admin Command Contract

The following commands are registered and available through admin-channel command routing.

### `!status`

- Returns `I am alive. 🦆`.

### `!messages`, `!usage`, `!feedback`

- Each command returns a zip file export for its respective table.

### `!metrics`

- Returns all three table exports (`messages`, `usage`, `feedback`).

### `!report`

- `!report` / `!report help` / `!report h` return report help text.
- other valid forms return generated report images and/or text output.
- failures return an explicit report-generation error message.

### `!log`

- If logging path is configured and log files exist, returns a zip of logs.
- If logging is not configured, returns `Log export disabled: no log path configured.`
- If no logs are present, returns a no-logs message.

### `!active [full]`

- `!active` returns workflow counts by type.
- `!active full` returns detailed active workflow entries with Mountain Time timestamps.

### `!cache`

- `!cache` lists current cache entries and sends a CSV report.
- `!cache cleanup` removes expired entries.
- `!cache remove <cache_tool> <entry_index>` removes one entry.
- `!cache clear confirm` clears all cache entries.
- invalid forms return usage/help-style error messages.

## Configuration Contract

The external config contract includes:

- source: local path or S3 URI
- format: JSON or YAML
- recursive `$include` support with optional JSONPath selectors
- deep-merge semantics for dict-style includes

Required top-level runtime sections include:

- `sql`
- `containers`
- `tools`
- `ducks`
- `servers`
- `admin_settings`
- `ai_completion_retry_protocol`
- `reporter_settings`
- `sender_email`

Optional sections include:

- `feedback_notifier_settings`
- `cache_cleanup_settings`
- `agents_as_tools`

## Observable Conventions

The following conventions are part of the user/operator-observable contract:

- Channel and server routing is ID-based from config.
- New duck conversations are thread-scoped.
- Thread inactivity and workflow-complete conditions close user-facing conversations.
- Admin command outputs are delivered in Discord as messages/files.
- Metrics and feedback are persisted for export/reporting behavior.

## Out of Scope

This interface document does not define:

- internal class/module boundaries
- AI prompt text contents
- SQL schema implementation details
- internal dependency injection/wiring mechanics
- non-observable helper utilities
