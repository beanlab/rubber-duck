from pydantic import ValidationError

from src.utils.config_types import GPTMessage


def is_gpt_message(data: dict) -> bool:
    try:
        GPTMessage.model_validate(data)
        return True
    except ValidationError:
        return False