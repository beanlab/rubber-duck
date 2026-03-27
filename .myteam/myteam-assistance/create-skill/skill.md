---
name: "create-skill"
description: "Author myteam skills. Use when the task is to define or improve skill.md triggers, workflow instructions, scope, or skill placement in the myteam hierarchy."
---

Create or update a `myteam` skill definition.

Workflow:
1. Run `myteam new skill <skill_path>` if the skill does not already exist.
2. Edit generated files and replace all placeholders that will remain in the
   repo.
3. In `skill.md`, set:
   - `name`: stable skill name
   - `description`: when the skill should be used and what it covers
4. Write imperative instructions, constraints, and verification steps.
5. Keep the skill focused on workflow guidance rather than role ownership.
6. Verify with `myteam get skill <skill_path>`.

Writing guidance:
- Put trigger conditions in the `description`.
- Keep instructions concise and action-oriented.
- Use grouped paths when they improve discoverability.
- Keep descriptions in `skill.md` frontmatter accurate because current
  `myteam` surfaces them directly.
- Keep persistent project artifacts outside `.myteam/` unless they are part of
  the team structure itself.
