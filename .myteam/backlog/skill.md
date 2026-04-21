---
name: Backlog
description: |
  Backlog management instructions and process.
  Load this skill if you need to **create** or **modify** items in the **backlog**.
---

# Backlog

The backlog for this project is stored in markdown files in `<project-root>/backlog/`.

If this folder does not yet exist, please make it.

## Backlog Document Format

Each backlog document should follow this template:

```md 
# [Title]

Created on: [Date]
Created by: [User]

## Details

This section has an overview of the feature.

- What problem does the feature address?
- What is the intent of the feature?
- What details exist so far about this feature?
    - This might include implementation details or guidance
    
Add sub-sections as needed, depending on the level of detail.

## Out-of-scope

What changes/features are left for other backlog items?
If these items are already capture in a backlog document, 
reference them here.

## Dependencies

What other backlog items does this item depend on?
Reference the respective backlog documents here.
```

Some older backlog documents may follow a different format. 
If you encounter one, please update it as best you can to match this format.
Ask the user for missing information.

## Guidance

- Creating a backlog document is about capturing the ideas that are immediately on-hand,
  not about fleshing out an idea or preparing for implementation
- Backlog documents serve as a placeholder or TODO item
  - Implementation details come in a separate process and separate document
- Draw relevant information from the conversation (if any) when drafting the document
  - Think through what information should and should not be included