# Application Interface

## Purpose

Document the external contract for Rubber Duck so users and operators can
understand how to configure, run, and interact with the system.

## Scope

Included:
- user-visible Discord workflows and failure modes
- admin command behavior and operational outputs
- startup interface and configuration contract
- external integrations and data boundaries

Excluded:
- internal module structure
- AI prompt contents
- SQL schema implementation details
- private refactors and helper utilities

## User Interface

### User-visible workflow overview

- The bot receives Discord messages in configured channels.
- Messages are routed into either admin command handling or a duck workflow.
- Duck workflows run inside private threads created per conversation.
- The app records messages, usage, and feedback for later export and reporting.

Expected user-visible sequence:
- The operator starts the app with a configuration file.
- The bot announces availability in the configured admin channel.
- Users send messages in configured duck channels.
- The app creates a private thread and runs the configured workflow.

### Message routing contract

General inbound message filters:
- messages from the bot are ignored
- messages from other bots are ignored
- messages starting with `//` are ignored

Admin-channel behavior:
- Messages in the configured admin channel are treated as commands.
- `!help` returns a generated help list of registered commands.
- Unknown commands return `Unknown command. Try !help`.
- Command execution errors return a generic unexpected-error message.

Duck-channel behavior:
- A message in a configured duck channel starts a new duck workflow.
- The app creates a thread using the first 20 characters of the triggering message.
- The user is mentioned in the new thread.
- The parent channel receives a join link message mentioning the user.
- If the original message contains `duck`, the app adds a 🦆 reaction to it.

Active-thread behavior:
- Messages in an active conversation thread are delivered to the running workflow.

### Duck workflow contract

Supported duck types:
- `agent_led_conversation`
- `user_led_conversation`
- `conversation_review`
- `registration`
- `assignment_feedback`

Shared lifecycle behavior:
- Duck workflows run inside the created thread.
- On completion or handled failure, the app sends `*This conversation has been closed.*`.
- Completed duck conversations are recorded for feedback-queue processing when applicable.

`agent_led_conversation`:
- Runs a single agent session per invocation in the thread.
- The agent may call tools during the session, but the workflow does not loop on user messages.

`user_led_conversation`:
- Sends configured introduction text.
- Continues turn-based conversation until completion or timeout conditions are reached.

`conversation_review`:
- Serves queued student conversations to TA or reviewer threads.
- Uses reaction-based scoring (`1️⃣`-`5️⃣`, skip via `⏭️`).
- Prompts for optional written feedback after numeric scoring.
- Ends inactive sessions with timeout messaging.

`registration`:
Expected user-facing sequence:
- prompt for Net ID
- Net ID format validation
- email verification challenge with retry and resend path
- nickname selection and validation
- role assignment flow

Observable failure or guardrail behavior:
- timeout closes conversation with timeout message
- repeated invalid verification tokens terminate registration attempt
- permission issues during nickname or role assignment notify the configured TA channel

`assignment_feedback`:
Expected user-facing sequence:
- optional initial instructions
- list of supported assignments
- prompt for markdown upload with up to three attempts
- assignment detection from report headers with AI fallback selection
- rubric-based grading response in markdown format

Observable failure or guardrail behavior:
- non-markdown or missing uploads trigger retry prompts
- unsupported assignment names terminate with an explicit unsupported message
- missing report sections produce explicit unsatisfactory rubric feedback

## Operations Interface

### Operating model

- The app runs as a single process started from `python -m src.main`.
- Behavior is driven by a resolved config loaded at startup.
- `src.main` is the composition root and wires all runtime dependencies from config.
- The resolved config is authoritative during runtime and is not reloaded.

### Startup interface

`python -m src.main [--config <path-or-s3-uri>] [--debug] [--log-path <path>]`

Inputs:
- `--config` optional local JSON or YAML path or `s3://...` URI
- `--debug` optional flag for debug log level
- `--log-path` optional path used for file-based logging

Expected outcome on success:
- Loads and resolves config including recursive `$include` directives.
- Connects runtime dependencies such as Discord client, SQL session, ducks, and tools.
- Starts the Discord bot loop.
- Sends `Duck online` to the configured admin channel when ready.

Config fallback behavior:
- If `--config` is omitted, the app attempts to read `CONFIG_FILE_S3_PATH` from the environment.

Failure behavior:
- Invalid configuration or missing dependencies cause startup to fail and log an error.
- If `--log-path` is omitted, runtime continues and warns that logging is console-only.

### Admin command contract

The following commands are registered and available through admin-channel routing:

`!status`:
- Returns `I am alive. 🦆`.

`!messages`, `!usage`, `!feedback`:
- Each command returns a zip file export for its respective table.

`!metrics`:
- Returns all three table exports.

`!report`:
- `!report` or `!report help` or `!report h` return report help text.
- Other valid forms return generated report images or text output.
- Failures return an explicit report-generation error message.

`!log`:
- If logging path is configured and log files exist, returns a zip of logs.
- If logging is not configured, returns `Log export disabled: no log path configured.`
- If no logs are present, returns a no-logs message.

`!active [full]`:
- `!active` returns workflow counts by type.
- `!active full` returns detailed active workflow entries with Mountain Time timestamps.

`!cache`:
- `!cache` lists current cache entries and sends a CSV report.
- `!cache cleanup` removes expired entries.
- `!cache remove <cache_tool> <entry_index>` removes one entry.
- `!cache clear confirm` clears all cache entries.
- Invalid forms return usage or help-style error messages.

### Configuration contract

The external config contract includes:
- source: local path or S3 URI
- format: JSON or YAML
- recursive `$include` support with optional JSONPath selectors
- deep-merge semantics for dict-style includes
- a single resolved config assembled before runtime wiring begins

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

Configuration-driven wiring guarantees:
- The resolved config defines the full runtime wiring for ducks, tools, containers, channels, and workflows.
- `src.main` consumes that resolved config to construct runtime subsystems and map channels to duck workflows.

## Constraints and Assumptions

- The bot runs as a single process started by operators.
- Discord credentials must be available at runtime.
- SQL connectivity is required for metrics and feedback persistence.
- S3 access is required only when configuration is loaded from `s3://...` URIs.
- Channel and server routing is ID-based from config.
- New duck conversations are thread-scoped.

## Open Questions

None.

## Related Documents

- application-design/intent.md
- application-design/structure.md
- application-design/change-workflow.md
- docs/deployment.md
- docs/getting-started.md
