"""Typed configuration for fixed-prefix prompt experiments."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReportingSpecification(BaseModel):
    """Controls human-facing output without changing recorded evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    console: Literal["concise", "detailed"] = "concise"


class ExperimentSpecification(BaseModel):
    """The intentionally small first configuration contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    cases: Literal["all"] | list[str] = "all"
    repetitions: int = Field(default=1, ge=1)
    concurrency: int = Field(default=3, ge=1)
    output_directory: Path | None = None
    reporting: ReportingSpecification = ReportingSpecification()

    @field_validator("cases")
    @classmethod
    def validate_cases(
        cls,
        cases: Literal["all"] | list[str],
    ) -> Literal["all"] | list[str]:
        if cases != "all" and not cases:
            raise ValueError("cases must contain at least one case ID or be 'all'")
        if cases != "all" and len(cases) != len(set(cases)):
            raise ValueError("cases must not contain duplicate case IDs")
        return cases


def load_experiment_specification(path: Path) -> ExperimentSpecification:
    """Load one declarative experiment specification."""
    data: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    return ExperimentSpecification.model_validate(data)
