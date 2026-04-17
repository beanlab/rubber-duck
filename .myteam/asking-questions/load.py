#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from myteam.utils import get_active_myteam_root, list_roles, list_skills, list_tools, print_instructions


def main() -> int:
    base = Path(__file__).resolve().parent  # .myteam/<role>
    print_instructions(base)
    myteam = get_active_myteam_root(base)
    list_skills(base, myteam, [])
    list_tools(base, myteam, [])
    list_roles(base, myteam, [])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
