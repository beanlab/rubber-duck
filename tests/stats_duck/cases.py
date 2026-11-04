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
Handoff = Literal["fixed", "model", "both"]


class StatsCase(CaseModel):
    id: str
    context: str
    run: AgentStage | Literal["full"] | list[AgentStage]
    handoff: Handoff = "model"
    history: list[HistoryTurn] = Field(default_factory=list)
    analysis_description: str | None = None
    order: dict[str, JsonValue] | None = None
    turns: list[str] = Field(default_factory=list)
    execution: ExecutionKind | None = None
    expect: CaseExpectation

    @model_validator(mode="after")
    def validate_run(self) -> Self:
        match self.run:
            case "full":
                return self
            case "decision" | "order" | "coder":
                stages: list[AgentStage] = [self.run]
            case _:
                stages = self.run

        if not stages:
            raise ValueError("Agent sequences cannot be empty")
        expected_order: list[AgentStage] = ["decision", "order", "coder"]
        start = expected_order.index(stages[0])
        if stages != expected_order[start:start + len(stages)]:
            raise ValueError("Agent sequences must follow decision, order, coder")

        if stages[0] == "order" and self.analysis_description is None:
            raise ValueError("Order runs require analysis_description")
        if stages[0] == "coder" and self.order is None:
            raise ValueError("Coder runs require order")

        if len(stages) > 1 and self.handoff in ("fixed", "both"):
            if "decision" in stages[:-1] and self.analysis_description is None:
                raise ValueError("Fixed decision handoffs require analysis_description")
            if "order" in stages[:-1] and self.order is None:
                raise ValueError("Fixed order handoffs require order")
        return self


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
