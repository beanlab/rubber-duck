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

# Outcome

The application recursively resolves `$include` directives, supports
optional JSONPath selectors for included content, and applies
deep-merge semantics for dictionary-style includes.

Channel and server routing are resolved from configured Discord IDs, and
each configured channel can map to a named global duck or an inline duck
definition.

---

# Related Scenarios

- [Loads runtime configuration](loads_runtime_configuration.md)
- [Starts bot runtime](../startup/starts_bot_runtime.md)
