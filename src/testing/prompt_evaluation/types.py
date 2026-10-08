"""Shared data contracts for fixed-prefix tutor response evaluation."""

from typing import Literal

from pydantic import BaseModel, ConfigDict
from typing_extensions import NotRequired, Protocol, TypedDict


TestOutcome = Literal["pass", "fail"]


class EvaluationResult(BaseModel):
    """Structured result returned by every configured evaluation test."""

    model_config = ConfigDict(extra="forbid")

    rating: TestOutcome
    evidence: list[str]
    rationale: str


class ParsedEvaluationResponse(Protocol):
    @property
    def output_parsed(self) -> EvaluationResult | None: ...


class ResponsesAPI(Protocol):
    async def parse(
        self,
        *,
        model: str,
        instructions: str,
        input: str,
        text_format: type[EvaluationResult],
        store: bool,
    ) -> ParsedEvaluationResponse: ...


class EvaluationClient(Protocol):
    @property
    def responses(self) -> ResponsesAPI: ...


class TranscriptTurn(TypedDict):
    role: Literal["student", "tutor"]
    message: str


class MetricLevel(TypedDict):
    definition: str


class EvaluationTestConfig(TypedDict):
    definition: str
    metric: dict[str, MetricLevel]
    evaluator_prompt: NotRequired[str]


class EvaluationConfig(TypedDict):
    evaluator_model: str
    jev_model: NotRequired[str]
    tests: dict[str, EvaluationTestConfig]
    evaluator_prompt: NotRequired[str]
    reference_answer: NotRequired[str]
    use_reference_answer: NotRequired[bool]


class EvaluationCase(TypedDict):
    id: str
    name: str
    transcript: list[TranscriptTurn]
    reference_answer: str
    tests: NotRequired[dict[str, EvaluationTestConfig]]


class EvaluatorContext(TypedDict):
    conversation_prefix: list[TranscriptTurn]
    candidate_response: TranscriptTurn
    tutor_prompt: str
    reference_answer: NotRequired[str]


class EvaluatorTestPrompt(TypedDict):
    name: str
    definition: str
    metric: dict[str, str]


class EvaluatorRequest(EvaluatorContext):
    test: EvaluatorTestPrompt


class TestResult(TypedDict):
    rating: TestOutcome
    evidence: list[str]
    rationale: str


class EvaluationSummary(TypedDict):
    passed: bool
    score: float
    blocking_tests: list[str]


class JevTestResult(TypedDict):
    rating: TestOutcome
    confidence: float
    probabilities: dict[str, float]


class JevEvaluation(TypedDict):
    model: str
    tests: dict[str, JevTestResult]
    summary: EvaluationSummary


class EvaluationRun(TypedDict):
    transcript: list[TranscriptTurn]
    tests: dict[str, TestResult]
    summary: EvaluationSummary
    reference_answer_used: bool
    jev: NotRequired[JevEvaluation]
