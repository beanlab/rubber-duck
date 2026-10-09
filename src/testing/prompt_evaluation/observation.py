"""Optional observation events emitted by prompt evaluation."""

from dataclasses import dataclass
from typing import Protocol

from src.gen_ai.completion import CompletionRequest, CompletionResult
from src.testing.prompt_evaluation.types import EvaluationRun, JevEvaluation


@dataclass(frozen=True)
class GenerationCompleted:
    """One fresh candidate generation completed."""

    request: CompletionRequest
    result: CompletionResult


@dataclass(frozen=True)
class SelectionCompleted:
    """JEV completed applicability selection and comparative grading."""

    result: JevEvaluation


@dataclass(frozen=True)
class EvaluationCompleted:
    """The complete synchronous evaluation result is available."""

    result: EvaluationRun


EvaluationEvent = GenerationCompleted | SelectionCompleted | EvaluationCompleted


class EvaluationObserver(Protocol):
    """Receives ephemeral evidence without controlling evaluator behavior."""

    def observe(self, event: EvaluationEvent) -> None: ...


class TrialCapture:
    """In-memory observer used by the explicit experiment runner."""

    def __init__(self) -> None:
        self.generation: GenerationCompleted | None = None
        self.selection: SelectionCompleted | None = None
        self.evaluation: EvaluationCompleted | None = None

    def observe(self, event: EvaluationEvent) -> None:
        if isinstance(event, GenerationCompleted):
            self.generation = event
        elif isinstance(event, SelectionCompleted):
            self.selection = event
        else:
            self.evaluation = event
