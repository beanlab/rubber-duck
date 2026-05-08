# Resolves Included Configuration

## Purpose

Compose config files.

---

# Context

The selected JSON or YAML runtime configuration contains one or more
`$include` directives.

---

# Action

The application resolves the runtime configuration during startup.

---

# Interaction

| Action | Outcome |
| --- | --- |
| `$include` directives | Recursively resolves the included content. |
| Include with JSONPath selector | Includes only the selected content. |
| Overlapping dictionary content | Applies deep-merge semantics. |
| Server and channel configuration | Uses configured Discord IDs, with each configured channel mapped to a named global duck or an inline duck definition. |

---

# Outcome

Resolved runtime configuration contains included content, merged
dictionary values, and channel-to-duck routing information needed for
startup.

---

# Related Scenarios

- [Loads runtime configuration](loads_runtime_configuration.md)
- [Starts bot runtime](../startup/starts_bot_runtime.md)
