from typing import TypedDict, Literal

from openai.types.responses import ResponseFunctionToolCallParam
from openai.types.responses.response_input_item import FunctionCallOutput

class Message(TypedDict):
    role: Literal['system', 'developer', 'user', 'assistant']
    content: str



class Context:
    def __init__(self):
        self._items: list[Message | ResponseFunctionToolCallParam | FunctionCallOutput] = []

    def update(self, new_item: Message | ResponseFunctionToolCallParam | FunctionCallOutput):
        self._items.append(new_item)

    def get_items(self) -> list[Message | ResponseFunctionToolCallParam | FunctionCallOutput]:
        return self._items

    def get_string_items(self) -> str:
        lines = []
        for item in self._items:
            if isinstance(item, dict):
                if item.get("role"):
                    lines.append(f"{item['role'].upper()}: {item['content']}")
                elif item.get("type") == "function_call":
                    lines.append(f"FUNCTION CALL [{item['name']}] with args: {item['arguments']}")
                elif item.get("type") == "function_output":
                    lines.append(f"FUNCTION OUTPUT for call {item['call_id']}: {item['output']}")
                else:
                    lines.append(str(item))
            else:
                lines.append(str(item))
        return "\n".join(lines)

    def __iter__(self):
        return iter(self._items)
