# Rubber Duck

Rubber Duck is a configurable Discord bot platform for AI-assisted learning workflows.
It supports multiple "duck" behaviors (Socratic tutoring, stats/code execution, registration, assignment feedback, debugging practice, and conversation review), all selected through config.

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
- `src/workflows/`: registration, assignment feedback, and debugging-practice workflows
- `src/gen_ai/`: OpenAI client orchestration + agent execution
- `src/armory/`: tool registration, Python tool execution, and caching
- `src/storage/` + `src/metrics/`: SQL persistence and reporting
- `src/prompts/`: prompt assets used by configured ducks/agents
- `archive/prompts/`: legacy and unreferenced prompt assets kept for historical reference
- `rubrics/`: grading rubrics for assignment feedback workflows
- `rubrics/examples/`: non-runtime rubric examples and demos
- `datasets/`: local datasets staged into container tools
- `docs/`: getting started and deployment docs
- `scripts/`: developer utility scripts (including metadata generation)
- `archive/`: non-runtime historical and scratch artifacts kept for reference

### Prerequisites

- Python 3.11 or newer (the production container uses Python 3.12)
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
- `debugging_practice_duck`: debugging practice workflow where a review agent assesses traceback-based rubric scenarios as JSON, optional subprocess agents handle incomplete or incorrect answers, and the workflow sends student-facing replies

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

Production deploys from `master` through `.github/workflows/ci-cd.yml`. GitHub Actions uses AWS OIDC to build a full-SHA-tagged image, provision a private EC2 environment with Terraform, update the host, and deploy the exact ECR digest through SSM. Runtime secrets come from Secrets Manager, configuration comes from a fixed S3 object, and SQLite data resides on a persistent EBS volume.

See [AWS production deployment](docs/deployment.md) for bootstrap, operation, rollback, and database-cutover instructions.

## Documentation

- [Getting Started](docs/getting-started.md)
- [Deployment Guide](docs/deployment.md)
- Archived legacy docs: `docs/old/`

## Developer Utilities

- `./cdx`: helper launcher script for local developer workflows.
- `scripts/generate_metadata.py`: generates dataset metadata artifacts.

## License

MIT. See [LICENSE](LICENSE).
