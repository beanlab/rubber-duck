---
name: "myteam-management"
description: "Manage myteam architecture and authoring decisions. Use when asked to create, update, remove, or reorganize roles/skills, decide top-level vs nested placement, or standardize team-management workflows in this repo."
---

Use this skill as the entry point for `myteam` structure work.

Shared structure rules:
- Use the `myteam` CLI to scaffold new roles and skills before editing them.
- Keep `.myteam/` focused on roles, skills, and tool entrypoints.
- Store persistent planning artifacts in `docs/plans/`, not in `.myteam/`.
- Prefer `role.md` and `skill.md` frontmatter as the source of truth for names
  and descriptions.
- Top-level roles and skills are discoverable from `myteam get role`.
- Nested roles and skills are discoverable after loading the parent.

Grouping guidance:
1. Use a parent skill for each broad domain when that domain may hold multiple
   related roles or skills.
2. Use top-level role paths only when the role is cross-domain and broadly
   discoverable.
3. Place workflow-specific skills under the owning domain or parent skill.
4. Avoid flat duplicates when a grouped path is clearer.

Routing:
- For role-specific authoring, use `myteam-management/create-role`.
- For skill-specific authoring, use `myteam-management/create-skill`.

Validation checklist:
1. Confirm the target path is not already used or intentionally being replaced.
2. Scaffold with `myteam new role <path>` or `myteam new skill <path>`.
3. Replace all placeholder content in generated files that the repo still
   chooses to keep.
4. Remove legacy `info.md` files if they are not needed.
5. Verify with `myteam get role <path>` or `myteam get skill <path>`.
