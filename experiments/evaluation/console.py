"""Terminal reporting for fixed-prefix tutor response evaluations."""

from experiments.evaluation.types import (
    EvaluationCase,
    EvaluationRun,
    TestResult,
    TestSuite,
)


SUITE_LABELS: dict[TestSuite, str] = {
    "standard": "Standard",
    "case": "Case-specific",
    "rubber_duck": "Rubber Duck",
}


def print_case_evaluation(case: EvaluationCase, result: EvaluationRun) -> None:
    """Print one case's response and evaluator comparison."""
    print(f"\n{'=' * 104}")
    print(f"Case: {case['name']} [{case['id']}]")
    print("\nModels used:")
    print(f"  Response generator (OpenAI): {result['candidate_model']}")
    print(f"  Evaluator (OpenAI):          {result['openai_evaluator_model']}")
    if "jev" in result:
        print(f"  Evaluator (JEV):             {result['jev']['model']}")
    print("\nTutor response:")
    print(f"  {result['transcript'][-1]['message']}")

    if "selection" in result:
        selected = ", ".join(result["selection"]["selected"]) or "none"
        print(f"\nJEV-selected Rubber Duck tests: {selected}")
        if result["selection"]["uncertain"]:
            print(
                "Uncertain applicability: "
                + ", ".join(result["selection"]["uncertain"])
            )

    _print_evaluator_comparison(result)
    _print_case_result(result)
    _print_openai_rationales(result)
    print("=" * 104)


def _print_evaluator_comparison(result: EvaluationRun) -> None:
    semantic = result["tests"]
    print("\nModel-evaluated tests:")
    if "jev" not in result:
        print(f"  {'Test':<32} {'Suite':<15} OpenAI")
        print(f"  {'-' * 32} {'-' * 15} ------")
        for name, value in semantic.items():
            print(
                f"  {_test_label(name):<32} {SUITE_LABELS[value['suite']]:<15} "
                f"{value['rating'].upper()}"
            )
        return

    jev = result["jev"]
    print(
        f"  {'Test':<32} {'Suite':<15} {'OpenAI':<8} {'JEV':<8} "
        f"{'JEV conf.':<10} Agreement"
    )
    print(f"  {'-' * 32} {'-' * 15} {'-' * 8} {'-' * 8} {'-' * 10} ---------")
    for name, value in semantic.items():
        jev_value = jev["tests"][name]
        agrees = value["rating"] == jev_value["rating"]
        print(
            f"  {_test_label(name):<32} {SUITE_LABELS[value['suite']]:<15} "
            f"{value['rating'].upper():<8} {jev_value['rating'].upper():<8} "
            f"{jev_value['confidence']:<10.2f} {'YES' if agrees else 'NO'}"
        )

    openai_score = _score(semantic)
    jev_score = jev["summary"]["score"]
    agreed = sum(
        value["rating"] == jev["tests"][name]["rating"]
        for name, value in semantic.items()
    )
    print(f"\n  OpenAI score: {openai_score:.0%}")
    print(f"  JEV score:    {jev_score:.0%}")
    print(f"  Agreement:    {agreed}/{len(semantic)} ({agreed / len(semantic):.0%})")


def _print_case_result(result: EvaluationRun) -> None:
    summary = result["summary"]
    print(f"\nCase result: {'PASS' if summary['passed'] else 'FAIL'}")
    print("Pass rule: every OpenAI rating must pass.")


def _print_openai_rationales(result: EvaluationRun) -> None:
    print("\nOpenAI evaluator rationales:")
    for name, value in result["tests"].items():
        suite = SUITE_LABELS[value["suite"]]
        print(f"\n  {_test_label(name)} [{suite}] — {value['rating'].upper()}")
        print(f"    {value['rationale']}")


def evaluation_failure_message(result: EvaluationRun) -> str:
    """Summarize failures without overflowing pytest's short output."""
    blocking = result["summary"]["blocking_tests"]
    counts: dict[TestSuite, int] = {
        suite: sum(result["tests"][name]["suite"] == suite for name in blocking)
        for suite in SUITE_LABELS
    }
    categories = ", ".join(
        f"{SUITE_LABELS[suite]}: {count}"
        for suite, count in counts.items()
        if count
    )
    return (
        f"Case failed {len(blocking)} of {len(result['tests'])} criteria "
        f"({categories}). See the evaluator comparison above."
    )


def print_prompt_summary(
    results: list[EvaluationRun],
    cases: list[EvaluationCase] | None = None,
) -> None:
    """Print aggregate evaluator scores for multi-case runs."""
    if len(results) == 1:
        return
    if cases is not None and len(cases) != len(results):
        raise ValueError("Prompt summary cases and results must have equal lengths")
    print(f"\n{'=' * 104}")
    print("Prompt evaluation summary")

    if cases is not None:
        print("\nCases:")
        for case, result in zip(cases, results, strict=True):
            summary = result["summary"]
            passed = len(result["tests"]) - len(summary["blocking_tests"])
            status = "PASS" if summary["passed"] else "FAIL"
            print(
                f"  {status:<4}  {case['id']} "
                f"({passed}/{len(result['tests'])} checks passed)"
            )

    jev_runs = [result for result in results if "jev" in result]
    semantic = [result["tests"] for result in results]
    print("\nModel-evaluated tests:")
    print(f"  OpenAI average score: {_average_score(semantic):.0%}")
    if jev_runs:
        jev_scores = [result["jev"]["summary"]["score"] for result in jev_runs]
        agreements = [
            openai["rating"] == result["jev"]["tests"][name]["rating"]
            for result in jev_runs
            for name, openai in result["tests"].items()
        ]
        print(f"  JEV average score:    {sum(jev_scores) / len(jev_scores):.0%}")
        print(
            f"  Evaluator agreement:  {sum(agreements)}/{len(agreements)} "
            f"({sum(agreements) / len(agreements):.0%})"
        )

    passed_cases = sum(result["summary"]["passed"] for result in results)
    print(f"\nCases passed: {passed_cases}/{len(results)}")
    print("Pass rule: every OpenAI rating must pass.")
    print("=" * 104)


def _score(results: dict[str, TestResult]) -> float:
    return sum(value["rating"] == "pass" for value in results.values()) / len(results)


def _average_score(results: list[dict[str, TestResult]]) -> float:
    return sum(_score(result) for result in results) / len(results)


def _test_label(name: str) -> str:
    return name.replace("_", " ").title()
