from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class CaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DatasetFixture(CaseModel):
    filename: str
    dataset_name: str
    path: str
    description: str


class HistoryTurn(CaseModel):
    role: Literal["user", "assistant"]
    content: str


class TextExpectation(CaseModel):
    contains_all: list[str] = Field(default_factory=list)
    excludes: list[str] = Field(default_factory=list)
    question: bool = False


class DecisionExpectation(CaseModel):
    analysis_requested: bool
    analysis_description: TextExpectation | None = None
    missing_information: TextExpectation | None = None


class CaseExpectation(CaseModel):
    decision: DecisionExpectation | None = None
    order: dict[str, JsonValue] | None = None
    code: TextExpectation | None = None
    texts: list[TextExpectation] = Field(default_factory=list)
    images: int = 0
    tables: int = 0


AgentStage = Literal["decision", "order", "coder"]
ExecutionKind = Literal["text", "image", "table"]


class StatsCase(CaseModel):
    id: str
    context: str
    run: AgentStage | Literal["full"] | list[AgentStage]
    history: list[HistoryTurn] = Field(default_factory=list)
    analysis_description: str | None = None
    order: dict[str, JsonValue] | None = None
    turns: list[str] = Field(default_factory=list)
    execution: ExecutionKind | None = None
    expect: CaseExpectation


class TestSuite(CaseModel):
    model: str
    reasoning: str | None = None
    base_prompt: Path
    contexts: dict[str, list[DatasetFixture]]
    cases: list[StatsCase]

    @model_validator(mode="after")
    def validate_cases(self) -> Self:
        ids = [case.id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("Case IDs must be unique")
        unknown = sorted({case.context for case in self.cases} - set(self.contexts))
        if unknown:
            raise ValueError(f"Unknown dataset contexts: {unknown}")
        return self


def load_suite(path: Path) -> TestSuite:
    data: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    return TestSuite.model_validate(data)
