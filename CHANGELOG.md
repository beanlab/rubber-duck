# Changelog

All notable changes in this repository are documented here.

## unified-startup (2026-03-31T00:00:00-06:00)

### Changed
- Unified runtime startup into `src/main.py` with `--platform discord|teams|both`.
- Added `--discord-config` and `--teams-config` for `--platform both`.
- Preserved single-platform `CONFIG_FILE_S3_PATH` fallback when `--config` is omitted.
- Kept Teams runtime `--port` behavior (`PORT` env fallback, default `3000`).

### Removed / Archived
- Removed legacy entry scripts `run_discord.py` and `run_teams.py`.

## stats-updates (2026-04-03T15:44:35-06:00)

### Added
- Added `describe_dataset` tool registration in `src/main.py` so stats ducks can request full dataset metadata by exact filename.
- Added `DatasetTools` in `src/armory/python_tools.py` to expose available dataset file paths and serve full metadata descriptions.
- Added regression coverage in `tests/test_python_tools_formatting.py` for numeric table formatting and scientific-notation suppression.

### Changed
- Updated stats prompts (`prompts/production-prompts/stats.md` and `prompts/production-prompts/cs-stats.md`) to require `describe_dataset` in metadata workflows and tighten output/error handling rules.
- Updated `production-config.yaml` so stats ducks include `describe_dataset`; standard stats also includes `conclude_conversation`.
- Updated `PythonTools` output formatting to normalize scientific notation in stdout/stderr and render numeric tables with trimmed decimal strings and markdown-safe parsing behavior.
- Updated `PythonExecContainer` runtime setup to configure numpy/pandas float display without scientific notation.
- Updated container resource metadata storage to retain exact filename, dataset name, and full description for dataset lookup.

### Fixed
- Aligned dataset-description call signatures and strict filename matching so dataset metadata lookups fail clearly when no exact match exists.
- Ensured White test output guidance in prompts returns only `f_pvalue`.

## writing-docs-skill (2026-03-26T11:59:55-06:00)

### Added
- Added `docs-assistance` myteam guidance for concise `DOCS.md` authoring.
- Added `docs/plans/PLAN_TEMPLATE.md` for shared multi-role feature planning.
- Added dedicated `dev-assistance` roles (`planner`, `test-writer`, `implementer`, `reviewer`, and `docs-writer`) and a `meta` role with role-specific loaders.
- Added `myteam-assistance/create-role` and `myteam-assistance/create-skill` nested skills.

### Changed
- Refactored `dev-assistance` into a full workflow with shared `docs/plans/PLAN.md` expectations and lightweight/full execution paths.
- Updated repository docs process to load `docs-assistance` before documentation edits.
- Reconciled all `DOCS.md` files under `src/`, `tests/`, and `archive/prompts` to current runtime behavior and ownership boundaries.
- Standardized `DOCS.md` structure around concise high-signal sections (`Purpose`, `Operational Flow`, optional boundaries/dependencies, and guardrails).
- Updated `myteam-assistance` structure and loader behavior to use grouped authoring subskills.
- Updated CS110 conversation-review `target_channel_ids` in `production-config.yaml`.
- Moved cache configuration to tool-level settings under `tools.<name>.cache` for `container_exec` tools.
- Renamed top-level cache cleanup config to `cache_cleanup_settings`.
- Updated cache command output to identify caches by tool source (`<backend>#<tool_name>`) while preserving index-based removal commands.
- Made semantic caching optional per `container_exec` tool and disabled caching for `run_cs_analysis` in production config.

### Fixed
- Corrected command documentation drift by including currently supported admin commands such as `!cache`.

### Removed / Archived
- Removed obsolete file-inventory-heavy narrative from subsystem docs in favor of decision-relevant operational notes.
