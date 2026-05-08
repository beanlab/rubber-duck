---
name: Refactoring Scenarios
description: |
  Load this skill when reorganizing scenario documentation, splitting
  broad scenario documents, moving guarantees, or improving the
  scenario tree structure.
---

# Refactoring Scenarios

Refactor scenario documentation when the tree no longer makes behavior
easy to find, maintain, or verify.

The purpose of refactoring is to preserve behavioral guarantees while
improving the documentation tree.

## When To Refactor

Refactor when:

- a document contains multiple independent behavioral guarantees
- a document uses prose where a concise `Interaction` table would better
  describe related variants or workflow phases
- a folder mixes unrelated capability areas
- parent context is duplicated across child scenarios
- it is unclear where a new scenario belongs
- the same guarantee appears in multiple places
- filenames or folders no longer describe observable behavior
- broad application design prose needs to become scenario-style
  documentation

## Rules

Do not lose information.

When moving, splitting, or converting prose to interaction tables,
preserve every behavioral guarantee, context, action, outcome,
non-goal, related scenario, and shared assumption.

Keep hierarchy semantic. Organize by externally meaningful capability
or operational concern, not internal module layout.

Parent documents may define shared terminology, assumptions, and
navigation. Child scenario files should define localized guarantees and
avoid repeating inherited context.

## Workflow

1. Read the existing scenario documents and identify every distinct
   behavioral guarantee.
2. Choose a domain-oriented tree structure that makes those guarantees
   discoverable.
3. Move shared terminology or assumptions into parent `README.md` or
   index documents.
4. Split broad documents only when they contain independent behavioral
   contracts. For cohesive command families, validation branches, or
   workflow phases, keep one scenario and use a concise `Interaction`
   table.
5. Update related-scenario links after moving files.
6. Review the original and refactored documents to confirm no guarantee
   was lost.
7. Review the final tree again for coherence, naming, and navigation.

## Report Back

Summarize:

- new folders or documents created
- files moved or split
- guarantees preserved or clarified
- any open questions that could not be resolved from the existing docs
