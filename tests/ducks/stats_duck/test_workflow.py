import pytest

from .assertions import assert_deliveries, read_scalar
from .fakes import ScriptedMessages, context

pytestmark = [
    pytest.mark.anyio,
]


# Compare a complete analysis with its independently known numerical result.
@pytest.mark.prompt_eval
@pytest.mark.parametrize(("question", "expected_value"), [])
@pytest.mark.skip(reason="Function signatures only; implementation pending.")
async def test_scalar_analysis(stats_duck, run_conversation, question, expected_value):
    ...


# Check delivery of the requested text, table, or image artifact.
@pytest.mark.prompt_eval
@pytest.mark.parametrize(("question", "expected_kind"), [])
@pytest.mark.skip(reason="Function signatures only; implementation pending.")
async def test_artifact_delivery(stats_duck, run_conversation, question, expected_kind):
    ...


# Check that missing details produce focused clarification before analysis.
@pytest.mark.prompt_eval
@pytest.mark.parametrize(("turns", "expected_missing_fields"), [])
@pytest.mark.skip(reason="Function signatures only; implementation pending.")
async def test_clarification(stats_duck, run_conversation, turns, expected_missing_fields):
    ...


# Follow decision, order, generated code, real execution, and delivery for a known calculation.
@pytest.mark.parametrize(
    ("question", "scripted_responses", "expected_order", "expected_value"), []
)
@pytest.mark.skip(reason="Function signatures only; implementation pending.")
async def test_analysis_workflow(
    stats_duck, evaluation, run_conversation, question, expected_order, expected_value
):
    ...


# List or describe real fixture datasets without calling the coder or executing Python.
@pytest.mark.parametrize(("question", "scripted_responses", "expected_content"), [])
@pytest.mark.skip(reason="Function signatures only; implementation pending.")
async def test_dataset_workflow(
    stats_duck, evaluation, run_conversation, question, expected_content
):
    ...


# Ask for missing details and use the user's answer to complete the requested calculation.
@pytest.mark.parametrize(
    ("turns", "scripted_responses", "expected_order", "expected_value"), []
)
@pytest.mark.skip(reason="Function signatures only; implementation pending.")
async def test_clarification_workflow(
    stats_duck, evaluation, run_conversation, turns, expected_order, expected_value
):
    ...


# Convert executed outputs into the expected user-visible text, tables, and images.
@pytest.mark.parametrize(("question", "scripted_responses", "expected_artifacts"), [])
@pytest.mark.skip(reason="Function signatures only; implementation pending.")
async def test_artifact_workflow(
    stats_duck, evaluation, run_conversation, question, expected_artifacts
):
    ...


# Include delivered results in history so a later request can refer to the preceding analysis.
@pytest.mark.parametrize(
    ("turns", "scripted_responses", "expected_requests", "expected_values"), []
)
@pytest.mark.skip(reason="Function signatures only; implementation pending.")
async def test_follow_up_workflow(
    stats_duck, evaluation, run_conversation, turns, expected_requests, expected_values
):
    ...


# Reuse the result for an equivalent canonical order while executing a different order separately.
@pytest.mark.parametrize(("turns", "scripted_responses", "expected_executions"), [])
@pytest.mark.skip(reason="Function signatures only; implementation pending.")
async def test_cache_reuse(
    stats_duck, evaluation, run_conversation, turns, expected_executions
):
    ...


# Repair failed execution or missing artifacts once and deliver either its result or a clear failure.
@pytest.mark.parametrize(("scripted_responses", "execution_results", "expected_deliveries"), [])
@pytest.mark.skip(reason="Function signatures only; implementation pending.")
async def test_code_repair(
    stats_duck, evaluation, run_conversation, execution_results, expected_deliveries
):
    ...


# Preserve live workflow delivery cases using controlled messages and sandbox artifacts.
@pytest.mark.prompt_eval
@pytest.mark.parametrize(
    ('turns', 'execution', 'expected'),
    [
        pytest.param(
            ["Make a histogram of calories from the cereal dataset."],
            "image",
            {
                "images": 1,
                "code": {
                    "contains_all": ["histplot", "calories", "cereal.csv", "savefig"],
                    "excludes": ["```"],
                },
            },
            id="full-ready-histogram",
        ),
        pytest.param(
            ["Make a histogram."],
            None,
            {
                "texts": [
                    {
                        "contains_all": ["dataset", "variable"],
                        "excludes": ["cereal.csv", "restaurant_nutrition.csv"],
                        "question": True,
                    },
                ],
            },
            id="full-missing-dataset",
        ),
        pytest.param(
            ["What datasets are available?"],
            None,
            {
                "texts": [
                    {
                        "contains_all": [
                            "Available datasets",
                            "Cereal Nutrition Data",
                            "Restaurant Nutrition Data",
                        ],
                        "excludes": ["cereal.csv", "restaurant_nutrition.csv"],
                    },
                ],
            },
            id="full-list-datasets",
        ),
        pytest.param(
            ["Describe the cereal dataset."],
            None,
            {
                "texts": [
                    {"contains_all": ["Cereal Nutrition Data", "cereal", "calories"]},
                ],
            },
            id="full-describe-cereal",
        ),
        pytest.param(
            ["Calculate the mean calories in the cereal dataset."],
            "text",
            {
                "texts": [{"contains_all": ["Analysis result"]}],
                "code": {
                    "contains_all": ["cereal.csv", "calories", "mean", "print"],
                    "excludes": ["```"],
                },
            },
            id="full-mean-calories",
        ),
        pytest.param(
            ["Make a histogram.", "Use the cereal dataset and the calories variable."],
            "image",
            {
                "texts": [{"contains_all": ["dataset", "variable"], "question": True}],
                "images": 1,
                "code": {
                    "contains_all": ["histplot", "calories", "cereal.csv", "savefig"],
                    "excludes": ["```"],
                },
            },
            id="full-clarify-then-histogram",
        )
    ],
)
async def test_workflow_deliveries(model_workflow, turns, execution, expected):
    workflow, sandbox, messages = model_workflow
    sandbox.execution = execution
    workflow._wait_message = ScriptedMessages(turns)
    await workflow(context())
    assert_deliveries(messages, sandbox, expected)
