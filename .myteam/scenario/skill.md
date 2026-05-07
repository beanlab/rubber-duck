---
name: "Scenario Authoring Skill"
description: "Load this skill when you are editing or creating new scenarios"
---
Scenarios are the authoritative definition of system behavior.

They replace:
- broad application specification documents,
- large architecture documents,
- and behavior-oriented test plans.

Scenarios are:
- human-readable,
- hierarchically organized,
- implementation-independent,
- directly testable,
- and behavior-focused.

Tests validate scenarios.
Implementations satisfy scenarios.

---

# Core Principles

## 1. Scenarios Define Observable Guarantees

A scenario describes:
- required preconditions,
- a triggering action,
- and guaranteed outcomes.

A scenario does NOT describe:
- code structure,
- implementation details,
- speculative future behavior,
- or broad conceptual overviews.

Focus on:
```text
What behavior must the system guarantee?
```

---

## 2. Scenarios Must Be Atomic

Each scenario should define exactly one behavioral guarantee.

Good:
```text
pawn promotes on final rank
```

Bad:
```text
pawn movement system
```

If multiple guarantees exist, split them into separate scenario files.

---

## 3. Scenarios Must Be Testable

Every guarantee in a scenario must be externally verifiable.

If a guarantee cannot be validated by a test or observable inspection, it does not belong in the scenario.

---

## 4. Scenarios Must Be Implementation-Independent

Avoid describing:
- classes,
- internal functions,
- storage mechanisms,
- framework details,
- or algorithm choices,

unless those are themselves contractual guarantees.

Good:
```text
The system retries until valid schema output is produced
```

Bad:
```text
The RetryManager invokes validate_output() in a loop
```

---

## 5. Filesystem Hierarchy Is Semantic

Scenario organization communicates:
- capability boundaries,
- inheritance context,
- behavioral grouping,
- and discoverability.

Directory structure matters.

Prefer domain-oriented hierarchy.

Good:
```text
scenarios/
  board/
  pieces/
  rules/
```

Bad:
```text
scenarios/
  utils/
  services/
  helpers/
```

---

# Scenario Structure

Each scenario file must contain the following sections.

```md
# <Scenario Title>

## Purpose

<10 words or less explanation of the capability>

---

# Preconditions

<Minimal required system state>

---

# Action

<Triggering interaction>

---

# Guarantees

<Observable required outcomes>

---

# Non-Goals (Optional)

<Explicit exclusions>

---

# Related Scenarios

<Optional references>
```

---

# Section Definitions

## Purpose

A concise statement of:
- what capability is being defined,
- and why it exists.

Keep this short.

---

## Preconditions

Defines the minimum required state for the scenario.

May include:
- available interfaces,
- filesystem state,
- loaded context,
- runtime assumptions,
- existing entities,
- permissions,
- or inherited guarantees.

Only include information necessary for the scenario.

Good:
```md
# Preconditions

A callable exists:

execute_step(prompt, output, input=None)
```

Bad:
```md
# Preconditions

The application uses Python 3.12,
Pydantic,
and asyncio.
```

unless those are contractually required.

---

## Action

Defines the triggering event.

Usually:
- function invocation,
- CLI execution,
- user interaction,
- message receipt,
- lifecycle transition,
- or system event.

Actions should be:
- concrete,
- reproducible,
- and unambiguous.

Good:
```md
# Action

Call:

execute_step(
  "write two poems",
  {
    "poem1": "first poem",
    "poem2": "second poem"
  }
)
```

---

## Guarantees

Defines required observable behavior.

This is the contract.

Guarantees may include:
- outputs,
- side effects,
- validation rules,
- state transitions,
- lifecycle semantics,
- orchestration behavior,
- persistence guarantees,
- visibility constraints,
- or completion behavior.

Every item must be:
- observable,
- deterministic where possible,
- and testable.

Good:
```md
# Guarantees

- Opens an isolated agent session
- Injects an objective containing:
  - prompt
  - output schema
- Continues execution until schema-valid output is produced
- Closes the session after completion
```

Bad:
```md
# Guarantees

- Uses clean architecture principles
- Efficiently processes requests
```

These are vague and non-testable.

---

## Non-Goals

Explicitly define:
- what the scenario does not specify,
- or what belongs elsewhere.

This prevents overlap and ambiguity.

Good:
```md
# Non-Goals

This scenario does not define:
- UI rendering
- network transport
- retry backoff timing
```

---

## Related Scenarios

Optional references to adjacent guarantees.

Use repository-relative paths.

Example:
```md
# Related Scenarios

- rules/check/detects_check.md
- game/completion/detects_checkmate.md
```

---

# Naming Rules

Scenario filenames must:
- be lowercase,
- use underscores,
- and describe behavioral guarantees.

Good:
```text
detects_checkmate.md
rejects_invalid_schema.md
closes_session_after_completion.md
```

Bad:
```text
checkmate.md
schema.md
session_stuff.md
```

Prefer:
```text
verb + behavioral outcome
```

---

# Granularity Rules

A scenario should answer exactly one question:

```text
What behavior is guaranteed in this situation?
```

If the answer contains:
- "and",
- multiple independent outcomes,
- or multiple behavioral domains,

the scenario is probably too broad.

Split it.

---

# Inheritance Rules

Parent directories may define:
- shared assumptions,
- shared terminology,
- or domain context.

Child scenarios inherit that context implicitly.

Do not repeat inherited information unnecessarily.

Example:
```text
scenarios/
  execution/
    README.md
    execute_step/
      schema_validation.md
      session_lifecycle.md
```

`execution/README.md` may define:
- agent terminology,
- execution lifecycle vocabulary,
- and shared assumptions.

Children define only localized guarantees.

---

# Relationship To Tests

Scenarios are authoritative.

Tests are verification artifacts.

Behavior must never exist solely in tests.

Ideal mapping:
```text
1 scenario ↔ 1 test target
```

Example:
```text
scenarios/
  pieces/pawn/promotes_on_last_rank.md

tests/
  pieces/pawn/test_promotes_on_last_rank.py
```

---

# Scenario Quality Checklist

Before finalizing a scenario, verify:

- Is the behavior atomic?
- Is the behavior observable?
- Is every guarantee testable?
- Is implementation detail minimized?
- Is the scope narrow?
- Does the filename describe the guarantee?
- Does the scenario avoid ambiguity?
- Could a test be written directly from this file?
- Could another engineer implement the behavior from this file alone?

If not, refine the scenario.