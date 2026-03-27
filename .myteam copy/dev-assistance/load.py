#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from myteam.utils import (
    get_active_myteam_root,
    list_roles,
    list_skills,
    list_tools,
    print_directory_tree,
    print_instructions,
)


def main() -> int:
    base = Path(__file__).resolve().parent  # .myteam/<role>
    print_instructions(base)
    myteam = get_active_myteam_root(base)

    src_root = myteam.parent / 'src'
    prompts_root = myteam.parent / 'prompts'

    print('Project structure')
    print_directory_tree(src_root, max_levels=3)
    print_directory_tree(prompts_root, max_levels=3)

    list_roles(base, myteam, [])
    list_skills(base, myteam, [])
    list_tools(base, myteam, [])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
