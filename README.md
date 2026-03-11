# Rubber Duck

Rubber Duck is a configurable Discord bot platform for AI-assisted learning workflows.
It supports multiple "duck" behaviors (Socratic tutoring, stats/code execution, registration, assignment feedback, and conversation review), all selected through config.

## What This Project Does

- Routes Discord messages into workflow-based conversations
- Runs OpenAI Responses API agents with optional tool calling
- Supports containerized Python execution tools for stats/code workflows
- Tracks messages, usage, and feedback metrics in SQL
- Provides admin channel commands for status, reports, logs, and metrics export
- Supports local and S3-backed configuration with composable `$include` directives

## Repository Layout

- `src/main.py`: app entrypoint and system wiring
- `src/bot/`: Discord client integration
- `src/rubber_duck_app.py`: channel/admin message routing
- `src/duck_orchestrator.py`: thread creation + duck dispatch
- `src/conversation/`: conversation implementations
- `src/workflows/`: registration and assignment feedback workflows
- `src/gen_ai/`: OpenAI client orchestration + agent execution
- `src/armory/`: tool registration, Python tool execution, and caching
- `src/storage/` + `src/metrics/`: SQL persistence and reporting
- `prompts/`: prompt assets used by configured ducks/agents
- `rubrics/`: grading rubrics for assignment feedback workflows
- `datasets/`: local datasets staged into container tools
- `docs/`: getting started and deployment docs

## Quick Start (Local)

### Prerequisites

- Python 3.11
- Poetry
- Docker (required if you enable container tools such as stats/code execution)
- Discord bot token
- OpenAI API key

### Install

```bash
git clone https://github.com/beanlab/rubber-duck.git
cd rubber-duck
poetry install
```

### Configure

1. Copy and adapt local config:

```bash
cp local-config-example.yaml local-testing-configs/local_<name>_config.yaml
```

2. Set required environment variables:

```bash
export DISCORD_TOKEN=your_discord_token
export OPENAI_API_KEY=your_openai_api_key
```

3. Update your local config with real channel/server/admin IDs.

### Run

```bash
poetry run python -m src.main --config ./local-testing-configs/local_<name>_config.yaml --debug
```

Optional flags:

- `--log-path <path>`: write logs to a file path in addition to console
- `--config s3://...`: load config from S3

If `--config` is omitted, `src.main` reads `CONFIG_FILE_S3_PATH` from env.

## Duck Types (Implemented)

Configured ducks are built by `duck_type`.

- `agent_led_conversation`: one-shot or agent-led interaction
- `user_led_conversation`: chat flow where user messages drive turns
- `conversation_review`: TA/reviewer scoring workflow
- `registration`: NetID/email verification + role assignment workflow
- `assignment_feedback`: rubric-based grading workflow for markdown reports

## Admin Commands

Commands are processed in the configured admin channel.

- `!help`: list commands
- `!status`: health check
- `!metrics`: export messages/usage/feedback tables as zip files
- `!report`: generate preconfigured report outputs
- `!log`: export log files
- `!active [full]`: show active workflow summary/details

## Configuration Model

Configuration supports both local files and S3 URIs, in JSON or YAML.

Key capabilities:

- Recursive `$include` references
- Optional JSONPath extraction with `path@$.json.path`
- Deep-merge behavior for dictionary includes
- Cycle detection for includes
- SQL config values may reference env vars via `env:VAR_NAME`

Primary examples:

- `local-config-example.yaml`
- `production-config.yaml`

## Deployment Summary

CI/CD is defined in `.github/workflows/ci-cd.yml`.

On pushes to `master`, the workflow currently:

- Builds Docker image
- Pushes image tags to ECR
- Uploads environment/config artifacts to S3
- Sends deployment notifications to Discord webhook

## Documentation

- [Getting Started](docs/getting-started.md)
- [Deployment Guide](docs/deployment.md)
- Archived legacy docs: `docs/old/`

## License

MIT. See [LICENSE](LICENSE).
