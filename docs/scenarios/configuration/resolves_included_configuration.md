# Resolves Included Configuration

---

# Overview

The `$include` directive allows a YAML configuration file to reuse values from another configuration file and path. It is used to extend existing configuration while allowing selective overrides.

---

# Context

In many systems, production configuration evolves frequently while local development configuration is manually copied and modified.

Over time, this leads to:
- duplicated configuration structures
- missing updates from production changes
- divergence between environments
- unnecessary maintenance overhead

This feature exists to reduce configuration drift by allowing local configurations to reference production definitions directly instead of duplicating them.

---

# Behavior

When `$include` is used in a configuration:

- The referenced configuration value is used as the base
- The local configuration overrides specific fields on top of it
- Only the referenced path is imported
- The result behaves as if the base configuration was written directly in place, with overrides applied

### Object behavior

When the included value is an object:
- fields from the included object are retained
- any overlapping fields in the local configuration override the included values
- non-overlapping fields are preserved

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

Result:

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

When the included value is a scalar (such as a string), the entire value is replaced by the included value.
No additional fields may be defined alongside `$include` in this case.

Valid example:

```yaml
sender_email:
  $include: "production-config.yaml@$.sender_email"
```

Invalid example:

```yaml
sender_email:
  $include: "production-config.yaml@$.sender_email"
  some_override_key: hello
```
---

# Edge Cases

- Including a non-existent path results in an error
- Including a value that is not compatible with the expected type results in an error
- Circular includes are not allowed
- Scalar includes do not allow additional sibling keys


# Constraints

- Only object values support field-level overrides
- Scalar and Array values fully replace the included value
- Invalid paths must produce a clear error

---

# Related Scenarios

- Loads runtime configuration
- Starts bot runtime
