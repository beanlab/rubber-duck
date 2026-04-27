# PLAN.md

## Metadata
- Feature: Unified runtime entrypoint for Discord/Teams/Both from `src/main.py`
- Status: complete
- Last Updated: 2026-03-31
- Planner Approval: approved (by: user, date: 2026-03-31)
- Final User Confirmation: confirmed (date: 2026-03-31)

## User Intent
- Goal:
  - Replace split launch scripts (`run_discord.py`, `run_teams.py`) with a primary launch path in `src/main.py` using a CLI argument that selects `discord`, `teams`, or `both`.
  - Defer Teams private-thread parity and instead move toward Teams DM/personal-chat behavior in a later step.
- Non-goals:
  - Implementing the Teams DM/personal-chat reroute behavior in this first implementation cycle.
  - Changing duck behavior, prompts, workflow semantics, or metrics format.
- Constraints:
  - Full `dev-assistance` workflow is active.
  - No production-code changes before plan approval and test-writing phase.
  - Existing behavior in Discord-only and Teams-only modes should remain functionally equivalent.

## Facts vs Assumptions
### Facts
- `src/main.py` currently composes and runs Discord runtime only.
- `run_discord.py` and `run_teams.py` both exist and each have their own CLI/runtime setup.
- Teams adapter currently does not create a separate private thread ID and returns the parent conversation ID in `create_thread`.
- User explicitly wants startup unification first, then Teams DM approach afterward.

### Assumptions
- Preferred launch style remains direct script invocation (`python src/main.py ...`).
- In `--platform both`, adapter-specific configs are provided separately.

## Acceptance Criteria
- [x] `src/main.py` CLI accepts platform selector with values `discord`, `teams`, and `both`.
- [x] `discord` mode behavior matches existing `run_discord.py` behavior for startup, routing, and background tasks.
- [x] `teams` mode behavior matches existing `run_teams.py` behavior for startup, HTTP message endpoint, and background tasks.
- [x] `both` mode accepts separate adapter configs and starts both adapters concurrently.
- [x] `both` mode starts both adapters concurrently and keeps them running until interrupted.
- [x] Startup logging clearly indicates selected platform mode and active services.
- [x] Existing Teams behavior remains unchanged in this phase (no private-thread emulation changes yet).
- [x] Targeted tests cover CLI mode selection and platform-specific bootstrap paths.
- [x] `run_discord.py` and `run_teams.py` are removed in this phase.

## Plan
### Phase 1: Planning
- [x] Clarifying questions complete
- [x] Plan approved by user

### Phase 2: Test Writing
- [x] Tests drafted from approved plan
- [x] Test-only scope preserved (no production code edits)
- [x] Tests define expected behavior for `discord`, `teams`, and `both` launch selection

### Phase 3: Implementation
- [x] Extract common runtime bootstrap/shared composition helpers
- [x] Add unified CLI platform selector in `src/main.py`
- [x] Implement Teams launcher path and Both-mode concurrent startup
- [x] Remove legacy entry scripts `run_discord.py` and `run_teams.py`
- [x] Implement adapter-specific config CLI for both mode (`--discord-config`, `--teams-config`)

### Phase 4: Review
- [x] Findings reported to user
- [x] Required fixes completed

### Phase 5: Docs
- [x] Docs updated
- [x] Docs summary provided to user

## Risks and Constraints
- Risk: `both` mode may have shutdown/cleanup race conditions across Discord and aiohttp/Teams runners.
  - Mitigation: explicit lifecycle handling, cancellation tests, and graceful cleanup paths.
- Risk: CLI/entrypoint migration could break existing deployment scripts.
  - Mitigation: document exact new command forms and validate startup paths during review.
- Risk: Shared composition refactor could introduce regressions in one adapter while fixing the other.
  - Mitigation: mode-specific tests and targeted smoke checks for both single-platform modes.

## Open Questions
- Q: none for planning gate
  - Owner: n/a
  - Status: closed

## Decisions Log
- Date: 2026-03-31
  - Decision: Execute startup unification before Teams DM/private-conversation changes.
  - Why: User-prioritized order and this creates a cleaner foundation for subsequent Teams routing work.
- Date: 2026-03-31
  - Decision: Keep Teams thread behavior unchanged in this phase.
  - Why: Scope control for first implementation cycle and reduced regression risk.
- Date: 2026-03-31
  - Decision: Remove `run_discord.py` and `run_teams.py` immediately; no compatibility wrappers.
  - Why: User requested direct unification without transitional scripts.
- Date: 2026-03-31
  - Decision: `--platform both` uses separate adapter config inputs.
  - Why: User requested separate config handling per adapter in dual-run mode.
- Date: 2026-03-31
  - Decision: Keep launch style as direct script execution with exact command forms:
  - Why: Preserve prior invocation style while moving to single entrypoint.
  - Command forms:
  - `python src/main.py --platform discord --config <discord-config-path> [--debug] [--log-path <path>]`
  - `python src/main.py --platform teams --config <teams-config-path> [--debug] [--log-path <path>] [--port <int>]`
  - `python src/main.py --platform both --discord-config <discord-config-path> --teams-config <teams-config-path> [--debug] [--log-path <path>] [--port <int>]`

## Handoffs
- Planner -> Test Writer: After user approval, write tests for unified CLI mode selection and mode-specific runtime launch behavior.
- Test Writer -> Planner (if blocked): If behavior expectations or CLI contract is ambiguous.
- Test Writer -> Implementer: After tests are committed and failing for missing feature behavior.
- Implementer -> Planner (if blocked): If tests conflict with runtime constraints or user intent.
- Implementer -> Reviewer: After tests pass and runtime behavior is validated.
- Reviewer -> Implementer (if fixes needed): With prioritized findings and required corrections.
- Reviewer -> Docs Writer: After review passes and docs-impact note is ready.

## Change Log
- Date: 2026-03-31
  - What changed: Initialized `docs/plans/PLAN.md` for unified runtime feature planning.
  - Why: Full workflow activation and requested pre-implementation planning approval gate.
- Date: 2026-03-31
  - What changed: Applied user planning decisions, finalized launch command contract, and marked planning phase complete.
  - Why: User approved planning direction and provided concrete decisions for implementation constraints.
- Date: 2026-03-31
  - What changed: Added test-only coverage for unified startup CLI parsing and mode-based runtime dispatch in `tests/test_main_startup_cli.py`; extended test shims in `tests/conftest.py` to allow importing `src.main` in isolation.
  - Why: Complete Phase 2 test-writing gate before implementation edits.
- Date: 2026-03-31
  - What changed: Implemented unified startup in `src/main.py` with `--platform discord|teams|both`, added `--discord-config` and `--teams-config` contract for both mode, migrated Teams runtime entry logic into `src/main.py`, switched imports to script-compatible `src.*`, and removed `run_discord.py` and `run_teams.py`.
  - Why: Complete Phase 3 implementation scope and satisfy approved startup unification requirements.
- Date: 2026-03-31
  - What changed: Review identified two required follow-up fixes before closeout: (1) single-platform CLI validation currently blocks `CONFIG_FILE_S3_PATH` fallback, and (2) `both` mode likely installs duplicate global log queue handlers via `filter_logs` in both adapters.
  - Why: Preserve prior startup behavior expectations and avoid duplicate/misdirected admin error notifications in dual-adapter mode.
- Date: 2026-03-31
  - What changed: Implemented review-required fixes in `src/main.py`: removed parser-time `--config` requirement for single-platform modes so runtime `CONFIG_FILE_S3_PATH` fallback remains intact, and added one-time global log-forwarding guard to prevent duplicate `filter_logs` installation in `--platform both`.
  - Why: Resolve reviewer findings and restore expected startup/config behavior without duplicating global log forwarding handlers.
- Date: 2026-03-31
  - What changed: Re-review verified both required fixes are present and acceptable: single-platform `CONFIG_FILE_S3_PATH` fallback path is reachable again, and `both` mode log forwarding setup is guarded to install once.
  - Why: Confirm completion of review findings before docs phase handoff.
- Date: 2026-03-31
  - What changed: Updated docs for unified startup contract in `README.md`, `docs/getting-started.md`, `src/DOCS.md`, and `CHANGELOG.md` including platform CLI usage (`discord|teams|both`), separate both-mode configs, Teams port behavior, env fallback notes, and legacy script removal.
  - Why: Complete Phase 5 docs scope and align developer-facing documentation with implemented behavior.
- Date: 2026-03-31
  - What changed: Completed orchestrator closeout gate checks (review readiness, finalized metadata, acceptance criteria verification, and final user confirmation).
  - Why: Mark feature complete and archive plan artifact per full workflow process.
