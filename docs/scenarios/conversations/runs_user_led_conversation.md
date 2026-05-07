# Runs User-Led Conversation

## Purpose

Run turn-based tutoring.

---

# Context

A configured duck has `duck_type` set to `user_led_conversation`, and a
routable user message has started a new duck conversation thread.

---

# Action

The user-led conversation workflow runs in the created thread.

---

# Outcome

The application sends the configured introduction text and continues a
turn-based conversation with the user until the workflow reaches its
completion or timeout conditions.

---

# Related Scenarios

- [Starts duck conversation from duck channel](../routing/starts_duck_conversation_from_duck_channel.md)
- [Forwards active thread messages](../routing/forwards_active_thread_messages.md)
- [Closes conversation after completion](closes_conversation_after_completion.md)
