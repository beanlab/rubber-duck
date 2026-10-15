import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--config",
        action="store",
        help="Path to the rubber duck application config for e2e tests.",
    )
