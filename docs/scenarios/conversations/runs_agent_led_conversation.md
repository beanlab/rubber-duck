# Runs Agent-Led Conversation

## Purpose

Run one-shot agent replies.

---

# Context

A configured duck has `duck_type` set to `agent_led_conversation`, and a
routable user message has started a new duck conversation thread.

---

# Action

The agent-led conversation workflow runs in the created thread.

---

# Outcome

The application runs the configured AI-backed one-shot agent response
flow in the thread and sends the response output to Discord as part of
that thread conversation.

---

# Related Scenarios

- [Starts duck conversation from duck channel](../routing/starts_duck_conversation_from_duck_channel.md)
- [Closes conversation after completion](closes_conversation_after_completion.md)
