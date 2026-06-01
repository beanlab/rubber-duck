import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError
import yaml


PRIORITY_ORDER = ["concept", "location", "intent", "fix"]
PRIORITY_STATUSES = ["complete", "incorrect", "incomplete", "unattempted"]
PriorityStatus = Literal["complete", "incorrect", "incomplete", "unattempted"]


class PriorityAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reasoning: str
    status: PriorityStatus


class UnrelatedAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reasoning: str
    unrelated: bool


class IncompleteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reasoning: str
    incomplete_response_part: str
    response: str


class UnrelatedCompletion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reasoning: str
    response: str


class IncorrectResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reasoning: str
    concept_understood: bool
    response: str


DEBUGGING_RESPONSE_MODELS: dict[str, type[BaseModel]] = {
    "priority_assessment": PriorityAssessment,
    "unrelated_assessment": UnrelatedAssessment,
    "incomplete_response": IncompleteResponse,
    "unrelated_completion": UnrelatedCompletion,
    "incorrect_response": IncorrectResponse,
}


def _empty_schema_response(schema_name: str) -> dict[str, Any]:
    if schema_name == "priority_assessment":
        return {"reasoning": "", "status": "incomplete"}
    if schema_name == "unrelated_assessment":
        return {"reasoning": "", "unrelated": False}
    if schema_name == "incorrect_response":
        return {"reasoning": "", "concept_understood": False, "response": ""}
    if schema_name == "incomplete_response":
        return {"reasoning": "", "incomplete_response_part": "", "response": ""}
    return {"reasoning": "", "response": ""}


def schema_prompt_text(schema_name: str) -> str:
    return json.dumps(
        DEBUGGING_RESPONSE_MODELS[schema_name].model_json_schema(),
        indent=2,
    ).strip()


def first_error(rubric: dict[str, Any]) -> str:
    for exercise in rubric["exercises"]:
        error = exercise.get("error", "")
        if error:
            return error
    return ""


def _rubric_full_project(rubric_data: dict[str, Any]) -> str:
    full_project = rubric_data.get("full project", "")
    if isinstance(full_project, str):
        return full_project
    if full_project:
        return yaml.safe_dump(full_project)
    return ""


def _field_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(
            field_text
            for item in value
            if (field_text := _field_text(item))
        ).strip()
    if isinstance(value, dict):
        return yaml.safe_dump(value, sort_keys=False).strip()
    if value is None:
        return ""
    return str(value).strip()


def _rubric_field_text(value: Any, field_name: str) -> str:
    if not isinstance(value, dict) or field_name not in value:
        return ""
    return _field_text(value[field_name])


def _traceback_from_string(value: str) -> str:
    lines = value.splitlines()
    for index, line in enumerate(lines):
        if line.strip() != "Traceback (most recent call last):":
            continue

        traceback_lines = []
        for traceback_line in lines[index:]:
            if traceback_lines and not traceback_line.strip():
                break
            traceback_lines.append(traceback_line.rstrip())
        return "\n".join(traceback_lines).strip()

    return ""


def _traceback_text(value: Any) -> str:
    if isinstance(value, str):
        return _traceback_from_string(value) or value.strip()
    if isinstance(value, list):
        for nested_value in value:
            error = _traceback_text(nested_value)
            if error:
                return error
        return ""
    if isinstance(value, dict):
        for nested_value in value.values():
            error = _traceback_text(nested_value)
            if error:
                return error
    return ""


def _first_traceback(value: Any) -> str:
    if isinstance(value, str):
        return _traceback_from_string(value)
    if isinstance(value, dict):
        if "traceback" in value:
            return _traceback_text(value["traceback"])
        for nested_value in value.values():
            error = _first_traceback(nested_value)
            if error:
                return error
        return ""
    if isinstance(value, list):
        for nested_value in value:
            error = _first_traceback(nested_value)
            if error:
                return error
    return ""


def _build_mapping_exercise(value: dict[str, Any], path: list[str]) -> dict[str, Any]:
    return {
        "name": " > ".join(path) if path else "rubric item",
        "rubric_item": yaml.safe_dump(value, sort_keys=False).strip(),
        "error": _first_traceback(value),
        "code": _rubric_field_text(value, "code"),
        "error_line": _rubric_field_text(value, "error line"),
        "intended_behavior": _rubric_field_text(value, "intended behavior"),
        "required_fix": _rubric_field_text(value, "required fix"),
        "required_concept": _rubric_field_text(value, "required concept"),
    }


def _build_string_exercise(value: str, path: list[str], index: int) -> dict[str, Any]:
    return {
        "name": " > ".join(path) if path else f"rubric item {index}",
        "rubric_item": value,
        "error": _first_traceback(value),
        "code": "",
        "error_line": "",
        "intended_behavior": "",
        "required_fix": "",
        "required_concept": "",
    }


def _walk_rubric_node(value: Any, path: list[str], exercises: list[dict[str, Any]]) -> None:
    if isinstance(value, dict):
        if "traceback" in value:
            exercises.append(_build_mapping_exercise(value, path))
            return

        for key, nested_value in value.items():
            if key == "full project":
                continue
            _walk_rubric_node(nested_value, [*path, str(key)], exercises)
        return

    if isinstance(value, list):
        for index, nested_value in enumerate(value, start=1):
            if isinstance(nested_value, str):
                exercises.append(_build_string_exercise(
                    nested_value, path, index))
            else:
                _walk_rubric_node(nested_value, [*path, str(index)], exercises)


def _parse_exercises(rubric_data: dict[str, Any]) -> list[dict[str, Any]]:
    exercises: list[dict[str, Any]] = []
    _walk_rubric_node(rubric_data, [], exercises)
    return exercises


def build_rubric_state(rubric_data: dict[str, Any]) -> dict[str, Any]:
    return {
        "exercises": _parse_exercises(rubric_data),
        "full_project": _rubric_full_project(rubric_data),
    }


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


def error_type(error: str) -> str:
    for line in reversed(error.splitlines()):
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


def parse_debugging_response(
        raw_response: str | None,
        schema_name: str,
) -> dict[str, Any]:
    if not raw_response:
        return _empty_schema_response(schema_name)

    try:
        response = DEBUGGING_RESPONSE_MODELS[schema_name].model_validate_json(
            raw_response.strip(),
        )
    except (ValidationError, ValueError, TypeError, json.JSONDecodeError):
        return _empty_schema_response(schema_name)

    payload = response.model_dump()
    if schema_name == "priority_assessment" and payload["status"] not in PRIORITY_STATUSES:
        return _empty_schema_response(schema_name)
    return payload
