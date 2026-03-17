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

### Prerequisites

- Python 3.11
- Poetry
- Docker (required if you enable container tools such as code execution)
- Discord bot token
- OpenAI API key

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

Primary examples:

- `local-config-example.yaml`
- `production-config.yaml`

## Deployment Summary

CI/CD is defined in `.github/workflows/ci-cd.yml`.

## Documentation

- [Getting Started](docs/getting-started.md)
- [Deployment Guide](docs/deployment.md)
- Archived legacy docs: `docs/old/`

## License

MIT. See [LICENSE](LICENSE).
