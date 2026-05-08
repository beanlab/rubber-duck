# Application Interface

Rubber Duck is a configurable Discord bot platform for AI-assisted
learning workflows. Its external behavior is documented as scenario
files under [scenarios](scenarios/README.md).
Scenario area README files define shared context for related
capabilities, while individual scenario files define externally
observable guarantees.

At the black-box level, the application:

- receives Discord messages in configured channels
- routes each message into either admin command handling or a duck workflow
- creates and manages private thread conversations for duck workflows
- runs AI-backed conversation and workflow logic according to duck configuration
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

- [Runs agent-led conversation](scenarios/conversations/runs_agent_led_conversation.md)
- [Runs user-led conversation](scenarios/conversations/runs_user_led_conversation.md)
- [Closes conversation after completion](scenarios/conversations/closes_conversation_after_completion.md)
- [Reports workflow failure to thread](scenarios/conversations/reports_workflow_failure_to_thread.md)

Workflow-specific behavior:

- [Completes email-verified registration](scenarios/registration/completes_email_verified_registration.md)
- [Rejects invalid registration attempts](scenarios/registration/rejects_invalid_registration_attempts.md)
- [Reports registration permission failures](scenarios/registration/reports_registration_permission_failures.md)
- [Grades markdown report upload](scenarios/assignment_feedback/grades_markdown_report_upload.md)
- [Rejects invalid assignment feedback uploads](scenarios/assignment_feedback/rejects_invalid_assignment_feedback_uploads.md)
- [Reports missing sections as unsatisfactory](scenarios/assignment_feedback/reports_missing_sections_as_unsatisfactory.md)
- [Serves queued conversations for review](scenarios/conversation_review/serves_queued_conversations_for_review.md)
- [Records reaction-based scores](scenarios/conversation_review/records_reaction_based_scores.md)
- [Closes inactive review sessions](scenarios/conversation_review/closes_inactive_review_sessions.md)

Admin commands:

- [Reports status](scenarios/admin/reports_status.md)
- [Exports metric tables](scenarios/admin/exports_metric_tables.md)
- [Generates reports](scenarios/admin/generates_reports.md)
- [Exports logs](scenarios/admin/exports_logs.md)
- [Reports active workflows](scenarios/admin/reports_active_workflows.md)
- [Manages cache entries](scenarios/admin/manages_cache_entries.md)

## Related Guides

- [Getting Started](getting-started.md)
- [Deployment](deployment.md)
