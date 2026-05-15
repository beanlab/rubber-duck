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

Use this test when scope is unclear:

```text
Would this scenario still be true after replacing the implementation?
```

### Keep Scenarios Atomic

Each scenario defines exactly one behavioral guarantee.

Good:

```text
rejects unsupported file upload
```

Bad:

```text
file processing workflow
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

### Focus On External Contracts

Write scenarios from the perspective of users, operators, integrations,
or downstream systems.

Prefer describing:

- visible inputs
- visible outputs
- accepted and rejected actions
- observable state transitions
- externally meaningful side effects
- required response patterns

Avoid describing:

- internal classes, functions, queues, services, workers, prompts, tools,
  model choices, framework behavior, storage layout, or configuration
  keys unless they are part of the external contract

### Document Capabilities By Behavior

When documenting a named capability, mode, assistant, policy, or
user-facing feature, describe the behavioral promise rather than the
implementation path.

Capability scenarios may include representative user inputs and
acceptable response patterns when exact output is variable.

Focus on:

- what the capability should do
- what it should refuse or avoid
- how it handles ambiguity
- what kinds of outputs are acceptable
- what completion or failure looks like from the outside

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

# Interaction (Optional)

| Action | Outcome |
| --- | --- |
| <Context-relative action or state> | <Observable response> |

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
about 10 words or less. **Omit this section** if the title and context make
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

### Interaction

Use an `Interaction` section when one atomic scenario is best described
as an ordered series of externally visible exchanges or tightly related
variants of one capability.

Use representative examples when exact output is variable. Examples
should define the expected response pattern, not prescribe hidden
implementation steps or full internal instructions.

Interaction tables must use exactly these columns:

```md
| Action | Outcome |
| --- | --- |
```

Each row should describe one user, operator, integration, or system
action and the observable outcome that follows.

Rows should be concise and context-relative. Do not repeat actors,
channels, command surfaces, or system names already established by
`Context` and `Action`.

Prefer:

```md
| Action | Outcome |
| --- | --- |
| Supported file uploaded | Accepts the file and reports that processing started. |
| Unknown command | Returns a help-style message listing supported actions. |
| Ambiguous request | Asks a clarifying question before continuing. |
```

Avoid:

```md
| Action | Outcome |
| --- | --- |
| The operator sends the cleanup command through the command router. | The application removes expired entries and reports the cleanup result. |
```

Do not split a scenario only because it has multiple related command
forms, validation branches, or workflow phases. If the variants belong
to one user/operator capability, keep them in one scenario and use an
`Interaction` table.

Split only when rows describe different behavioral contracts that would
naturally be discovered, tested, or maintained separately.

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

Prefer names based on the promised behavior, not the mechanism that
provides it.

Examples:

```text
rejects_invalid_schema.md
closes_session_after_completion.md
preserves_feedback_submission.md
asks_clarifying_question_for_ambiguous_request.md
exports_report_as_csv.md
```

Avoid:

```text
runs_worker_job.md
calls_validation_service.md
processes_queue_message.md
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
- Would this scenario still be true after replacing the implementation?
- Does the title describe user-visible behavior instead of an internal process?
- Are internal mechanisms mentioned only when they are externally contractual?
- Could a black-box test verify this behavior?
- Is the scope narrow?
- Does the filename describe the guarantee?
- Does the scenario avoid ambiguity?
- Does any `Interaction` table avoid repeating context from surrounding sections?
- Are interaction action labels short enough to scan while still reproducible?
- Do interaction outcomes describe observable behavior without repeating the application actor on every row?
- Could a test be written directly from this file?
- Could another engineer implement the behavior from this file alone?
