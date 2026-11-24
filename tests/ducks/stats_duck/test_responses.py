"""Live stage responses and diagnostic handoffs using ordinary pytest cases."""

import ast

import pytest

from .assertions import assert_decision, assert_text
from .fakes import context, history

pytestmark = [pytest.mark.anyio, pytest.mark.prompt_eval]


# Check each decision response against the supplied conversation history.
@pytest.mark.parametrize(
    ('turns', 'expected'),
    [
        pytest.param(
            [
                {
                    "role": "user",
                    "content": "Make a histogram of calories from the cereal dataset.",
                },
            ],
            {
                "analysis_requested": True,
                "analysis_description": {
                    "contains_all": ["histogram", "calories", "cereal"],
                },
            },
            id="decide-ready-histogram",
        ),
        pytest.param(
            [{"role": "user", "content": "Make a histogram."}],
            {
                "analysis_requested": False,
                "missing_information": {"contains_all": ["dataset", "variable"]},
            },
            id="decide-missing-dataset",
        ),
        pytest.param(
            [
                {
                    "role": "user",
                    "content": "Calculate the mean from the cereal dataset.",
                },
                {"role": "assistant", "content": "Which variable should I use?"},
                {"role": "user", "content": "Calories."},
            ],
            {
                "analysis_requested": True,
                "analysis_description": {"contains_all": ["mean", "calories", "cereal"]},
            },
            id="decide-follow-up-uses-history",
        )
    ],
)
async def test_decision(model_workflow, turns, expected):
    workflow, _, _ = model_workflow
    result = await workflow._decide(context(), history(turns))
    assert_decision(result, expected)


# Check canonical orders independently of preceding model decisions.
@pytest.mark.parametrize(
    ('description', 'expected_order'),
    [
        pytest.param(
            "Create a histogram of calories from the cereal dataset.",
            {
                "plot": "seaborn.histplot",
                "data": "cereal.csv",
                "args": {"x": "calories"},
            },
            id="order-cereal-histogram",
        ),
        pytest.param(
            "List the available datasets.",
            {"action": "list_datasets", "data": None},
            id="order-list-datasets",
        )
    ],
)
async def test_order(model_workflow, description, expected_order):
    workflow, _, _ = model_workflow
    result = await workflow._order_from_menu(context(), description)
    assert result == expected_order


# Preserve Python syntax and code-content checks without claiming numerical correctness.
@pytest.mark.parametrize(
    ('order', 'expected_code'),
    [
        pytest.param(
            {
                "plot": "seaborn.histplot",
                "data": "cereal.csv",
                "args": {"x": "calories"},
            },
            {
                "contains_all": ["histplot", "calories", "cereal.csv", "savefig"],
                "excludes": ["```"],
            },
            id="code-cereal-histogram",
        )
    ],
)
async def test_generated_code(model_workflow, order, expected_code):
    workflow, _, _ = model_workflow
    code = await workflow._generate_code(context(), order)
    ast.parse(code)
    assert_text(code, expected_code)


# Exercise fixed and model-produced decision-to-order inputs as isolated stage diagnostics.
@pytest.mark.parametrize("handoff", ["fixed", "model"])
@pytest.mark.parametrize(
    ('turns', 'fixed_description', 'expected'),
    [
        pytest.param(
            [
                {
                    "role": "user",
                    "content": "Make a histogram of calories from the cereal dataset.",
                },
            ],
            "Create a histogram of calories from the cereal dataset.",
            {
                "decision": {
                    "analysis_requested": True,
                    "analysis_description": {
                        "contains_all": ["histogram", "calories", "cereal"],
                    },
                },
                "order": {
                    "plot": "seaborn.histplot",
                    "data": "cereal.csv",
                    "args": {"x": "calories"},
                },
            },
            id="decision-to-order",
        )
    ],
)
async def test_decision_order_handoff(
    model_workflow, turns, fixed_description, expected, handoff
):
    workflow, _, _ = model_workflow
    decision = await workflow._decide(context(), history(turns))
    assert_decision(decision, expected["decision"])
    description = fixed_description if handoff == "fixed" else decision["analysis_description"]
    order = await workflow._order_from_menu(context(), description)
    assert order == expected["order"]


# Exercise fixed and model-produced coder inputs after validating the preceding decision and order.
@pytest.mark.parametrize("handoff", ["fixed", "model"])
@pytest.mark.parametrize(
    ('turns', 'fixed_description', 'fixed_order', 'expected'),
    [
        pytest.param(
            [
                {
                    "role": "user",
                    "content": "Calculate the mean calories in the cereal dataset.",
                },
            ],
            "Calculate the mean of calories in the cereal dataset.",
            {"data": "cereal.csv", "analysis": "mean", "args": {"column": "calories"}},
            {
                "decision": {
                    "analysis_requested": True,
                    "analysis_description": {
                        "contains_all": ["mean", "calories", "cereal"],
                    },
                },
                "order": {
                    "data": "cereal.csv",
                    "analysis": "mean",
                    "args": {"column": "calories"},
                },
                "code": {
                    "contains_all": ["cereal.csv", "calories", "mean", "print"],
                    "excludes": ["```"],
                },
            },
            id="decision-to-order-to-coder-mean",
        )
    ],
)
async def test_decision_order_coder_handoff(
    model_workflow, turns, fixed_description, fixed_order, expected, handoff
):
    workflow, _, _ = model_workflow
    decision = await workflow._decide(context(), history(turns))
    assert_decision(decision, expected["decision"])
    description = fixed_description if handoff == "fixed" else decision["analysis_description"]
    order = await workflow._order_from_menu(context(), description)
    assert order == expected["order"]
    code = await workflow._generate_code(context(), fixed_order if handoff == "fixed" else order)
    ast.parse(code)
    assert_text(code, expected["code"])


# Execute generated code on known data and check its independently calculated numerical result.
@pytest.mark.skip(reason="Function signatures only; implementation pending.")
@pytest.mark.parametrize(("order", "expected_value"), [])
async def test_coder(stats_duck, evaluation, run_stage, order, expected_value):
    ...


# Evaluate the clarification prompt with fixed guidance and conversation context.
@pytest.mark.skip(reason="Function signatures only; implementation pending.")
@pytest.mark.parametrize(("history", "missing_information", "expected_properties"), [])
async def test_clarification_prompt(
    stats_duck, evaluation, run_stage, history, missing_information, expected_properties
):
    ...
