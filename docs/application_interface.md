# Application Interface

## Purpose

Rubber Duck is a configurable Discord bot platform for AI-assisted learning workflows.

At the black-box level, the application:

- receives Discord messages in configured channels
- routes each message into either admin command handling or a duck workflow
- creates and manages private thread conversations for duck workflows
- runs AI-backed workflow logic according to duck configuration
- records messages, usage, and feedback for later export and reporting

## Scope

Included:

- user-visible Discord workflows, states, and failure modes
- admin command behavior and operational outputs
- startup interface and configuration contract
- external integrations and data boundaries visible to operators

Excluded:

- internal module structure and class layout
- prompt implementation details
- SQL schema internals beyond external export and persistence expectations
- private refactors, helper utilities, and other implementation-only changes

## User Interface

### Workflow overview

Expected user-visible sequence:

1. An operator starts the app with a configuration file.
2. The bot announces availability in the configured admin channel.
3. Users send messages in configured duck channels.
4. The app creates a private thread for each new duck conversation.
5. The configured workflow runs inside that thread.

Successful runtime interactions produce one or more of the following:

- Discord messages, reactions, or file attachments
- new Discord threads
- exported artifacts such as zip, CSV, image, or text outputs

### Message routing contract

General inbound message filters:

- messages from the bot are ignored
- messages from other bots are ignored
- messages starting with `//` are ignored
- unmatched non-admin and non-configured messages are ignored

Admin-channel behavior:

- messages in the configured admin channel are treated as commands
- `!help` returns a generated help list of registered commands
- unknown commands return `Unknown command. Try !help`
- command execution errors return a generic unexpected-error message

Duck-channel behavior:

- a message in a configured duck channel starts a new duck workflow
- the app creates a thread using the first 20 characters of the triggering message
- the user is mentioned in the new thread
- the parent channel receives a join-link message mentioning the user
- if the original message contains `duck`, the app adds a `🦆` reaction

Active-thread behavior:

- messages in an active conversation thread are delivered to the running workflow

### Duck workflow contract

Supported duck types:

- `agent_led_conversation`
- `user_led_conversation`
- `conversation_review`
- `registration`
- `assignment_feedback`

Shared lifecycle behavior:

- duck workflows run inside the created thread
- on completion or handled failure, the app sends `*This conversation has been closed.*`
- completed duck conversations are recorded for feedback-queue processing when applicable
- unexpected workflow failures surface an error-code message before the conversation closes

`agent_led_conversation`:

- runs a single agent session per invocation in the thread
- the agent may call tools during the session, but the workflow does not loop on later user messages

`user_led_conversation`:

- sends configured introduction text
- continues a turn-based conversation until completion or timeout conditions are reached

`conversation_review`:

- serves queued student conversations to TA or reviewer threads
- uses reaction-based scoring (`1️⃣` through `5️⃣`, skip via `⏭️`)
- prompts for optional written feedback after numeric scoring
- ends inactive sessions with timeout messaging

`registration`:

Expected user-facing sequence:

- prompt for Net ID
- validate Net ID format
- run an email verification challenge with retry and resend paths
- prompt for nickname selection and validate the result
- run the role-assignment flow

Observable failure or guardrail behavior:

- timeout closes the conversation with a timeout message
- repeated invalid verification tokens terminate the registration attempt
- permission issues during nickname or role assignment notify the configured TA channel

`assignment_feedback`:

Expected user-facing sequence:

- send optional initial instructions
- list supported assignments
- prompt for a markdown upload with up to three attempts
- detect the assignment from report headers, with AI fallback selection when needed
- return a rubric-based grading response in markdown format

Observable failure or guardrail behavior:

- non-markdown or missing uploads trigger retry prompts
- unsupported assignment names terminate with an explicit unsupported message
- missing report sections produce explicit unsatisfactory rubric feedback

## Operations Interface

### Operating model

- the app runs as a single process started from `python -m src.main`
- behavior is driven by a resolved config loaded at startup
- each configured channel maps to either admin command handling or a duck workflow
- the resolved config is authoritative for the runtime and is not reloaded after startup

### Startup interface

`python -m src.main [--config <path-or-s3-uri>] [--debug] [--log-path <path>]`

Inputs:

- `--config`: optional local JSON or YAML path, or an `s3://...` URI
- `--debug`: optional flag that enables debug log level
- `--log-path`: optional path used for file-based logging

Expected outcome on success:

- load and resolve config, including recursive `$include` directives
- connect runtime dependencies such as the Discord client, SQL session, ducks, and tools
- start the Discord bot loop
- send `Duck online` to the configured admin channel when ready

Config fallback behavior:

- if `--config` is omitted, the app attempts to read `CONFIG_FILE_S3_PATH` from the environment

Failure behavior:

- invalid configuration or missing dependencies cause startup to fail and log an error
- if `--log-path` is omitted, runtime continues and warns that logging is console-only

### Admin command contract

The following commands are available through admin-channel routing:

`!status`:

- returns `I am alive. 🦆`

`!messages`, `!usage`, `!feedback`:

- each command returns a zip file export for its respective table

`!metrics`:

- returns all three table exports

`!report`:

- `!report`, `!report help`, and `!report h` return report help text
- other valid forms return generated report images or text output
- failures return an explicit report-generation error message

`!log`:

- if logging path is configured and log files exist, returns a zip of logs
- if logging is not configured, returns `Log export disabled: no log path configured.`
- if no logs are present, returns a no-logs message

`!active [full]`:

- `!active` returns workflow counts by type
- `!active full` returns detailed active workflow entries with Mountain Time timestamps

`!cache`:

- `!cache` lists current cache entries and sends a CSV report
- `!cache cleanup` removes expired entries
- `!cache remove <cache_tool> <entry_index>` removes one entry
- `!cache clear confirm` clears all cache entries
- invalid forms return usage or help-style error messages

### Configuration contract

The external configuration contract includes:

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

- the resolved config defines the runtime wiring for ducks, tools, containers, channels, and workflows
- startup consumes that resolved config to construct runtime subsystems and map channels to duck workflows

## Constraints and Assumptions

- the bot runs as a single operator-started process
- Discord credentials must be available at runtime
- SQL connectivity is required for metrics and feedback persistence
- S3 access is required only when configuration is loaded from an `s3://...` URI
- channel and server routing is ID-based from config
- new duck conversations are thread-scoped

## Open Questions

None currently.

## Related Documents

- `application-design/application_interface.md`
- `docs/deployment.md`
- `docs/getting-started.md`
- `docs/backlog/registration-prompt-resume-only-mismatch.md`
