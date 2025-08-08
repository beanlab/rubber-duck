from typing import Any, Type

from pydantic import BaseModel, create_model

from ..utils.config_types import StructuredOutput

class PrettyModel(BaseModel):
    def __str__(self) -> str:
        return "\n".join(f"{k.capitalize()}: {v}" for k, v in self.dict().items())

class StructuredOutputs:
    def __init__(self, model_defs: list[StructuredOutput]):
        self._models: dict[str, Type[BaseModel]] = {}
        for model_def in model_defs:
            self.register_model_from_dict(model_def)

    def _parse_type(self, type_str: str) -> Any:
        allowed_types = {"str": str, "int": int, "float": float, "bool": bool, "list": list, "dict": dict,
                         "None": type(None)}
        return eval(type_str, {"__builtins__": {}}, allowed_types)

    def register_model_from_dict(self, model_def: StructuredOutput):
        name = model_def["name"]
        fields = {
            field_name: (self._parse_type(type_str), ...)
            for field_name, type_str in model_def["fields"].items()
        }
        self._models[name] = create_model(name, __base__=PrettyModel, **fields)

    def get(self, name: str) -> Type[BaseModel]:
        return self._models[name]

    def all(self) -> dict[str, Type[BaseModel]]:
        return self._models
