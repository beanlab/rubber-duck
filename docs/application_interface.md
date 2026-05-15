# Application Interface

Rubber Duck is a configurable Discord bot platform for AI-assisted
learning conversations and operational tasks. Its external behavior is
documented as scenario files under [scenarios](scenarios/README.md).
Scenario area README files define shared context for related
capabilities, while individual scenario files define externally
observable guarantees.

At the black-box level, the application:

- receives Discord messages in configured channels
- routes each message into admin command handling, duck conversation
  handling, or ignored-message behavior
- creates and manages private thread conversations for ducks
- applies each duck's user-facing behavior contract according to configuration
- records messages, usage, and feedback metrics for later export and reporting

## Scenario Index

Startup and configuration:

- [Starts bot runtime](scenarios/startup/starts_bot_runtime.md)
- [Rejects invalid runtime configuration](scenarios/startup/rejects_invalid_runtime_configuration.md)
- [Loads runtime configuration](scenarios/configuration/loads_runtime_configuration.md)
- [Resolves included configuration](scenarios/configuration/resolves_included_configuration.md)

Message routing:

- [Ignores non-routable messages](scenarios/routing/ignores_non_routable_messages.md)
- [Routes admin channel messages to commands](scenarios/routing/routes_admin_channel_messages_to_commands.md)
- [Starts duck conversation from duck channel](scenarios/routing/starts_duck_conversation_from_duck_channel.md)
- [Forwards active thread messages](scenarios/routing/forwards_active_thread_messages.md)

Duck conversations:

- [Ends conversation threads](scenarios/conversations/ends_conversation_threads.md)
- [Standard Duck supports student learning](scenarios/conversations/standard_duck_supports_student_learning.md)
- [Stats Duck provides statistical outputs](scenarios/conversations/stats_duck_provides_statistical_outputs.md)

Specialized conversation behavior:

- [Registration verifies and registers users](scenarios/registration/registration_verifies_and_registers_users.md)
- [Assignment feedback grades report submissions](scenarios/assignment_feedback/assignment_feedback_grades_report_submissions.md)
- [Conversation review scores queued conversations](scenarios/conversation_review/conversation_review_scores_queued_conversations.md)

Admin commands:

- [Reports status](scenarios/admin/reports_status.md)
- [Exports metric tables](scenarios/admin/exports_metric_tables.md)
- [Generates reports](scenarios/admin/generates_reports.md)
- [Exports logs](scenarios/admin/exports_logs.md)
- [Reports active conversations](scenarios/admin/reports_active_conversations.md)
- [Manages cache entries](scenarios/admin/manages_cache_entries.md)

## Related Guides

- [Getting Started](getting-started.md)
- [Deployment](deployment.md)
