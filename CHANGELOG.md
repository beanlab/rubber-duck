# Changelog

All notable changes in this repository are documented here.

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

### Fixed
- Corrected command documentation drift by including currently supported admin commands such as `!cache`.

### Removed / Archived
- Removed obsolete file-inventory-heavy narrative from subsystem docs in favor of decision-relevant operational notes.
