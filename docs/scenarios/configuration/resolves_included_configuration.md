# Resolves Included Configuration

# Overview

The `$include` directive allows runtime configuration files to reuse
values from another configuration file, optionally selecting a nested
value by path, and then apply local overrides.

This lets local configuration inherit production defaults without
duplicating the full production structure.

# Context

Operators may maintain local, staging, or production configuration files
that share most settings but differ in a small number of environment-
specific values.

Without includes, those files must duplicate shared configuration,
which increases the risk of drift when production configuration changes.

# Trigger

The application loads a JSON or YAML runtime configuration file before
startup validation.

# Specification

When a configuration node contains `$include`, the application resolves
the referenced file and path before the final runtime configuration is
validated.

The include reference uses this form:

```text
<config-file>@<path>
```

The referenced value becomes the base value for the current node.

Only the referenced path is imported. Other values from the referenced
file are not imported unless they are inside the selected path.

If the included value is an object, local sibling fields are merged onto
that object.

Object merge behavior:

- fields from the included object are retained
- local fields with the same path override included fields
- local fields that do not exist in the included object are added
- included fields that are not overridden remain unchanged
- nested objects are merged recursively

If the included value is a scalar or array, the included value replaces
the current node completely.

Scalar and array includes must not define sibling fields alongside
`$include`.

Includes are resolved recursively. Included files may themselves contain
`$include` directives.

# Examples

## Object Include With Override

Production configuration:

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

Local configuration:

```yaml
ducks:
  standard-rubber-duck:
    $include: "production-config.yaml@$.ducks.standard-rubber-duck"
    settings:
      agent:
        engine: gpt-5-nano
```

Resolved configuration:

```yaml
ducks:
  standard-rubber-duck:
    settings:
      agent:
        name: RubberDuck
        prompt_files:
          - prompts/production-prompts/standard-rubber-duck.md
        engine: gpt-5-nano
        reasoning: low
```

## Scalar Include

Production configuration:

```yaml
sender_email: duck@example.edu
```

Local configuration:

```yaml
sender_email:
  $include: "production-config.yaml@$.sender_email"
```

Resolved configuration:

```yaml
sender_email: duck@example.edu
```

## Invalid Scalar Include With Sibling Field

```yaml
sender_email:
  $include: "production-config.yaml@$.sender_email"
  some_override_key: hello
```

This is invalid because scalar includes replace the current node and
cannot be merged with sibling fields.

# Failure Modes

If the referenced file cannot be loaded, configuration loading fails.

If the referenced path does not exist, configuration loading fails.

If an include cycle is detected, configuration loading fails.

If a scalar or array include defines sibling fields, configuration
loading fails.

If multiple non-object includes are used at the same node, configuration
loading fails.

# Constraints

Only object includes support field-level overrides.

Scalar and array includes replace the full current node.

Include resolution happens before runtime configuration validation.

The final resolved configuration must behave as if the included values
had been written directly in place, with local overrides applied.

# Non-Goals

This scenario does not define the complete runtime configuration schema.

This scenario does not define validation rules for individual runtime
configuration fields after include resolution.

This scenario does not require included files to come from the same
environment as the including file.

# Related Scenarios

- [Loads runtime configuration](loads_runtime_configuration.md)
- [Starts bot runtime](../startup/starts_bot_runtime.md)
