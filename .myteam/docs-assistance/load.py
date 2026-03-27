#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from myteam.utils import print_instructions, get_active_myteam_root, list_roles, list_skills, list_tools


def print_docs_locations(project_root: Path) -> None:
    docs_paths = sorted(project_root.rglob("DOCS.md"))
    print("## `DOCS.md` files in project:\n")
    if not docs_paths:
        print("(none found)")
        return
    for docs_path in docs_paths:
        print(f"- {docs_path.relative_to(project_root)}")


def main() -> int:
    base = Path(__file__).resolve().parent  # .myteam/<role>
    project_root = base.parent.parent
    print_instructions(base)
    print_docs_locations(project_root)
    myteam = get_active_myteam_root(base)
    list_roles(base, myteam, [])
    list_skills(base, myteam, [])
    list_tools(base, myteam, [])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
