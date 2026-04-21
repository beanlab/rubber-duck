## Intent

The application design should document how the application interacts
with the real world.

This documentation focuses on two interfaces:

- the **user** interface
- the **operations** interface

These interfaces define the application's external contract.

### User Interface

The **user** interface describes what the product does and how users
experience it.

This includes things such as:

- user-visible behavior
- supported workflows
- important states and transitions
- validation rules and constraints that users encounter
- user-facing errors and failure modes
- external side effects visible to users
- major UX concepts and expectations

Tests should validate that the implemented application conforms to the
documented user-facing behavior.

### Operations Interface

The **operations** interface describes how developers, operators, and
deployment systems interact with the application.

This includes things such as:

- configuration surfaces
- runtime dependencies
- environment requirements
- deployment assumptions
- operational procedures
- external integrations and service dependencies
- data import/export behavior at system boundaries
- changes that require corresponding operational changes outside the
  codebase

This information may not be visible to end users, but it is still part
of the application's real-world contract.

### What Belongs Here

Include information that affects how a person or system must use,
operate, configure, integrate with, or reason about the application.

Examples include:

- a user workflow
- a permission rule
- a required environment variable
- a deployment dependency
- an API contract
- a failure mode users or operators must handle
- a how the application reads or writes external data

### What Does Not Belong Here

Do not include implementation details that do not change the external
contract.

Examples include:

- internal module layout
- class structure
- helper functions
- private refactors
- algorithm swaps with no interface impact
- code cleanup
- test-only scaffolding
- naming changes internal to the codebase

### Decision Rule

If changing something would require a user, operator, deployer,
integrator, or downstream system to change behavior or expectations,
it belongs in the application design.

If not, it is probably an implementation detail and should stay out of
these documents.
