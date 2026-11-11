import ast
from typing import Literal

from src.gen_ai.ai_responses import ResponsesAPI
from src.workflows.stats_duck.stats_duck_workflow import (
    INTRODUCTION,
    Decision,
    StatsOrder,
)
from tests.stats_duck.cases import (
    DecisionExpectation,
    StatsCase,
    TestSuite,
    TextExpectation,
)
from tests.stats_duck.harness import (
    Harness,
    build_harness,
    context,
    history,
    stats_order,
)


Status = Literal["passed", "failed", "blocked"]
Path = Literal["fixed", "model"]


class Report:
    def __init__(self, case_id: str) -> None:
        self.case_id = case_id
        self.results: list[tuple[str, Status, str]] = []

    def add(self, name: str, status: Status, detail: str = "") -> None:
        self.results.append((name, status, detail))
        print(f"  {status.upper():7} {name}", flush=True)
        if detail:
            print(f"          {detail}", flush=True)

    def start(self, name: str) -> None:
        print(f"  RUNNING {name}", flush=True)

    def finish(self) -> None:
        passed = sum(status == "passed" for _, status, _ in self.results)
        print(f"  RESULT  {passed}/{len(self.results)} stages passed")
        failures = [
            f"- {status}: {name}" + (f" — {detail}" if detail else "")
            for name, status, detail in self.results
            if status != "passed"
        ]
        assert not failures, f"{self.case_id}\n" + "\n".join(failures)


def assert_text(value: str, expected: TextExpectation) -> None:
    normalized = value.casefold()
    missing = [term for term in expected.contains_all if term.casefold() not in normalized]
    excluded = [term for term in expected.excludes if term.casefold() in normalized]
    assert not missing, f"missing {missing}; received {value!r}"
    assert not excluded, f"contained excluded terms {excluded}; received {value!r}"
    assert not expected.question or "?" in value, f"expected a question; received {value!r}"


def assert_decision(result: Decision, expected: DecisionExpectation) -> None:
    assert result["analysis_requested"] is expected.analysis_requested, (
        f"expected analysis_requested={expected.analysis_requested}; received {result!r}"
    )
    if expected.analysis_description:
        assert_text(result["analysis_description"] or "", expected.analysis_description)
    if expected.missing_information:
        assert_text(result["missing_information"] or "", expected.missing_information)


def assert_workflow(case: StatsCase, harness: Harness) -> None:
    assert harness.sandbox.execution is None
    assert harness.messages.texts[0] == INTRODUCTION
    texts = harness.messages.texts[1:]
    assert len(texts) == len(case.expect.texts)
    for value, expected in zip(texts, case.expect.texts, strict=True):
        assert_text(value, expected)
    assert len(harness.messages.images) == case.expect.images
    assert len(harness.messages.tables) == case.expect.tables
    if case.expect.code:
        assert len(harness.sandbox.generated_code) == 1
        assert_text(harness.sandbox.generated_code[0], case.expect.code)
    else:
        assert not harness.sandbox.generated_code


def detail(error: Exception) -> str:
    return f"{type(error).__name__}: {error}" if str(error) else type(error).__name__


async def decision(
        case: StatsCase, harness: Harness, report: Report, name: str,
) -> tuple[Decision | None, bool]:
    result: Decision | None = None
    report.start(name)
    try:
        result = await harness.workflow._decide(context(), history(case.history))
        assert case.expect.decision is not None, "missing expect.decision"
        assert_decision(result, case.expect.decision)
    except Exception as error:
        report.add(name, "failed", detail(error))
        return result, False
    report.add(name, "passed", f"response: {result!r}")
    return result, True


async def order(
        case: StatsCase,
        harness: Harness,
        report: Report,
        name: str,
        description: str,
) -> tuple[StatsOrder | None, bool]:
    result: StatsOrder | None = None
    report.start(name)
    try:
        result = await harness.workflow._order_from_menu(context(), description)
        assert case.expect.order is not None, "missing expect.order"
        assert result == case.expect.order, f"expected {case.expect.order!r}; received {result!r}"
    except Exception as error:
        report.add(name, "failed", detail(error))
        return result, False
    report.add(name, "passed", f"response: {result!r}")
    return result, True


async def coder(
        case: StatsCase,
        harness: Harness,
        report: Report,
        name: str,
        stats_order: StatsOrder,
) -> bool:
    report.start(name)
    try:
        code = await harness.workflow._generate_code(context(), stats_order)
        ast.parse(code)
        assert case.expect.code is not None, "missing expect.code"
        assert_text(code, case.expect.code)
    except Exception as error:
        report.add(name, "failed", detail(error))
        return False
    report.add(name, "passed", f"response: {code!r}")
    return True


async def run_tail(
        case: StatsCase,
        harness: Harness,
        report: Report,
        stages: list[Literal["decision", "order", "coder"]],
        path: Path,
        active: bool,
        model_decision: Decision | None,
        model_order: StatsOrder | None,
) -> None:
    blocked_by = stages[0]
    for stage in stages[1:]:
        name = f"{stage} [{path}]"
        if not active:
            report.add(name, "blocked", f"{blocked_by} did not pass")
            continue

        if stage == "order":
            description = case.analysis_description
            if path == "model" and model_decision is not None:
                description = model_decision["analysis_description"]
            if description is None:
                report.add(name, "failed", "handoff did not provide an analysis description")
                passed, model_order = False, None
            else:
                model_order, passed = await order(case, harness, report, name, description)
        else:
            next_order = stats_order(case.order) if case.order is not None else None
            if path == "model":
                next_order = model_order
            if next_order is None:
                report.add(name, "failed", "handoff did not provide an order")
                passed = False
            else:
                passed = await coder(case, harness, report, name, next_order)

        if path == "model" and not passed:
            active, blocked_by = False, name


async def run_case(
        suite: TestSuite,
        case: StatsCase,
        responses_api: ResponsesAPI,
) -> None:
    print(f"\n[{case.id}] handoff={case.handoff}", flush=True)
    report = Report(case.id)
    harness = build_harness(
        suite, case.context, responses_api, turns=case.turns, execution=case.execution,
    )
    if case.run == "full":
        report.start("full workflow")
        try:
            await harness.workflow(context())
            assert_workflow(case, harness)
        except Exception as error:
            report.add("full workflow", "failed", detail(error))
        else:
            report.add(
                "full workflow",
                "passed",
                f"texts: {harness.messages.texts[1:]!r}; "
                f"images: {len(harness.messages.images)}; "
                f"tables: {len(harness.messages.tables)}; "
                f"code: {harness.sandbox.generated_code!r}",
            )
        report.finish()
        return

    match case.run:
        case "decision" | "order" | "coder":
            stages = [case.run]
        case list():
            stages = case.run
        case "full":
            raise AssertionError("Full workflow already handled")
    first_decision: Decision | None = None
    first_order: StatsOrder | None = None
    if stages[0] == "decision":
        first_decision, passed = await decision(case, harness, report, "decision")
    elif stages[0] == "order":
        assert case.analysis_description is not None
        first_order, passed = await order(
            case, harness, report, "order", case.analysis_description,
        )
    else:
        assert case.order is not None
        passed = await coder(case, harness, report, "coder", stats_order(case.order))

    if case.handoff in ("fixed", "both"):
        await run_tail(case, harness, report, stages, "fixed", True, None, None)
    if case.handoff in ("model", "both"):
        await run_tail(
            case, harness, report, stages, "model", passed, first_decision, first_order,
        )
    report.finish()
