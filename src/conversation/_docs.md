## Relevant File Locations

- `src/conversation/conversation.py`
- `src/conversation/threads.py`
- `src/duck_orchestrator.py`
- `src/main.py`
- `src/rubber_duck_app.py`

## Runtime Entry Flow

- `RubberDuckApp.route_message(...)` starts `duck-orchestrator` for configured duck channels.
- `DuckOrchestrator.__call__(...)` chooses the duck implementation for the channel, creates a thread, builds `DuckContext`, and runs the conversation under workflow alias `thread_id`.
- `main.build_ducks(...)` constructs concrete conversation types from duck config and maps them by channel via `_setup_ducks(...)`.

## Conversation Types

- `AgentLedConversation`:
  - Runs one-shot agent handling via `AIClient.run_agent(context, agent, None)`.
- `UserLedConversation`:
  - Sends an introduction message first.
  - Runs interactive loop via `AIClient.run_conversation(...)` using `TalkTool`-backed receive/send callables.

## Thread Setup and Handoff

- `SetupPrivateThread.__call__(...)`:
  - Creates a new thread from parent channel (title truncated to 20 chars).
  - Mentions the user inside the thread.
  - Sends the join link back to the parent channel.
- `DuckOrchestrator` uses the returned thread id as the conversation workflow alias, enabling message and reaction events to route into that active thread workflow.
