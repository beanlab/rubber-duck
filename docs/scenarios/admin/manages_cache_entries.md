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

# Interaction

| Action | Outcome |
| --- | --- |
| `!cache` | Lists current cache entries and sends a CSV report. |
| `!cache cleanup` | Removes expired cache entries and reports the cleanup result. |
| `!cache remove <cache_tool> <entry_index>` | Removes the selected cache entry and reports the removal result. |
| `!cache clear confirm` | Clears all cache entries and reports the clear result. |
| Invalid `!cache` form | Returns usage or help-style error messaging. |

---

# Outcome

Cache management commands provide observable Discord responses for
listing, cleaning, removing, clearing, and invalid command forms.

---

# Related Scenarios

- [Routes admin channel messages to commands](../routing/routes_admin_channel_messages_to_commands.md)
