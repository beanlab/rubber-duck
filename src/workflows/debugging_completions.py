import random
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .debugging_parsing import (
    error_type,
)


DEBUGGING_PRACTICE_FEEDBACK_MESSAGE = (
    "*The debugging practice duck is an experimental feature that is actively being developed. "
    "Please leave feedback below as to your experience using the duck.*"
)


@lru_cache(maxsize=1)
def load_debugging_practice_responses() -> dict[str, list[str]]:
    responses_path = Path(
        __file__).parents[1] / "prompts" / "debugging-practice-duck" / "prefabs.yaml"
    with responses_path.open(encoding="utf-8") as prefab_file:
        responses = yaml.safe_load(prefab_file) or {}
    return {
        key: value
        for key, value in responses.items()
        if isinstance(value, list)
    }


def priority_prompt(priority_key: str, error_type_name: str = "error") -> str:
    prompt = random.choice(load_debugging_practice_responses()[priority_key])
    return prompt.format(error_type=error_type_name or "error")


def priority_prompt_for_item(priority_key: str, exercise: dict[str, Any]) -> str:
    return priority_prompt(priority_key, error_type(exercise["error"]))


def build_completion_message() -> dict[str, Any]:
    return {
        "response": random.choice(load_debugging_practice_responses()["exercise_complete"]),
    }


def completed_item_transition_message() -> str:
    responses = load_debugging_practice_responses()
    return " ".join([
        random.choice(responses["item_complete"]),
        random.choice(responses["next_item"]),
    ])


def build_next_exercise_message(
        next_exercise: dict[str, Any],
        completed_previous: bool = False,
) -> dict[str, Any]:
    message_parts = [
        completed_item_transition_message()
        if completed_previous
        else "Here is the code and its associated error.",
    ]
    if next_exercise["code"]:
        message_parts.extend([
            "Code:",
            f"```python\n{next_exercise['code'].strip()}\n```",
        ])
    if next_exercise["error"]:
        message_parts.extend([
            "Traceback:",
            f"```\n{next_exercise['error']}\n```",
        ])
    return {
        "response": "\n\n".join(message_parts),
    }


def build_incorrect_response_message(
        completion: dict[str, Any],
        exercise: dict[str, Any],
        priority_key: str,
) -> dict[str, Any]:
    if completion["response"]:
        response = completion["response"]
    else:
        response = priority_prompt_for_item(priority_key, exercise)
    return {
        "response": response,
    }


def build_unrelated_response_message(
        completion: dict[str, Any],
) -> dict[str, Any]:
    if completion["response"]:
        response = completion["response"]
    else:
        response = random.choice(
            load_debugging_practice_responses()["retry_fix"])
    return {
        "response": response,
    }


def build_incomplete_response_message(
        decision: dict[str, Any],
) -> dict[str, Any]:
    return {
        "response": incomplete_response_message(decision),
    }


def incomplete_response_message(decision: dict[str, Any]) -> str:
    response = str(decision.get("response", "")).strip()
    if response:
        return response

    if decision["incomplete_response_part"].strip():
        return (
            f"I think this response is incomplete: {decision['incomplete_response_part'].strip()}\n\n"
            "Would you explain that in more detail?"
        )

    return random.choice(load_debugging_practice_responses()["retry_incomplete"])


def build_opening_message(settings: dict[str, Any]) -> str:
    return f"*{settings['first_message'].strip()}*"
