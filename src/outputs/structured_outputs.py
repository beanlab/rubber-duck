from typing import Dict

from pydantic import BaseModel, create_model

ALLOWED_TYPES = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "list": list,
    "dict": dict,
    "None": type(None),
}


class PrettyModel(BaseModel):
    def __str__(self) -> str:
        return "\n".join(f"{k}: {v}" for k, v in self.dict().items())


def schema_to_model(name: str, fields: Dict[str, str]) -> type[BaseModel]:
    """Create a Pydantic model given a model name and fields dict."""
    parsed_fields = {k: (ALLOWED_TYPES[v], ...) for k, v in fields.items()}
    return create_model(name, __base__=PrettyModel, **parsed_fields)
