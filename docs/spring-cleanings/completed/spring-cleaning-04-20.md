# Spring Cleaning 04-20

## Project Structure
- Finding: Top-level `backlog/` and `meetings/` appear isolated from docs/code. Evidence: `rg -n "backlog/" -S .` and `rg -n "meetings/" -S .` returned no matches. Confidence: medium. Suggested: move under `docs/` (e.g., `docs/backlog/`, `docs/meetings/`) and update references to those files (especially in `.myteam`).
- Finding: Root `datasets/` seems tooling-only rather than runtime-facing. Evidence: `rg -n "datasets/" -S src` returned no matches; references appear in `scripts/generate_metadata.py` and `scripts/DOCS.md`. Confidence: medium. Suggested: keep `datasets/` at the repo root but add a README clarifying these are for local testing only.

## Prompt Evaluation
- Finding: `socratic-duck` prompt references an "Explainer Duck" handoff, but no explainer workflow/duck is configured. Evidence: `prompts/production-prompts/socratic-duck.txt` lines referencing "Explainer Duck"; `rg -n "Explainer|explainer" production-config.yaml docs src` returned no matches. Confidence: high. Suggested: remove the handoff instructions referencing the Explainer Duck.
- Finding: `agent_led_conversation` is documented as one-shot, but `standard-rubber-duck` instructs multi-turn persistence, which may conflict with the workflow contract. Evidence: `docs/application_interface.md` says "`agent_led_conversation` runs a one-shot agent response flow"; `prompts/production-prompts/standard-rubber-duck.md` requires continuing conversation and not concluding unless explicitly told. Confidence: medium. Suggested: confirm actual runtime behavior for `agent_led_conversation`, then update `docs/application_interface.md` to match.

## Src Evaluation
- Finding: Duplicate queue-wait logic exists in `TalkTool.receive_message_from_user` and `utils.message_utils.wait_for_message`, increasing drift risk for timeouts/queue semantics. Evidence: `src/armory/talk_tool.py` defines `receive_message_from_user` with `quest.queue('messages', None)` + `ctx.timeout`; `src/utils/message_utils.py` defines `wait_for_message` with similar queue/timeout; used in `src/workflows/registration.py` and `src/workflows/assignment_feedback_workflow.py`. Confidence: high. Suggested: refactor `receive_message_from_user` to call `wait_for_message(ctx.timeout)` and preserve exact behavior (raise `ConversationComplete` on timeout, return `message['content']` on success).
- Finding: Dead/unused `_tools` registry in `armory.tools` appears unreferenced. Evidence: `src/armory/tools.py` defines `_tools: dict[str, Callable] = {}`; `rg -n "_tools" -S src/armory` shows no reads/writes besides the definition. Confidence: high. Suggested: remove the unused registry or wire it into `Armory` if it is meant to cache tool metadata.
- Finding: Debug-only S3 listing code is embedded in runtime module `resource_staging.py`, including a hard-coded S3 prefix. Evidence: `src/utils/resource_staging.py` defines `debug_list_s3_prefix` and calls it in a `__main__` block with `s3://stats121-datasets/datasets/`; no other references found. Confidence: medium. Suggested: remove the debug section from `src/utils/resource_staging.py`.
- Finding: Duplicate `SendMessage` protocol definitions can drift and confuse tooling around message signatures. Evidence: `src/utils/protocols.py` defines `class SendMessage(Protocol)`; `src/gen_ai/gen_ai.py` defines a second `class SendMessage(Protocol)` with similar but not identical annotations. Confidence: medium. Suggested: replace the `gen_ai` definition with an import from `utils.protocols` so there is a single source of truth.

## Summary
- Moved `backlog/` and `meetings/` under `docs/` and updated `.myteam` references to the new paths. Commit suggestion: `Move backlog and meetings under docs`.
- Added `datasets/README.md` clarifying the folder is for local testing only. Commit suggestion: `Document datasets as local testing only`.
- Clarified `agent_led_conversation` behavior in `docs/application_interface.md` to reflect single-session execution with tool calls. Commit suggestion: `Clarify agent_led_conversation behavior in interface docs`.
- Refactored `TalkTool.receive_message_from_user` to use `utils.message_utils.wait_for_message` while preserving timeout behavior. Commit suggestion: `Deduplicate TalkTool message wait logic`.
- Removed the unused `_tools` registry from `src/armory/tools.py`. Commit suggestion: `Remove unused armory tools registry`.
- Removed debug-only S3 listing code from `src/utils/resource_staging.py`. Commit suggestion: `Drop debug S3 listing helper`.
- Unified `SendMessage` protocol definition by importing it from `utils.protocols` in `src/gen_ai/gen_ai.py`. Commit suggestion: `Use shared SendMessage protocol in gen_ai`.
