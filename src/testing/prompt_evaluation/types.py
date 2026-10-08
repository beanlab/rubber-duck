"""Shared data contracts for fixed-prefix tutor response evaluation."""

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict
from typing_extensions import NotRequired, Protocol, TypedDict


TestOutcome = Literal["pass", "fail"]
ApplicabilityOutcome = Literal[
    "applicable",
    "not_applicable",
    "insufficient_evidence",
]
EvaluationScope = Literal["response", "action", "trajectory"]
EvaluationOracle = Literal["semantic", "deterministic"]
TestSelectionMode = Literal["always", "conditional"]
TestSuite = Literal["standard", "case", "rubber_duck"]
TestEvaluator = Literal["openai", "deterministic"]
ResponseAction = Literal[
    "talk_to_user",
    "conclude_conversation",
    "direct_message",
]


class EvaluationResult(BaseModel):
    """Structured result returned by every configured evaluation test."""

    model_config = ConfigDict(extra="forbid")

    rating: TestOutcome
    evidence: list[str]
    rationale: str


class NamedEvaluationResult(EvaluationResult):
    """One named result in a combined evaluator response."""

    name: str


class CombinedEvaluationResult(BaseModel):
    """Structured results for every selected semantic test."""

    model_config = ConfigDict(extra="forbid")

    results: list[NamedEvaluationResult]


ResponseModel = TypeVar("ResponseModel", bound=BaseModel, covariant=True)


class ParsedEvaluationResponse(Protocol, Generic[ResponseModel]):
    @property
    def model(self) -> str: ...

    @property
    def output_parsed(self) -> ResponseModel | None: ...


class ResponsesAPI(Protocol):
    async def parse(
        self,
        *,
        model: str,
        instructions: str,
        input: str,
        text_format: type[ResponseModel],
        store: bool,
    ) -> ParsedEvaluationResponse[ResponseModel]: ...


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


class RubberDuckTestConfig(EvaluationTestConfig):
    scope: EvaluationScope
    oracle: EvaluationOracle
    selection: TestSelectionMode
    applies_when: str


class EvaluationConfig(TypedDict):
    evaluator_model: str
    jev_model: NotRequired[str]
    standard_tests: dict[str, EvaluationTestConfig]
    case_tests: NotRequired[dict[str, EvaluationTestConfig]]
    evaluator_prompt: NotRequired[str]
    reference_answer: NotRequired[str]
    use_reference_answer: NotRequired[bool]


class RubberDuckTestsConfig(TypedDict):
    rubber_duck_tests: dict[str, RubberDuckTestConfig]


class EvaluationCase(TypedDict):
    id: str
    name: str
    transcript: list[TranscriptTurn]
    reference_answer: str
    tests: NotRequired[dict[str, EvaluationTestConfig]]


class EvaluationCasesFile(TypedDict):
    cases: list[EvaluationCase]


class EvaluatorContext(TypedDict):
    conversation_prefix: list[TranscriptTurn]
    candidate_response: TranscriptTurn
    candidate_action: ResponseAction
    tutor_prompt: str
    reference_answer: NotRequired[str]


class EvaluatorTestPrompt(TypedDict):
    name: str
    definition: str
    metric: dict[str, str]
    rules: str


class EvaluatorRequest(EvaluatorContext):
    tests: list[EvaluatorTestPrompt]


class TestResult(TypedDict):
    rating: TestOutcome
    evidence: list[str]
    rationale: str
    suite: TestSuite
    evaluator: TestEvaluator


class EvaluationSummary(TypedDict):
    passed: bool
    score: float
    blocking_tests: list[str]


class JevTestResult(TypedDict):
    rating: TestOutcome
    confidence: float
    probabilities: dict[str, float]
    suite: TestSuite


class JevApplicabilityResult(TypedDict):
    outcome: ApplicabilityOutcome
    confidence: float
    probabilities: dict[str, float]


class TestSelection(TypedDict):
    selected: list[str]
    skipped: list[str]
    uncertain: list[str]
    applicability: dict[str, JevApplicabilityResult]


class JevEvaluation(TypedDict):
    model: str
    tests: dict[str, JevTestResult]
    selection: TestSelection
    summary: EvaluationSummary


class EvaluationRun(TypedDict):
    transcript: list[TranscriptTurn]
    candidate_action: ResponseAction
    candidate_model: str
    openai_evaluator_model: str
    tests: dict[str, TestResult]
    summary: EvaluationSummary
    reference_answer_used: bool
    selection: NotRequired[TestSelection]
    jev: NotRequired[JevEvaluation]
