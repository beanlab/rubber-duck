"""Terminal reporting for fixed-prefix tutor response evaluations."""

from src.testing.prompt_evaluation.types import EvaluationCase, EvaluationRun


def print_case_evaluation(case: EvaluationCase, result: EvaluationRun) -> None:
    """Print one case's response, ratings, and rationales."""
    print(f"\n{'=' * 79}")
    print(f"Case: {case['name']} [{case['id']}]")
    print("\nTutor response:")
    print(f"  {result['transcript'][-1]['message']}")
    _print_evaluation(result)
    print("=" * 79)


def _print_evaluation(result: EvaluationRun) -> None:
    """Print one case's ratings and rationales."""
    print("\nEvaluation tests:")
    print(f"  {'Test':<28} {'Rating':<24} {'Outcome':<14} Score")
    print(f"  {'-' * 28} {'-' * 24} {'-' * 14} -----")
    for test_name, value in result["tests"].items():
        name = test_name.replace("_", " ").title()
        rating = value["rating"].replace("_", " ").upper()
        outcome = (value["outcome"] or "measurement").upper()
        score = "—" if value["score"] is None else f"{value['score']:.2f}"
        print(f"  {name:<28} {rating:<24} {outcome:<14} {score}")

    summary = result["summary"]
    score = "—" if summary["score"] is None else f"{summary['score']:.0%}"
    print(f"\nCase result: {'PASS' if summary['passed'] else 'FAIL'}")
    print(f"Quality score: {score}")
    print("\nEvaluator rationales:")
    for test_name, value in result["tests"].items():
        name = test_name.replace("_", " ").title()
        print(f"\n  {name} — {value['rating'].replace('_', ' ').upper()}")
        print(f"    {value['rationale']}")


def evaluation_failure_message(result: EvaluationRun) -> str:
    """Describe the configured tests that blocked a case from passing."""
    blocking_results = [
        f"{name}={result['tests'][name]['rating']} "
        f"({result['tests'][name]['outcome']})"
        for name in result["summary"]["blocking_tests"]
    ]
    return (
        "Tutor response did not satisfy all configured evaluation tests: "
        + ", ".join(blocking_results)
    )


def print_prompt_summary(results: list[EvaluationRun]) -> None:
    """Print aggregate measurements for the evaluated prompt."""
    scores = [
        result["summary"]["score"]
        for result in results
        if result["summary"]["score"] is not None
    ]
    passed = sum(result["summary"]["passed"] for result in results)
    average = sum(scores) / len(scores) if scores else None
    print(f"\n{'=' * 79}")
    print("Prompt evaluation summary")
    print(f"Cases passed: {passed}/{len(results)}")
    print(f"Average quality score: {'—' if average is None else f'{average:.0%}'}")
    print("=" * 79)
