from src.workflows.stats_duck.stats_duck_workflow import INTRODUCTION


# Check required terms, excluded terms, and question form in a model response.
def assert_text(value: str, expected: dict) -> None:
    normalized = value.casefold()
    missing = [
        term for term in expected.get("contains_all", []) if term.casefold() not in normalized
    ]
    excluded = [
        term for term in expected.get("excludes", []) if term.casefold() in normalized
    ]
    assert not missing, f"missing {missing}; received {value!r}"
    assert not excluded, f"contained excluded terms {excluded}; received {value!r}"
    assert not expected.get("question", False) or "?" in value, (
        f"expected a question; received {value!r}"
    )


# Check structured decisions and any declared analysis or clarification requirements.
def assert_decision(result: dict, expected: dict) -> None:
    assert result["analysis_requested"] is expected["analysis_requested"], result
    if expected.get("analysis_description"):
        assert_text(result["analysis_description"] or "", expected["analysis_description"])
    if expected.get("missing_information"):
        assert_text(result["missing_information"] or "", expected["missing_information"])


# Preserve the existing delivery checks without treating a canned sandbox value as numerical evidence.
def assert_deliveries(messages, sandbox, expected: dict) -> None:
    assert sandbox.execution is None
    assert messages.texts[0] == INTRODUCTION
    texts = messages.texts[1:]
    assert len(texts) == len(expected.get("texts", []))
    for value, requirement in zip(texts, expected.get("texts", []), strict=True):
        assert_text(value, requirement)
    assert len(messages.images) == expected.get("images", 0)
    assert len(messages.tables) == expected.get("tables", 0)
    if expected.get("code"):
        assert len(sandbox.generated_code) == 1
        assert_text(sandbox.generated_code[0], expected["code"])
    else:
        assert not sandbox.generated_code


# Read the delivered scalar and reject missing or ambiguous numerical output.
def read_scalar(deliveries: list[dict]) -> float:
    ...
