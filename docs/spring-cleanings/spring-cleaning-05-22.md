# Project Structure

- Active prompt assets now live under `src/prompts/`, and the runtime config was updated to point at that tree. The repo is aligned on the new layout.
- `archive/prompts/` remains separate historical content and should stay out of runtime path changes.
- The only remaining structure note is that `src/prompts/debugging-practice-duck/` still includes `prefabs.yaml` alongside prompt text, which is acceptable if that YAML is part of the workflow bundle.

# Prompt Evaluation

- `src/prompts/` has no exact duplicate prompt files by content hash, and the filenames are mostly consistent kebab-case. The only naming outlier is `TA-incomplete.md` with the uppercase acronym.
- Prompt references in `production-config.yaml` now point to `src/prompts/...`, so the move is reflected in the active configuration.
- The prompt tree is still small and clear enough that no extra nesting or renaming is required for the move itself.

# Src Evaluation

- `src/workflows/debugging_practice_duck_workflow.py` now anchors its prompt directory under `src/prompts/`, which removes the old repo-root dependency for that workflow.
- `src/gen_ai/build.py` and `src/main.py` still read configured prompt paths directly, so they remain dependent on the process CWD and on config hygiene. That is acceptable for this move, but it is the main residual brittleness left in path handling.
- No functional code path still points at the old top-level `prompts/` tree.
