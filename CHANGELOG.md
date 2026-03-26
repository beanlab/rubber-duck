# Changelog

All notable changes in this repository are documented here.

## writing-docs-skill (2026-03-26T09:52:13-06:00)

### Added
- Added `docs-assistance` myteam guidance for concise `DOCS.md` authoring.
- Added nested `docs-assistance/read` and `docs-assistance/write` skills for doc reconciliation workflow.

### Changed
- Updated repository docs process to load docs-specific skills before documentation edits.
- Reconciled all `DOCS.md` files under `src/`, `tests/`, and `archive/prompts` to current runtime behavior and ownership boundaries.
- Standardized `DOCS.md` structure around concise high-signal sections (`Purpose`, `Operational Flow`, optional boundaries/dependencies, and guardrails).

### Fixed
- Corrected command documentation drift by including currently supported admin commands such as `!cache`.

### Removed / Archived
- Removed obsolete file-inventory-heavy narrative from subsystem docs in favor of decision-relevant operational notes.
