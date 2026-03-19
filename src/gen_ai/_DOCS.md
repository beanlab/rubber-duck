## Relevant File Locations

- `src/gen_ai/gen_ai.py`
- `src/gen_ai/build.py`
- `src/main.py`
- `src/conversation/conversation.py`
- `src/armory/armory.py`

## Runtime Entry Flow

- `main._main(...)` creates `AIClient(armory, bot.typing, record_message, record_usage)`.
- `main.build_ducks(...)` builds configured agents with `build_agent(...)` and injects `AIClient` into conversation workflows.
- Conversation workflows call:
  - `AIClient.run_agent(...)` for one-shot agent runs.
  - `AIClient.run_conversation(...)` for iterative user/agent exchanges.

## Agent Construction

- `build_agent(config)` supports:
  - inline `prompt` string, or
  - `prompt_files` list concatenated in order.
- Agent settings include:
  - `engine` -> `Agent.model`
  - `tools` -> tool names resolved through armory
  - `tool_required` -> `"auto" | "required" | "none"` or specific function choice
  - optional `output_format` and `reasoning`

## Completion and Tool Loop

- `AIClient._get_completion(...)` calls `AsyncOpenAI.responses.create(...)` with:
  - `instructions` from agent prompt
  - `input` as prior context + local history
  - tool schemas from armory and tool choice settings
- `AIClient._run_agent(...)` processes response outputs:
  - `function_call` -> parse args, run tool, append `function_call_output` to history
  - `message` -> return text response
  - `reasoning` -> currently ignored for output
- Usage and message records are emitted through `record_usage` and `record_message` hooks.