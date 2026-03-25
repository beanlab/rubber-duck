#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from myteam.utils import print_instructions, get_active_myteam_root, list_roles, list_skills, list_tools


def _print_tree(root: Path, *, max_depth: int = 3, max_entries_per_dir: int = 30) -> None:
    if not root.exists():
        return

    print()
    print(f"{root.name}/")

    def walk(directory: Path, prefix: str, depth: int) -> None:
        if depth >= max_depth:
            return

        entries = sorted(
            (
                entry for entry in directory.iterdir()
                if entry.name not in {'__pycache__'} and not entry.name.startswith('.')
            ),
            key=lambda entry: (entry.is_file(), entry.name.lower()),
        )
        truncated = len(entries) > max_entries_per_dir
        entries = entries[:max_entries_per_dir]

        for idx, entry in enumerate(entries):
            is_last = idx == len(entries) - 1 and not truncated
            branch = "└── " if is_last else "├── "
            print(f"{prefix}{branch}{entry.name}{'/' if entry.is_dir() else ''}")
            if entry.is_dir():
                next_prefix = prefix + ("    " if is_last else "│   ")
                walk(entry, next_prefix, depth + 1)

        if truncated:
            print(f"{prefix}└── ...")

    walk(root, "", 0)


def main() -> int:
    base = Path(__file__).resolve().parent  # .myteam/<role>
    print_instructions(base)
    myteam = get_active_myteam_root(base)

    src_root = myteam.parent / 'src'
    prompts_root = myteam.parent / 'prompts'

    print('Project structure')
    _print_tree(src_root)
    _print_tree(prompts_root)

    list_roles(base, myteam, [])
    list_skills(base, myteam, [])
    list_tools(base, myteam, [])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
