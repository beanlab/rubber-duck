from typing import Any

from .config_types import AgentMessage


def is_agent_message(value: Any) -> bool:
    try:
        AgentMessage.model_validate(value)
        return True
    except Exception:
        return False