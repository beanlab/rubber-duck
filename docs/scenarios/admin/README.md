# Admin Scenarios

Admin scenarios describe operator-visible command behavior in the
configured admin channel.

The shared admin context is:

- the bot is running
- admin command routing is available
- operators send commands as Discord messages in the configured admin channel
- command results are returned as Discord messages, files, or explicit error messages

Individual command-family scenarios may use an `Interaction` table when
one command area has several related forms.

## Scenarios

- [Reports status](reports_status.md)
- [Exports metric tables](exports_metric_tables.md)
- [Generates reports](generates_reports.md)
- [Exports logs](exports_logs.md)
- [Reports active conversations](reports_active_conversations.md)
- [Manages cache entries](manages_cache_entries.md)
