## Purpose

`src/gen_ai` builds configured agents and executes model/tool loops via the OpenAI Responses API.

## Operational Flow

- `build_agent(...)` builds `Agent` objects from inline prompts or `prompt_files`.
- `AIClient._get_completion(...)` calls `AsyncOpenAI.responses.create(...)` with instructions, history, tool schemas, tool settings, and optional reasoning/output format.
- `AIClient._run_agent(...)` handles response items:
  - `function_call`: execute tool through armory, append `function_call_output`, continue loop.
  - `message`: return assistant text.
  - `reasoning`: ignored for user output.
- `run_conversation(...)` loops user input -> model/tool execution until the conversation concludes.

## Dependencies

- Depends on `Armory` for tool schemas/tool execution.
- Depends on record hooks for metrics (`record_message`, `record_usage`).

## Failure Modes and Guardrails

- OpenAI/API failures are wrapped in `GenAIException` with agent context.
- Tool-call argument parsing assumes valid JSON from model output; malformed arguments fail the turn.
