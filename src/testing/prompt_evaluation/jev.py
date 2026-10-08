"""JEV evaluator for binary prompt-quality criteria."""

import os
from typing import Any

from typesafe_sdk import AsyncTypeSafeClient, Choice

from src.testing.prompt_evaluation.types import (
    EvaluationConfig,
    EvaluationSummary,
    EvaluationTestConfig,
    EvaluatorContext,
    JevEvaluation,
    JevTestResult,
)


class JevEvaluator:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "jev-latest",
        client: Any = None,
    ) -> None:
        self.api_key = api_key or os.getenv("JEV_API_KEY")
        self.model = model
        self.client = client
        if not self.api_key and client is None:
            raise ValueError("JEV_API_KEY is required for JEV evaluation")

    async def evaluate(
        self,
        context: EvaluatorContext,
        config: EvaluationConfig,
        tests: dict[str, EvaluationTestConfig],
    ) -> JevEvaluation:
        if self.client is not None:
            return await self._evaluate(self.client, context, config, tests)
        async with AsyncTypeSafeClient(api_key=self.api_key) as client:
            return await self._evaluate(client, context, config, tests)

    async def _evaluate(
        self,
        client: Any,
        context: EvaluatorContext,
        config: EvaluationConfig,
        tests: dict[str, EvaluationTestConfig],
    ) -> JevEvaluation:
        questions = {
            name: Choice(
                instructions={
                    "test": test["definition"],
                    "rules": test.get("evaluator_prompt")
                    or config.get("evaluator_prompt"),
                },
                criteria={
                    rating: level["definition"]
                    for rating, level in test["metric"].items()
                },
            )
            for name, test in tests.items()
        }
        response = await client.system_one(
            state=context,
            questions=questions,
            model=self.model,
        )

        if set(response.choices) != set(tests):
            raise RuntimeError("JEV did not return every evaluation test")

        results: dict[str, JevTestResult] = {}
        for name in tests:
            answer = response.choices[name]
            if answer.choice not in {"pass", "fail"}:
                raise RuntimeError(f"JEV returned invalid rating: {answer.choice}")
            results[name] = {
                "rating": answer.choice,
                "confidence": answer.confidence,
                "probabilities": dict(answer.probabilities),
            }
        blocking = [
            name for name, result in results.items() if result["rating"] == "fail"
        ]
        summary: EvaluationSummary = {
            "passed": not blocking,
            "score": 1 - len(blocking) / len(results),
            "blocking_tests": blocking,
        }
        return {
            "model": response.model,
            "tests": results,
            "summary": summary,
        }
