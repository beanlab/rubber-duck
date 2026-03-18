---
name: Myteam Assistance
description: |
  Instructions for working with the local myteam setup in this repository.
  Use this skill when creating, editing, debugging, or documenting `.myteam` roles and skills for the rubber-duck project.
---

This project keeps a repository-local myteam directory at `.myteam/`.

## Local Myteam Structure

- `.myteam/load.py`
    - Root loader that prints instructions and lists available roles, skills, and tools.
- `.myteam/role.md`
    - Role-level instructions loaded by `myteam get role` when present.
- `.myteam/<skill-name>/skill.md`
    - Skill instructions and trigger metadata.
- `.myteam/<skill-name>/load.py`
    - Skill loader that prints the skill instructions and lists related roles/skills/tools.

## Core Commands

- Initialize local myteam scaffold:
    - `myteam init`
- Create a new role/skill under `.myteam/`:
    - `myteam new role <role-path>`
    - `myteam new skill <skill-path>`
- Load role instructions:
    - `myteam get role`
    - `myteam get role <role>`
- Load skill instructions:
    - `myteam get skill <skill-path>`
    - Example: `myteam get skill dev-assistance/config`

## How It Works In This Repo

- `myteam get role` and `myteam get skill ...` execute local loader scripts and print nearby markdown instructions.
- Skill naming is hierarchical using `/` separators (for example `dev-assistance/config`).
- Each nested skill folder is a standalone unit with its own `skill.md` and `load.py`.
- Skill frontmatter in `skill.md` (`name` + `description`) controls discoverability and triggering context.

## Authoring Guidelines

- Keep `skill.md` concise and operational.
- Every `skill.md` contains instructions meant for codex to quickly gain understanding of the project structure. 
- Avoid placeholder text; every skill should provide actionable instructions and relevant information.