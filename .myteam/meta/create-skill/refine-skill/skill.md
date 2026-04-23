---
name: "refine-skill"
description: "Load this skill when you are asked to make edits to an existing skill."
---

Skill Refinement Workflow:
1. Ask the user what was unsatisfactory about the skill.
2. Consider the user's response and any proposed edits:
  - Are issues extensive enough that a rewrite/rearchitecture is needed?
  - If you had the opportunity to use the skill before the user requested an edit, consider the following:
    - What about the skill was efficient? What was inefficient?
    - If the change is being requested based off some failure state, what about the skill could have contributed to the failure? How can the skill be edited to eliminate this class of issue?
  - Can the issue be solved easily by editing the prompt in skill.md in a way that reflects good design practice?
3. If edits are extensive enough that research is needed, conduct appropriate web searches for relevant topics. Consider the following:
  - Are implemented tools/features/dependencies being used correctly? Do they work in a way contrary to the implementation in the skill?
  - What alternative tools/approaches/dependencies exist to accomplish the same task? What trade-offs exist if a switch is made?
4. Confirm that there is not already a `<skill-name>-edits.md` in the working directory.
   - If one exists, verify the edits outlined inside are consistent with steps 2 and 3 then skip to step 6.
   - If it is incomplete, clear the file and resume normal workflow from step 5.
5. Create a proposed set of changes for the user and write it to a file with name convention `<skill-name>-edits.md`.
6. Inform the user that `<skill-name>-edits.md` is complete. Wait for the user's approvale before continuing.
7. Strictly following `<skill-name>-edits.md`, implement the skill.
