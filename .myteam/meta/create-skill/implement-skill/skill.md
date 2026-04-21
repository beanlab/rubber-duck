---
name: "implement-skill"
description: "Load this skill when you are ready to implement a skill outlined in a <skill-name>-design.md file."
---

Design specifications for the skill will always be in a file with a name convention of `<skill-name>-design.md`. Review it before proceeding with implementation workflow.

Workflow:
1. Run `myteam new skill <skill_path>` if the skill does not already exist.
2. Edit generated files and replace all placeholders that will remain in the
   repo:
   - In `skill.md`, set:
      - `name`: stable skill name that is unique to the directory
      - `description`: when the skill should be used and what it covers. Include explicit trigger conditions in this field.
3. Confirm that there is not already a `<skill-name>-plan.md` in the working directory.
   - If one exists, verify it is complete, skipping to step 5 if it is.
   - If it is incomplete, clear the file and resume normal workflow from step 4.
4. Using `<skill-name>-design.md` create a stepwise plan to implement the architecture outlined in the file. Write this plan to a file with a name convention of `<skill-name>-plan.md`.
5. Inform the user the implementation plan is ready for review. Wait for the user's approval before continuing.
6. Strictly following `<skill-name>-plan.md`, implement the skill. Refer to `<skill-name>-design.md` for specifics regarding portions of the plan.
7. Verify with `myteam get skill <skill_path>`.

Implementation Guidance:
- Keep instructions concise and action-oriented. Include imperative instructions, constraints, and verification steps.
- Use grouped paths when they improve discoverability.
- Keep descriptions in `skill.md` frontmatter accurate because current `myteam` surfaces them directly.
- Keep persistent project artifacts outside `.myteam/` unless they are part of the team structure itself.
