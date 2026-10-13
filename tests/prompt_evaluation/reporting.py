"""Small console reports for tutor experiments."""

from tests.prompt_evaluation.types import EvaluationCase, EvaluationRun


def print_case_evaluation(case: EvaluationCase, result: EvaluationRun) -> None:
    """Print the response and each criterion result for one case."""
    status = "PASS" if result["summary"]["passed"] else "FAIL"
    print(f"\n{case['name']} [{case['id']}]: {status}")
    print(f"Response: {result['transcript'][-1]['message']}")
    for name, test in result["tests"].items():
        comparison = _jev_comparison(result, name)
        print(
            f"  {name}: {test['rating'].upper()} "
            f"({test['evaluator']}){comparison}"
        )
        if test["rationale"]:
            print(f"    {test['rationale']}")


def evaluation_failure_message(result: EvaluationRun) -> str:
    """Return a compact pytest failure message."""
    blocking = ", ".join(result["summary"]["blocking_tests"])
    return f"Failed criteria: {blocking}. See the evaluation output above."


def print_prompt_summary(results: list[EvaluationRun]) -> None:
    """Print a one-line aggregate after a multi-case run."""
    if len(results) < 2:
        return
    passed = sum(result["summary"]["passed"] for result in results)
    print(f"\nPrompt evaluation: {passed}/{len(results)} cases passed")


def _jev_comparison(result: EvaluationRun, name: str) -> str:
    test = result["tests"][name]
    if test["evaluator"] != "openai" or "jev" not in result:
        return ""
    jev_result = result["jev"]["tests"].get(name)
    if jev_result is None:
        return ""
    return (
        f", JEV {jev_result['rating'].upper()} "
        f"at {jev_result['confidence']:.0%} confidence"
    )
