## Purpose

`src/conversation` contains the thread-setup flow and conversation modes used by the duck orchestrator.

## Operational Flow

- `SetupPrivateThread` creates a thread, mentions the user in-thread, and posts the join link back in the parent channel.
- `AgentLedConversation` runs a one-shot agent turn through `AIClient.run_agent(...)`.
- `UserLedConversation` sends an introduction, then loops through `AIClient.run_conversation(...)` using `TalkTool` send/receive methods.

## Boundaries

- This module does not choose which duck runs; selection happens in `DuckOrchestrator`.
- This module does not persist workflow state directly; quest/workflow storage owns persistence.

## Failure Modes and Guardrails

- User-led conversations rely on queue-backed message intake and configured timeouts; timeout behavior terminates the conversation loop via `ConversationComplete`.
