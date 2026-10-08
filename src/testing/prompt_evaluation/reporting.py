"""Terminal reporting for fixed-prefix tutor response evaluations."""

from src.testing.prompt_evaluation.types import (
    EvaluationCase,
    EvaluationRun,
    JevEvaluation,
)


def print_case_evaluation(case: EvaluationCase, result: EvaluationRun) -> None:
    """Print one case's response, ratings, and rationales."""
    print(f"\n{'=' * 79}")
    print(f"Case: {case['name']} [{case['id']}]")
    print("\nTutor response:")
    print(f"  {result['transcript'][-1]['message']}")
    _print_openai_evaluation(result)
    if "jev" in result:
        _print_jev_evaluation(result["jev"])
    print("=" * 79)


def _print_openai_evaluation(result: EvaluationRun) -> None:
    """Print OpenAI ratings and rationales."""
    print("\nOpenAI evaluation:")
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


def _print_jev_evaluation(evaluation: JevEvaluation) -> None:
    """Print JEV ratings and confidence."""
    print(f"\nJEV evaluation ({evaluation['model']}):")
    print(f"  {'Test':<32} {'Result':<8} {'Confidence':<10} P(pass)")
    print(f"  {'-' * 32} {'-' * 8} {'-' * 10} -------")
    for test_name, value in evaluation["tests"].items():
        name = test_name.replace("_", " ").title()
        print(
            f"  {name:<32} {value['rating'].upper():<8} "
            f"{value['confidence']:<10.2f} {value['probabilities']['pass']:.2f}"
        )

    summary = evaluation["summary"]
    print(f"\nJEV case result: {'PASS' if summary['passed'] else 'FAIL'}")
    print(f"JEV quality score: {summary['score']:.0%}")


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
    print(f"OpenAI cases passed: {passed}/{len(results)}")
    print(f"OpenAI average quality score: {average:.0%}")

    jev_results = [result["jev"] for result in results if "jev" in result]
    if jev_results:
        jev_passed = sum(result["summary"]["passed"] for result in jev_results)
        jev_average = sum(
            result["summary"]["score"] for result in jev_results
        ) / len(jev_results)
        confidences = [
            test["confidence"]
            for result in jev_results
            for test in result["tests"].values()
        ]
        print(f"JEV cases passed: {jev_passed}/{len(jev_results)}")
        print(f"JEV average quality score: {jev_average:.0%}")
        print(f"JEV average confidence: {sum(confidences) / len(confidences):.2f}")
    print("=" * 79)
