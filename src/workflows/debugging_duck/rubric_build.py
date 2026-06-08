from pathlib import Path
from typing import Any

import yaml


def error_type(traceback: str) -> str:
    for line in reversed(traceback.splitlines()):
        stripped_line = line.strip()
        if not stripped_line:
            continue
        if ":" in stripped_line:
            candidate = stripped_line.split(":", 1)[0].strip()
        else:
            candidate = stripped_line.split(maxsplit=1)[0].strip()
        if candidate.endswith("Error") or candidate in {"Exception", "SyntaxError"}:
            return candidate
    return "error"


def load_rubric_files(settings: dict[str, Any]) -> dict[str, Any]:
    rubric_files = settings["rubric_path"]
    if isinstance(rubric_files, str):
        rubric_files = [rubric_files]

    loaded_rubric: dict[str, Any] = {}
    for rubric_file in rubric_files:
        file_contents = Path(rubric_file).read_text()
        if not file_contents.strip():
            continue

        parsed = yaml.safe_load(file_contents)
        if parsed:
            loaded_rubric |= parsed

    return loaded_rubric


def build_rubric_state(rubric_data: dict[str, Any]) -> dict[str, Any]:
    exercises = []

    project_fields = {"full project", "code", "correct code"}
    exercise_names = [
        name
        for name in rubric_data
        if name not in project_fields
    ]

    for name in exercise_names:
        rubric_item = rubric_data[name]
        traceback = "\n".join(rubric_item["traceback"]).strip()
        code = rubric_item.get("code")

        if isinstance(code, list):
            code = "\n".join(str(item).strip()
                             for item in code if str(item).strip())
        elif code is None:
            code = ""
        else:
            code = str(code).strip()

        exercise = {
            "name": str(name),
            "rubric_text": yaml.safe_dump(
                {name: rubric_item},
                sort_keys=False,
            ).strip(),
            "traceback": traceback,
            "error_type": error_type(traceback),
            "code": code,
        }

        exercises.append(exercise)

    return {
        "exercises": exercises,
        "text": yaml.safe_dump(rubric_data, sort_keys=False).strip(),
    }
