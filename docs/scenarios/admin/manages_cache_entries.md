# Manages Cache Entries

## Purpose

Inspect and mutate caches.

---

# Context

The bot is running with cache tooling available through admin command
routing.

---

# Action

An operator sends a `!cache` command in the configured admin channel.

---

# Outcome

`!cache` lists current cache entries and sends a CSV report. `!cache
cleanup` removes expired entries. `!cache remove <cache_tool>
<entry_index>` removes one entry. `!cache clear confirm` clears all
cache entries. Invalid forms return usage or help-style error messages.

---

# Related Scenarios

- [Routes admin channel messages to commands](../routing/routes_admin_channel_messages_to_commands.md)
