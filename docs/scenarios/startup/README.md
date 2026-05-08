# Startup Scenarios

Startup scenarios describe externally visible application lifecycle
behavior when an operator starts the bot runtime.

The shared startup context is:

- an operator starts the application from the repository entry point
- runtime configuration must be loadable and valid before the bot becomes available
- startup success and failure are observable through logs and admin-channel messages

## Scenarios

- [Starts bot runtime](starts_bot_runtime.md)
- [Rejects invalid runtime configuration](rejects_invalid_runtime_configuration.md)
