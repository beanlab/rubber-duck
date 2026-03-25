# Changelog

All notable changes in this repository are documented here.

## spring-cleaning-test (2026-03-25T09:22:33-06:00)

### Added
- Introduced repository cleanup automation via `.myteam/spring-cleaning` skill and nested role/task loaders.
- Added and standardized `DOCS.md` coverage for `src/` submodules and `tests/`.
- Added top-level SQL metrics tests under `tests/` with shared test bootstrap in `tests/conftest.py`.
- Added archival structure and docs under `archive/` for prompts, metrics, and education scratch/tutorial content.
- Added checklist conclusion requirements to `.myteam/feature-check/skill.md`.

### Changed
- Refactored registration config to use shared YAML anchor defaults in `production-config.yaml`.
- Updated config typing and registration workflow wiring to align with current runtime behavior.
- Updated local config examples to avoid duplicate top-level keys and improve include usage clarity.
- Updated lockfile and myteam dependency resolution metadata in `poetry.lock`.
- Updated docs across moved/archived areas to reflect current structure and ownership.

### Fixed
- Prevented `!log` command failures when log path is not configured.
- Added SQL session rollback on metrics write failures.
- Fixed metadata generation script path handling and related cleanup fallout.

### Removed / Archived
- Archived legacy prompts and old education scratch material.
- Archived unused metrics CSV handler and removed dead armory cache module.
