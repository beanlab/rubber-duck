from pathlib import Path

from .gen_ai import Agent
from ..utils.config_types import (
    SingleAgentSettings,
)


def build_agent(config: SingleAgentSettings) -> Agent:
    prompt = config.get("prompt")
    if not prompt:
        prompt_files = config.get("prompt_files")
        if not prompt_files:
            raise ValueError(
                f"You must provide either 'prompt' or 'prompt_files' for {config['name']}"
            )
        prompt = "\n".join(
            [Path(prompt_path).read_text(encoding="utf-8") for prompt_path in prompt_files]
        )

    tool_required = config.get("tool_required", "auto")
    if tool_required not in ["auto", "required", "none"]:
        tool_required = {"type": "function", "name": tool_required}

    output_schema = config.get("output_format", None)

    return Agent(
        name=config["name"],
        prompt=prompt,
        model=config["engine"],
        tools=config["tools"],
        tool_settings=tool_required,
        output_format=output_schema,
        reasoning=config.get("reasoning"),
    )
