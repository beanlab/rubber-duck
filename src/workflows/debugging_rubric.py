from dataclasses import dataclass
from typing import Any, Iterable

import yaml


@dataclass(frozen=True)
class RubricScenario:
    name: str
    rubric_item: str
    error: str
    code: str
    error_line: str
    intended_behavior: str
    required_fix: str
    required_concept: str


class Rubric:
    PRIORITY_KEYS = ("error_meaning", "error_location", "intended_behavior", "fix")

    def __init__(self, rubric_data: dict[str, Any]):
        self.scenarios = self._parse_scenarios(rubric_data)
        self.full_project = self._full_project(rubric_data)
        self.current_scenario_index = 0
        self.priorities = self._empty_priorities()
        self.active_transfer_priority: str | None = None
        self.active_incomplete_priority: str | None = None
        self.active_incomplete_prompt_count = 0

    @classmethod
    def from_rubric_data(cls, rubric_data: dict[str, Any]) -> "Rubric":
        return cls(rubric_data)

    @property
    def current_scenario(self) -> RubricScenario | None:
        if self.current_scenario_index >= len(self.scenarios):
            return None
        return self.scenarios[self.current_scenario_index]

    @property
    def next_scenario_name(self) -> str | None:
        next_index = self.current_scenario_index + 1
        if next_index >= len(self.scenarios):
            return None
        return self.scenarios[next_index].name

    @property
    def first_error(self) -> str:
        for scenario in self.scenarios:
            if scenario.error:
                return scenario.error
        return ""

    def is_finished(self) -> bool:
        return self.current_scenario_index >= len(self.scenarios)

    def current_item_fulfilled(self) -> bool:
        return all(self.priorities.values())

    def priority_fulfilled(self, priority_key: str) -> bool:
        return bool(self.priorities.get(priority_key))

    def apply_fulfilled_priorities(self, fulfilled_priorities: Iterable[str]) -> None:
        for priority_key in fulfilled_priorities:
            if priority_key in self.priorities:
                self.priorities[priority_key] = True

    def mark_priority_fulfilled(self, priority_key: str) -> None:
        if priority_key in self.priorities:
            self.priorities[priority_key] = True

    def reset_priority_state(self) -> None:
        self.priorities = self._empty_priorities()

    def advance_scenario(self) -> None:
        if self.current_scenario_index < len(self.scenarios):
            self.current_scenario_index += 1
        self.reset_priority_state()
        self.clear_active_response_state()

    def clear_active_response_state(self) -> None:
        self.active_transfer_priority = None
        self.active_incomplete_priority = None
        self.active_incomplete_prompt_count = 0

    def set_active_transfer_priority(self, priority_key: str | None) -> None:
        self.active_transfer_priority = priority_key

    def set_active_incomplete_priority(self, priority_key: str | None) -> None:
        self.active_incomplete_priority = priority_key

    def increment_incomplete_prompt_count(self) -> None:
        self.active_incomplete_prompt_count += 1

    def reset_incomplete_prompt_count(self) -> None:
        self.active_incomplete_prompt_count = 0

    def _empty_priorities(self) -> dict[str, bool]:
        return {priority_key: False for priority_key in self.PRIORITY_KEYS}

    @staticmethod
    def _full_project(rubric: dict[str, Any]) -> str:
        full_project = rubric.get("full project", "")
        if isinstance(full_project, str):
            return full_project
        if full_project:
            return yaml.safe_dump(full_project)
        return ""

    @staticmethod
    def _field_text(value: Any) -> str:
        if isinstance(value, str):
            return value.strip()

        if isinstance(value, list):
            return "\n".join(
                field_text
                for item in value
                if (field_text := Rubric._field_text(item))
            ).strip()

        if isinstance(value, dict):
            return yaml.safe_dump(value, sort_keys=False).strip()

        if value is None:
            return ""

        return str(value).strip()

    @staticmethod
    def _rubric_field_text(value: Any, field_name: str) -> str:
        if not isinstance(value, dict) or field_name not in value:
            return ""

        return Rubric._field_text(value[field_name])

    @staticmethod
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

    @staticmethod
    def _traceback_text(value: Any) -> str:
        if isinstance(value, str):
            return Rubric._traceback_from_string(value) or value.strip()

        if isinstance(value, list):
            for nested_value in value:
                error = Rubric._traceback_text(nested_value)
                if error:
                    return error
            return ""

        if isinstance(value, dict):
            for nested_value in value.values():
                error = Rubric._traceback_text(nested_value)
                if error:
                    return error
        return ""

    @staticmethod
    def _first_traceback(value: Any) -> str:
        if isinstance(value, str):
            return Rubric._traceback_from_string(value)

        if isinstance(value, dict):
            if "traceback" in value:
                return Rubric._traceback_text(value["traceback"])

            for nested_value in value.values():
                error = Rubric._first_traceback(nested_value)
                if error:
                    return error
            return ""

        if isinstance(value, list):
            for nested_value in value:
                error = Rubric._first_traceback(nested_value)
                if error:
                    return error
        return ""

    @classmethod
    def _parse_scenarios(cls, rubric: dict[str, Any]) -> list[RubricScenario]:
        scenarios: list[RubricScenario] = []

        def walk(value: Any, path: list[str]) -> None:
            if isinstance(value, dict):
                if "traceback" in value:
                    name = " > ".join(path) if path else "rubric item"
                    scenarios.append(RubricScenario(
                        name=name,
                        rubric_item=yaml.safe_dump(value, sort_keys=False).strip(),
                        error=cls._first_traceback(value),
                        code=cls._rubric_field_text(value, "code"),
                        error_line=cls._rubric_field_text(value, "error line"),
                        intended_behavior=cls._rubric_field_text(value, "intended behavior"),
                        required_fix=cls._rubric_field_text(value, "required fix"),
                        required_concept=cls._rubric_field_text(value, "required concept"),
                    ))
                    return

                for key, nested_value in value.items():
                    if key == "full project":
                        continue
                    walk(nested_value, [*path, str(key)])
                return

            if isinstance(value, list):
                for index, nested_value in enumerate(value, start=1):
                    if isinstance(nested_value, str):
                        name = " > ".join(path) if path else f"rubric item {index}"
                        scenarios.append(RubricScenario(
                            name=name,
                            rubric_item=nested_value,
                            error=cls._first_traceback(nested_value),
                            code="",
                            error_line="",
                            intended_behavior="",
                            required_fix="",
                            required_concept="",
                        ))
                    else:
                        walk(nested_value, [*path, str(index)])

        walk(rubric, [])
        return scenarios
