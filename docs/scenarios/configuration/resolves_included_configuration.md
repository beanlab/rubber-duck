# Resolves Included Configuration

# Context

The `$include` directive allows YAML configuration files to inherit
values from another configuration file and path. It is used to reduce
duplication and prevent configuration drift between production and
local development environments.

Local configurations can extend production defaults while overriding
only specific fields.

---

# Purpose

Developers maintain separate local configuration files that diverge
from production over time. This typically results in:

- duplicated configuration structures
- missing updates when production config changes
- increased maintenance overhead
- inconsistent behavior between environments

The $include directive addresses this by enabling local configs to
inherit directly from production definitions.

---

# Examples

## Include with Override

Production Configuration:

```yaml
ducks:
  standard-rubber-duck:
    settings:
      agent:
        name: RubberDuck
        prompt_files:
          - prompts/production-prompts/standard-rubber-duck.md
        engine: gpt-5.4-mini
        reasoning: low
```

Local Configuration:

```yaml
ducks:
  standard-rubber-duck:
    $include: "production-config.yaml@$.ducks.standard-rubber-duck"
    settings:
      agent:
        engine: gpt-5-nano # value to override
```

Resolved Configuration:

```yaml
ducks:
  standard-rubber-duck:
    settings:
      agent:
        name: RubberDuck
        prompt_files:
          - prompts/production-prompts/standard-rubber-duck.md
        engine: gpt-5.4-nano # overridden value
        reasoning: low
```

## Include Scalar

Including scalar values (such as strings) is supported, but the $include
key must be the only key in the mapping. No sibling keys are allowed.

Working example:

```yaml
sender_email:
  $include: "production-config.yaml@$.sender_email"
```

Error-raising example:

```yaml
sender_email:
  $include: "production-config.yaml@$.sender_email"
  some_override_key: hello
```
---

# Rules and Constraints

- The include target must resolve to an object/map
- Circular includes are not supported
- Missing or invalid JSONPath expressions result in an informative error
- Local configuration values always take precedence over included values
- Scalars and Arrays are fully replaced

---

# Related Scenarios

- [Loads runtime configuration](loads_runtime_configuration.md)
- [Starts bot runtime](../startup/starts_bot_runtime.md)
