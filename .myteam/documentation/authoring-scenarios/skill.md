---
name: Authoring Scenarios
description: |
  Load this skill when writing or editing individual scenario files that
  define atomic, testable behavioral guarantees.
---

# Authoring Scenarios

Scenario files define one externally observable behavioral guarantee.

Each scenario must be:

- human-readable
- implementation-independent
- atomic
- externally verifiable
- directly testable

## Core Rules

### Define Observable Guarantees

A scenario describes:

- relevant context
- a triggering action
- guaranteed outcomes

A scenario does not describe code structure, private helper behavior,
framework details, speculative future behavior, or broad conceptual
overviews.

Focus on:

```text
What behavior must the system guarantee in this situation?
```

### Keep Scenarios Atomic

Each scenario defines exactly one behavioral guarantee.

Good:

```text
rejects registration without configured course
```

Bad:

```text
registration workflow
```

If the scenario contains multiple independent outcomes or multiple
behavioral domains, split it.

### Keep Scenarios Testable

Every guarantee must be externally verifiable by a test or observable
inspection. If a guarantee cannot be verified, it does not belong in the
scenario.

### Avoid Implementation Details

Avoid classes, internal functions, storage mechanisms, framework
details, and algorithm choices unless they are themselves contractual
guarantees.

Good:

```text
The system retries until schema-valid output is produced.
```

Bad:

```text
The RetryManager invokes validate_output() in a loop.
```

## Scenario Template

```md
# <Scenario Title>

## Purpose (Optional)

<10 words or less explaining the capability>

---

# Context

<Relevant system state, actors, inputs, permissions, and assumptions>

---

# Action

<Triggering interaction>

---

# Outcome

<Observable required outcomes>

---

# Non-Goals (Optional)

<Explicit exclusions>

---

# Related Scenarios

<Optional repository-relative references>
```

## Section Guidance

### Purpose

State the capability being defined and why it exists. Keep it short,
about 10 words or less. Omit this section if the title and context make
the purpose obvious.

### Context

Define only the context needed to understand and reproduce the
scenario. Context may include available interfaces, filesystem state,
loaded context, runtime assumptions, existing entities, actors,
permissions, inherited guarantees, or relevant constraints.

### Action

Define the concrete triggering event: function invocation, CLI
execution, user interaction, message receipt, lifecycle transition, or
system event. Actions must be reproducible and unambiguous.

### Outcome

Define the required observable behavior. Outcomes may include outputs,
side effects, validation rules, state transitions, lifecycle semantics,
or persistence behavior.

Every outcome must be observable, deterministic where possible, and
testable.

### Non-Goals

Use non-goals to state what the scenario does not specify or what
belongs elsewhere. This prevents overlap and ambiguity.

### Related Scenarios

Reference adjacent guarantees with repository-relative paths.

## Naming

Scenario filenames must be lowercase, use underscores, and describe
behavioral guarantees.

Prefer:

```text
verb + behavioral outcome
```

Examples:

```text
rejects_invalid_schema.md
closes_session_after_completion.md
preserves_feedback_submission.md
```

## Relationship To Tests

Scenarios are authoritative. Tests are verification artifacts.

Ideal mapping:

```text
1 scenario -> 1 test target
```

## Quality Checklist

Before finalizing a scenario, verify:

- Is the behavior atomic?
- Is the behavior observable?
- Is every outcome testable?
- Is implementation detail minimized?
- Is the scope narrow?
- Does the filename describe the guarantee?
- Does the scenario avoid ambiguity?
- Could a test be written directly from this file?
- Could another engineer implement the behavior from this file alone?
