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
| The configuration contains `$include` directives. | The application recursively resolves the included content. |
| An include specifies a JSONPath selector. | The application includes only the selected content. |
| Included dictionary content overlaps with local dictionary content. | The application applies deep-merge semantics. |
| Server and channel configuration is resolved. | Routing uses configured Discord IDs, and each configured channel maps to a named global duck or an inline duck definition. |

---

# Outcome

Resolved runtime configuration contains included content, merged
dictionary values, and channel-to-duck routing information needed for
startup.

---

# Related Scenarios

- [Loads runtime configuration](loads_runtime_configuration.md)
- [Starts bot runtime](../startup/starts_bot_runtime.md)
