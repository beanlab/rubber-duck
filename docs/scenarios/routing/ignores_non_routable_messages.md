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

# Interaction

| Action | Outcome |
| --- | --- |
| Message from the bot itself | Ignored. |
| Message from another bot | Ignored. |
| Message starting with `//` | Ignored. |
| Message outside configured channels and active conversation threads | Ignored. |

---

# Outcome

The application does not handle the message as an admin command, does
not start a duck conversation, does not continue an active conversation,
and does not send a user-visible response for that message.

---

# Related Scenarios

- [Routes admin channel messages to commands](routes_admin_channel_messages_to_commands.md)
- [Starts duck conversation from duck channel](starts_duck_conversation_from_duck_channel.md)
- [Forwards active thread messages](forwards_active_thread_messages.md)
