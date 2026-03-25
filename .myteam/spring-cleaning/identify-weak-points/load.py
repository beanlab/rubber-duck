#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from myteam.utils import print_instructions, get_active_myteam_root, explain_skills, explain_roles, explain_tools, list_skills, \
    list_roles, list_tools, print_directory_tree


def print_project_tree(root: Path, *, max_depth: int = 5) -> None:
    if not root.exists():
        print(f"Project path not found: {root}")
        return

    print_directory_tree(
        root=root,
        max_levels=max_depth,
        exclude=(
            ".git",
            ".github",
            ".myteam",
            "datasets",
            "education",
            ".idea",
            ".mypy_cache",
            ".next",
            ".pytest_cache",
            ".ruff_cache",
            ".venv",
            ".vscode",
            "__pycache__",
            "build",
            "coverage",
            "dist",
            "node_modules",
            "venv",
            ".DS_Store",
        ),
    )


def main() -> int:
    base = Path(__file__).resolve().parent  # .myteam/<role>
    myteam = get_active_myteam_root(base)

    print_instructions(base)
    print_project_tree(myteam.parent)

    explain_roles()
    list_roles(base, myteam, [])

    explain_skills()
    list_skills(base, myteam, [])

    explain_tools()
    list_tools(base, myteam, [])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
