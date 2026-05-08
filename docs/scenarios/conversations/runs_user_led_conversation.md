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

# Interaction

| Action | Outcome |
| --- | --- |
| The workflow starts in the created thread. | The application sends the configured introduction text. |
| The user sends follow-up messages while the workflow is active. | The application continues the turn-based conversation. |
| The workflow reaches completion or timeout conditions. | The conversation proceeds to the configured closure behavior. |

---

# Outcome

User-led conversations continue through turn-based Discord exchanges
until the workflow completes or times out.

---

# Related Scenarios

- [Starts duck conversation from duck channel](../routing/starts_duck_conversation_from_duck_channel.md)
- [Forwards active thread messages](../routing/forwards_active_thread_messages.md)
- [Closes conversation after completion](closes_conversation_after_completion.md)
