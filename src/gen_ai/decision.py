"""Provider-neutral decisions backed by external model services."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, TypeAlias

from pydantic import JsonValue, TypeAdapter
from typesafe_sdk import (
    AsyncTypeSafeClient,
    Choice,
    JSONContent as JevJSONContent,
    Question,
    SystemOneResponse,
)


JSONValue: TypeAlias = JsonValue
JSONContent: TypeAlias = dict[str, JSONValue]


@dataclass(frozen=True)
class ChoiceQuestion:
    """One named decision with explicit allowed outcomes."""

    instructions: dict[str, str]
    criteria: dict[str, str]


@dataclass(frozen=True)
class ChoiceDecision:
    """One provider decision normalized for application use."""

    choice: str
    confidence: float
    probabilities: dict[str, float]


@dataclass(frozen=True)
class DecisionResponse:
    """Named decisions returned by one provider request."""

    model: str
    decisions: dict[str, ChoiceDecision]


class DecisionService(Protocol):
    """Capability used when an application needs constrained decisions."""

    async def decide(
        self,
        state: dict[str, JSONValue],
        questions: Mapping[str, ChoiceQuestion],
    ) -> DecisionResponse: ...


class _JevClient(Protocol):
    async def system_one(
        self,
        state: JevJSONContent,
        questions: Mapping[str, Question],
        *,
        model: str | None = None,
    ) -> SystemOneResponse: ...


_JEV_JSON_CONTENT = TypeAdapter(JevJSONContent)


class JevDecisionService:
    """JEV implementation of the constrained-decision capability."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "jev-latest",
        client: _JevClient | None = None,
    ) -> None:
        self._api_key = api_key or os.getenv("JEV_API_KEY")
        self._model = model
        self._client = client
        if not self._api_key and client is None:
            raise ValueError("JEV_API_KEY is required for JEV decisions")

    async def decide(
        self,
        state: dict[str, JSONValue],
        questions: Mapping[str, ChoiceQuestion],
    ) -> DecisionResponse:
        if self._client is not None:
            return await self._decide(self._client, state, questions)
        async with AsyncTypeSafeClient(api_key=self._api_key) as client:
            return await self._decide(client, state, questions)

    async def _decide(
        self,
        client: _JevClient,
        state: dict[str, JSONValue],
        questions: Mapping[str, ChoiceQuestion],
    ) -> DecisionResponse:
        provider_questions: dict[str, Question] = {
            name: Choice(
                instructions=question.instructions,
                criteria=question.criteria,
            )
            for name, question in questions.items()
        }
        response = await client.system_one(
            state=_JEV_JSON_CONTENT.validate_python(state),
            questions=provider_questions,
            model=self._model,
        )
        if set(response.choices) != set(questions):
            raise RuntimeError("JEV did not return every requested decision")
        return DecisionResponse(
            model=response.model,
            decisions={
                name: ChoiceDecision(
                    choice=answer.choice,
                    confidence=answer.confidence,
                    probabilities=dict(answer.probabilities),
                )
                for name, answer in response.choices.items()
            },
        )
