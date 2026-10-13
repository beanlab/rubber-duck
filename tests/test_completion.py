from pydantic import BaseModel

from tests.prompt_evaluation.completion import _response_text_config


class StructuredAnswer(BaseModel):
    answer: str


def test_pydantic_output_contract_becomes_responses_json_schema() -> None:
    assert _response_text_config(StructuredAnswer) == {
        "format": {
            "type": "json_schema",
            "name": "StructuredAnswer",
            "schema": {
                "properties": {
                    "answer": {"title": "Answer", "type": "string"},
                },
                "required": ["answer"],
                "title": "StructuredAnswer",
                "type": "object",
            },
            "strict": True,
        }
    }
