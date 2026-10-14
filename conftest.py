import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-prompt-evals",
        action="store_true",
        default=False,
        help="Run live, paid prompt evaluations.",
    )
    parser.addoption(
        "--config",
        action="store",
        help="Path to the rubber duck application config for e2e tests.",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    if config.getoption("--run-prompt-evals"):
        return
    skip = pytest.mark.skip(reason="Pass --run-prompt-evals to run live evaluations.")
    for item in items:
        if "prompt_eval" in item.keywords:
            item.add_marker(skip)
