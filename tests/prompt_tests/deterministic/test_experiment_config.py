"""Tests for self-contained experiment specifications."""

from pathlib import Path

from experiments.config import ExperimentModels, ExperimentSpecification
from experiments.config import load_experiment_specification
from experiments.evaluation.config import load_evaluation_suite
from experiments.runner import ROOT, _configure_models, _specification_path
from src.gen_ai.build import build_agent
from src.gen_ai.gen_ai import Agent
from src.utils.config_loader import load_configuration


def test_baseline_declares_every_model_and_all_cases() -> None:
    path = ROOT / "experiments/configs/standard-duck-baseline.yaml"

    specification = load_experiment_specification(path)

    assert specification.models.response == "gpt-5.6-luna"
    assert specification.models.evaluator == "gpt-5.6-sol"
    assert specification.models.jev == "jev-latest"
    assert specification.cases == "all"


def test_experiment_name_resolves_to_config_file() -> None:
    assert _specification_path("standard-duck-baseline") == (
        ROOT / "experiments/configs/standard-duck-baseline.yaml"
    )
    assert _specification_path("custom/experiment.yaml") == Path(
        "custom/experiment.yaml"
    )


def test_pytest_model_defaults() -> None:
    prompt_config = load_evaluation_suite(
        ROOT / "tests/prompt_tests/configs"
    ).config
    application_config = load_configuration(str(ROOT / "production-config.yaml"))
    response_agent = build_agent(
        application_config["ducks"]["standard-rubber-duck"]["settings"]["agent"]
    )

    assert response_agent.model == "gpt-5.6-luna"
    assert prompt_config["evaluator_model"] == "gpt-5.6-luna"
    assert prompt_config["jev_model"] == "jev-latest"


def test_experiment_models_override_pytest_defaults() -> None:
    specification = ExperimentSpecification(
        name="model-override",
        models=ExperimentModels(
            response="response-override",
            evaluator="evaluator-override",
            jev="jev-override",
        ),
    )
    agent = Agent(
        name="RubberDuck",
        prompt="Tutor prompt",
        model="default-response",
        tools=["talk_to_user"],
    )
    prompt_config = load_evaluation_suite(
        ROOT / "tests/prompt_tests/configs"
    ).config

    configured_agent, configured_evaluation, jev_model = _configure_models(
        specification,
        agent,
        prompt_config,
    )

    assert configured_agent.model == "response-override"
    assert configured_evaluation["evaluator_model"] == "evaluator-override"
    assert configured_evaluation["jev_model"] == "jev-override"
    assert jev_model == "jev-override"
