#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from myteam.utils import print_instructions, get_myteam_root, explain_skills, explain_roles, explain_tools, list_skills, \
    list_roles, list_tools


def main() -> int:
    base = Path(__file__).resolve().parent  # .myteam/<role>
    myteam = get_myteam_root(base)

    print_instructions(base)

    explain_roles()
    list_roles(base, myteam, [])

    explain_skills()
    list_skills(base, myteam, [])

    explain_tools()
    list_tools(base, myteam, [])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
