## Structure

The application design should be organized so that the right information
is easy to find and easy to maintain.

For simple projects, the entire application design may reside in a
single document named `application-design.md`.

As the project grows, the design should be broken into multiple
documents organized by interface area or theme.

## Default Structure

Start with:

- `application-design.md`

This top-level document should serve as the overview for the design
tree.

When multiple documents are needed, `application-design.md` should act
as a table of contents and summary of the major interfaces. It should
link to child documents.

As subfolders are introduced, each folder should follow the same
pattern:

- an index document that explains the scope of that section
- child documents that cover narrower topics in more detail

## Required Content for Each Document

Each application-design document should contain, as appropriate:

- purpose
- scope
- user interface impact
- operations interface impact
- constraints and assumptions
- open questions
- links to related documents

Not every document needs the same headings, but every document should
make these concerns easy to identify.

A useful default template is:

```md
# [Document Title]

## Purpose

What this document covers and why it exists.

## Scope

What is included here.
What is intentionally covered elsewhere.

## User Interface

Describe user-visible behavior, workflows, constraints, and failure
modes relevant to this topic.

## Operations Interface

Describe configuration, runtime, deployment, integration, or support
considerations relevant to this topic.

## Constraints and Assumptions

Document important limits, invariants, dependencies, or assumptions.

## Open Questions

List unresolved design questions, if any.
If backlog documents exist that are relevant to this topic, link them here.

## Related Documents

Link to parent, child, or sibling documents.
```

## When To Split Documents

Split a document when:

- it grows beyond roughly 300 lines
- it covers multiple unrelated interface areas
- readers would struggle to know where to add a new change
- readers would struggle to know where to find relevant information on a topic
- one section has grown large enough to stand on its own
- the same topic is repeated across multiple documents

Do not split a document merely to create more files.
Split when doing so improves clarity and ownership.

## How To Organize Multiple Documents

When multiple documents are used:

- organize by interface theme, not by implementation module
- keep closely related concepts together
- prefer shallow hierarchies unless deeper nesting clearly improves
  navigation
- ensure parent documents summarize and link to children
- ensure child documents link back to their parent or related overview

A reader should be able to start at `application-design.md` and find
the relevant detailed document without guessing.

## Naming Guidance

Choose document and folder names based on externally meaningful
concepts.

Good names describe product or operational concerns, such as:

- `authentication.md`
- `notifications.md`
- `deployment.md`
- `data-imports/`

Avoid names based purely on internal code structure unless that
structure is itself part of the external operating model.

## Maintenance Rule

Keep the document tree aligned with the current application behavior and
operational model.

When a change affects an existing interface, update the owning document.
When a new interface area emerges, create a document for it in the most
appropriate place in the hierarchy.
