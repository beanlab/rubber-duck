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


class StageCase(CaseModel):
    id: str
    context: str


class DecisionCase(StageCase):
    history: list[HistoryTurn]
    expect: DecisionExpectation


class OrderCase(StageCase):
    analysis_description: str
    expect: dict[str, JsonValue]


class ClarificationCase(StageCase):
    history: list[HistoryTurn]
    missing_information: str
    expect: TextExpectation


class FulfillmentCase(StageCase):
    order: dict[str, JsonValue]
    expect: list[dict[str, JsonValue]]


class ChainExpectation(CaseModel):
    decision: DecisionExpectation
    order: dict[str, JsonValue] | None = None
    clarification: TextExpectation | None = None

    @model_validator(mode="after")
    def validate_branch(self) -> Self:
        if self.decision.analysis_requested:
            if self.order is None or self.clarification is not None:
                raise ValueError("Actionable chains require only an order")
        elif self.clarification is None or self.order is not None:
            raise ValueError("Incomplete chains require only a clarification")
        return self


class ChainCase(StageCase):
    history: list[HistoryTurn]
    expect: ChainExpectation


class WorkflowSuite(CaseModel):
    model: str
    reasoning: str | None = None
    base_prompt: Path
    contexts: dict[str, list[DatasetFixture]]
    decisions: list[DecisionCase]
    orders: list[OrderCase]
    clarifications: list[ClarificationCase]
    fulfillments: list[FulfillmentCase]
    chains: list[ChainCase]

    @model_validator(mode="after")
    def validate_cases(self) -> Self:
        cases: list[StageCase] = [
            *self.decisions,
            *self.orders,
            *self.clarifications,
            *self.fulfillments,
            *self.chains,
        ]
        ids = [case.id for case in cases]
        if len(ids) != len(set(ids)):
            raise ValueError("Case IDs must be unique")
        unknown = sorted({case.context for case in cases} - set(self.contexts))
        if unknown:
            raise ValueError(f"Unknown dataset contexts: {unknown}")
        return self


def load_suite(path: Path) -> WorkflowSuite:
    data: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    return WorkflowSuite.model_validate(data)
