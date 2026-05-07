# Ignores Non-Routable Messages

## Purpose

Filter irrelevant inbound messages.

---

# Context

The bot is running with a configured admin channel, one or more
configured duck channels, and any current active conversation threads.

---

# Action

Discord delivers a message that is from the bot itself, from another
bot, starts with `//`, or is posted outside the configured admin
channel, configured duck channels, and active conversation threads.

---

# Outcome

The application does not start a command workflow, does not start a duck
workflow, does not forward the message to an active workflow queue, and
does not send a user-visible response for that message.

---

# Related Scenarios

- [Routes admin channel messages to commands](routes_admin_channel_messages_to_commands.md)
- [Starts duck conversation from duck channel](starts_duck_conversation_from_duck_channel.md)
- [Forwards active thread messages](forwards_active_thread_messages.md)
