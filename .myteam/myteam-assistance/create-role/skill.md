---
name: "create-role"
description: "Author myteam roles. Use when the task is to define or improve role.md behavior, ownership boundaries, delegation criteria, or role discoverability."
---

Create or update a `myteam` role definition.

Workflow:
1. Run `myteam new role <role_path>` if the role does not already exist.
2. Edit generated files and replace all placeholders that will remain in the
   repo.
3. In `role.md`, set:
   - `name`: stable role name
   - `description`: when this role should be used and what it owns
4. Write concise body instructions covering responsibilities, handoffs,
   validation expectations, and non-goals.
5. Verify with `myteam get role <role_path>`.

Writing guidance:
- Focus on ownership and delegation boundaries, not generic topic knowledge.
- State what the role owns end-to-end.
- State what the role must hand off.
- Prefer concrete execution language over vague advice.
- Keep descriptions in `role.md` frontmatter accurate because current `myteam`
  surfaces them directly.
- Keep the role aligned with repository structure rules in `.myteam/role.md`.
