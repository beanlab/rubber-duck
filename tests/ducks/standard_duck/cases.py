from pathlib import Path


# Validate Standard Duck YAML and return cases and criteria for the requested scope.
def load_cases(path: Path, *, run: str = "response") -> list[dict]:
    ...
