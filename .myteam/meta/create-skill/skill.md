---
name: "create-skill"
description: "Load this skill if the user requests you create or modify a skill for them."
---

Skill creation workflow is simple, and twofold:

1. Load the design-skill skill and proceed through its workflow.
2. Only after this step is complete its completion, load the implement-skill and proceed through its workflow.

In the case you are invoking this skill for any individual component of the skill design, creation, or refinement process, load only the relevant subskill.
