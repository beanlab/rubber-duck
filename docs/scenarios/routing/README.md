# Routing Scenarios

Routing scenarios describe how Discord messages become admin commands,
duck conversations, active conversation input, or ignored messages.

The shared routing context is:

- the bot is running with configured Discord channel IDs
- admin messages are routed by the configured admin channel
- duck messages are routed by configured duck channels
- active conversation messages are routed by conversation thread state
- ignored messages do not start commands, duck conversations, or active
  conversation input

## Scenarios

- [Ignores non-routable messages](ignores_non_routable_messages.md)
- [Routes admin channel messages to commands](routes_admin_channel_messages_to_commands.md)
- [Starts duck conversation from duck channel](starts_duck_conversation_from_duck_channel.md)
- [Forwards active thread messages](forwards_active_thread_messages.md)
