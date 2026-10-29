"""YAML configuration for pytest-based prompt evaluation."""

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import TypeAdapter

from experiments.evaluation.types import (
    EvaluationCase,
    EvaluationCasesFile,
    EvaluationConfig,
    RubberDuckTestConfig,
    RubberDuckTestsConfig,
)


@dataclass(frozen=True)
class EvaluationSuite:
    """Resolved cases and criteria shared by tests and experiments."""

    config: EvaluationConfig
    cases: list[EvaluationCase]
    rubber_duck_tests: dict[str, RubberDuckTestConfig]


def load_evaluation_suite(directory: Path) -> EvaluationSuite:
    """Load and validate the canonical three-file evaluation suite."""
    config = TypeAdapter(EvaluationConfig).validate_python(
        _load_yaml(directory / "config.yaml")
    )
    cases = TypeAdapter(EvaluationCasesFile).validate_python(
        _load_yaml(directory / "cases.yaml")
    )["cases"]
    case_ids = [case["id"] for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Evaluation case IDs must be unique")
    rubber_duck_tests = TypeAdapter(RubberDuckTestsConfig).validate_python(
        _load_yaml(directory / "rubber_duck_tests.yaml")
    )["rubber_duck_tests"]
    return EvaluationSuite(config, cases, rubber_duck_tests)


def case_configuration(
    shared: EvaluationConfig,
    case: EvaluationCase,
) -> EvaluationConfig:
    """Attach evaluator-only case data without mutating shared configuration."""
    config = shared.copy()
    config["reference_answer"] = case["reference_answer"]
    config["case_tests"] = case.get("tests", {})
    return config


def _load_yaml(path: Path) -> object:
    data: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data
