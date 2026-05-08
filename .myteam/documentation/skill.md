---
name: Documentation
description: |
  Load this skill when creating, editing, migrating, or organizing
  scenario-style documentation for an application's external behavior or
  operational contract.
---

# Documentation

Scenario documentation is the authoritative documentation model for
externally meaningful system behavior.

Use it to document how the application behaves at its real-world
interfaces:

- user-visible behavior and workflows
- operational contracts and configuration surfaces
- externally observable validation, failures, side effects, and state
  transitions
- integration boundaries and runtime assumptions that users, operators,
  deployers, or downstream systems must honor

Do not use scenario documentation for internal code structure, private
helper behavior, speculative future behavior, or implementation details
that do not affect the external contract.

## What A Scenario Is

A scenario is a human-readable, implementation-independent behavioral
guarantee.

It describes:

- the relevant context
- the triggering action
- the observable outcomes the system must guarantee

Tests validate scenarios. Implementations satisfy scenarios. Behavior
must not exist only in tests.

## Documentation Tree

Scenario documentation is organized as a file tree. The tree is
semantic: directory placement communicates capability boundaries,
behavioral grouping, shared context, and discoverability.

Prefer domain-oriented hierarchy:

```text
scenarios/
  registration/
  conversation/
  assignment-feedback/
  operations/
```

Avoid implementation-oriented hierarchy:

```text
scenarios/
  utils/
  services/
  helpers/
```

Parent directories may include a `README.md` or index document that
defines shared terminology, assumptions, domain context, and links to
child scenarios. Child scenario files inherit that context implicitly
and should not repeat it unnecessarily.

Scenario files should describe localized guarantees. If a document
contains multiple independent guarantees, split it into separate
scenario files. If a document contains tightly related variants or
workflow phases of one user/operator capability, keep them together and
use an `Interaction` table.

Individual scenarios use `Context`, `Action`, and `Outcome` as their
core sections. When a single scenario requires a short sequence of
externally visible exchanges or related variants, it may use an optional
`Interaction` section with an `Action` / `Outcome` table. Table rows
should be concise and inherit actors, channels, and system context from
the surrounding sections.

## Relationship To Application Design

Scenario documentation replaces broad application design docs when the
content describes externally meaningful behavior or operational
contracts.

When migrating application design material, convert narrative interface
descriptions into:

- parent context documents for shared concepts and navigation
- atomic child scenarios for specific behavioral guarantees

Keep broad product prose, implementation architecture, and internal code
notes out of scenario files unless they define external contract.

## Subskills

Load `documentation/authoring-scenarios` when writing or editing one
scenario file.

Load `documentation/refactoring-scenarios` when reorganizing the
scenario documentation tree, splitting broad documents, moving
guarantees, or improving navigation.
