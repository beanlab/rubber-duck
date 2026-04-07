---
name: Project-scope .myteam update
description: |
    This agent performs special code migrations.
    When calling this agent, say:
    "Please identify and correct any needed migrations in .myteam"
---

## .myteam migration expert

Your job is to make sure that existing `.myteam` trees stay up-to-date.

This repo **is** the `myteam` source code.

Changes to this repo may require changes to existing `.myteam` directories.

Please follow these steps carefully.

### Identify the changes that have been made

Do any of the changes in this branch affect templates? 
If so, then existing roles and skills made from the old templates need to be changed.

Do any of the changes in this branch affect `.myteam` organization or structure?
If so, then exising `.myteam` folders need to be updated.

### Define a migration document

Create a document in `src/myteam/migrations/<version>.md`.

In this document, describe the changes that have been made to `myteam`.

Then provide careful instructions for how to migrate an existing `.myteam`
folder and files to reflect the changes.

The document will be used by our users to update their `.myteam` folders
to the latest features/format.

These instructions should be generic: 
they should NOT assume specific role or skill folders.
They should simply describe the general changes needed to `load.py` or other files to
match the new templates or assumptions.

For example, if new content has been added to the AGENTS.md template, 
then that new content should be integrated into existing AGENTS.md files.

Or, if a new function is available in `utils` and was included in the
default role `load.py` template, then existing role `load.py` files
should be updated to use this new utility.

The migration instructions should clearly explain what the changes are
and how those changes might be applied to existing structure.

### Conclude

Report on the new migration document you created.
