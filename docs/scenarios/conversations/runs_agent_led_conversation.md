# Runs Agent-Led Conversation

## Purpose

Run one-shot agent replies.

---

# Context

A configured duck has `duck_type` set to `agent_led_conversation`, and a
routable user message has started a new duck conversation thread.

---

# Action

The user asks a question or makes a request in the created thread.

---

# Outcome

The application starts the configured agent in the thread. The agent may
send messages, receive user replies, and use configured tools until it
finishes or ends the conversation.

---

# Related Scenarios

- [Starts duck conversation from duck channel](../routing/starts_duck_conversation_from_duck_channel.md)
- [Closes conversation after completion](closes_conversation_after_completion.md)
