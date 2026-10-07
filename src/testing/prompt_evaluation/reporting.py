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
    print(f"  {'Test':<32} Result")
    print(f"  {'-' * 32} ------")
    for test_name, value in result["tests"].items():
        name = test_name.replace("_", " ").title()
        rating = value["rating"].replace("_", " ").upper()
        print(f"  {name:<32} {rating}")

    summary = result["summary"]
    print(f"\nCase result: {'PASS' if summary['passed'] else 'FAIL'}")
    print(f"Quality score: {summary['score']:.0%}")
    print("\nEvaluator rationales:")
    for test_name, value in result["tests"].items():
        name = test_name.replace("_", " ").title()
        print(f"\n  {name} — {value['rating'].replace('_', ' ').upper()}")
        print(f"    {value['rationale']}")


def evaluation_failure_message(result: EvaluationRun) -> str:
    """Describe the configured tests that blocked a case from passing."""
    blocking_results = [
        f"{name}={result['tests'][name]['rating']}"
        for name in result["summary"]["blocking_tests"]
    ]
    return (
        "Tutor response did not satisfy all configured evaluation tests: "
        + ", ".join(blocking_results)
    )


def print_prompt_summary(results: list[EvaluationRun]) -> None:
    """Print aggregate measurements for the evaluated prompt."""
    passed = sum(result["summary"]["passed"] for result in results)
    average = sum(result["summary"]["score"] for result in results) / len(results)
    print(f"\n{'=' * 79}")
    print("Prompt evaluation summary")
    print(f"Cases passed: {passed}/{len(results)}")
    print(f"Average quality score: {average:.0%}")
    print("=" * 79)
