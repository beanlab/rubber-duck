# Rubber Duck

Rubber Duck is a configurable Discord bot platform for AI-assisted learning workflows.
The current runtime provides Standard tutoring and Stats analysis ducks. The repository
also contains registration and other learning workflows.

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
- `src/workflows/`: Standard, Stats, registration, and other learning workflows
- `src/gen_ai/`: OpenAI client orchestration + agent execution
- `src/armory/`: tool registration, Python tool execution, and caching
- `src/storage/` + `src/metrics/`: SQL persistence and reporting
- `src/prompts/`: prompt assets used by configured ducks/agents
- `archive/prompts/`: legacy and unreferenced prompt assets kept for historical reference
- `rubrics/`: grading rubrics for assignment feedback workflows
- `rubrics/examples/`: non-runtime rubric examples and demos
- `datasets/`: local datasets staged into container tools
- `docs/`: getting started, application flow, and deployment docs
- `tests/`: pytest cases and shared application drivers
- `evaluation/`: experiment orchestration, graders, measurements, and reports
- `scripts/`: developer utility scripts (including metadata generation)
- `archive/`: non-runtime historical and scratch artifacts kept for reference

### Prerequisites

- Python 3.11 or newer (the production container uses Python 3.12)
- Poetry
- Docker (required if you enable container tools such as code execution)
- Discord bot token
- OpenAI API key

## Duck Configuration

Configured ducks use `builder: module:function`, with duck-specific `settings`.
The production configuration selects Standard and Stats builders, plus
registration and conversation review through inline channel definitions. Other workflow
implementations in the repository are not automatically selectable by a
`duck_type` string.

See [application flow](docs/application-flow.md) for startup, routing, conversation
lifecycle, and the current builder-based runtime.

## Admin Commands

Commands are processed in the configured admin channel.

- `!help`: list commands
- `!status`: health check
- `!metrics`: export messages/usage/feedback tables as zip files
- `!stats-cache`: export Stats cache hit/miss events as CSV
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
- [Application Flow](docs/application-flow.md)
- [Tests](tests/DOCS.md)
- [Stats Test Guide](tests/ducks/stats_duck/README.md)
- [Evaluation Tooling and Experiments](evaluation/README.md)
- [Evaluation Documentation](evaluation/docs/README.md)
- Archived legacy docs: `docs/old/`

## Developer Utilities

- `./cdx`: helper launcher script for local developer workflows.
- `scripts/generate_metadata.py`: generates dataset metadata artifacts.

## License

MIT. See [LICENSE](LICENSE).
