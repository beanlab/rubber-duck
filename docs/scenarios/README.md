# Scenarios

Rubber Duck scenario documentation defines externally observable
behavior at the Discord, command, conversation, and configuration
interfaces.

The runtime contract is Discord-first and config-driven:

- the app runs as a single process started from `python -m src.main`
- behavior is driven by a resolved local file or S3 configuration
- each configured channel can map to a named global duck or an inline duck definition
- incoming messages are routed by channel identity and conversation state
- admin command outputs are delivered in Discord as messages or files
- new duck conversations are scoped to private Discord threads
- duck behavior scenarios describe the black-box response contract that
  each named duck presents to users

## Scenario Areas

Each scenario area includes a README that defines shared context for
the scenarios in that folder.

- [Startup](startup/)
- [Routing](routing/)
- [Conversations](conversations/)
- [Registration](registration/)
- [Assignment feedback](assignment_feedback/)
- [Conversation review](conversation_review/)
- [Admin](admin/)
- [Configuration](configuration/)

Successful runtime interactions either send Discord messages, reactions,
or files; create Discord threads; or produce command outputs and
artifacts such as zip, CSV, image, or text files.

The runtime records message, usage, and feedback telemetry for later
export and reporting.
