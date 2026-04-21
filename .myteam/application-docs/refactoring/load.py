#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from myteam.utils import print_instructions, get_active_myteam_root, explain_skills, explain_roles, explain_tools, list_skills, \
    list_roles, list_tools, print_directory_tree


def main() -> int:
    base = Path(__file__).resolve().parent  # .myteam/<role>
    myteam = get_active_myteam_root(base)

    print_instructions(base)
    docs = [
        "intent.md",
        "structure.md",
    ]
    for doc in docs:
        print((base / doc).read_text())

    application_docs = myteam.parent / 'application-design'
    if application_docs.exists():
        print_directory_tree(application_docs)

    # explain_skills()
    # list_skills(base, myteam, [])
    #
    # explain_tools()
    # list_tools(base, myteam, [])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
